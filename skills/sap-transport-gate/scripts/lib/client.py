from typing import Optional

import requests
import urllib3
from requests.auth import HTTPBasicAuth

from .config import SapConfig, get_config

_session: Optional[requests.Session] = None
_csrf_token: Optional[str] = None
_session_cookies: Optional[dict] = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
    return _session


def _auth_headers(config: SapConfig) -> dict:
    return {"X-SAP-Client": config.client}


def _fetch_csrf_token(
    url: str, config: SapConfig, params: Optional[dict] = None
) -> str:
    global _session_cookies
    resp = _get_session().get(
        url,
        auth=HTTPBasicAuth(config.username, config.password),
        headers={**_auth_headers(config), "x-csrf-token": "fetch"},
        params=params,
        verify=config.verify_ssl,
        timeout=30,
    )
    token = resp.headers.get("x-csrf-token")
    if not token:
        raise RuntimeError("No CSRF token received from SAP server")
    if resp.cookies:
        _session_cookies = dict(resp.cookies)
    return token


def make_adt_request(
    url: str,
    method: str = "GET",
    timeout: int = 30,
    data=None,
    params: Optional[dict] = None,
    extra_headers: Optional[dict] = None,
) -> requests.Response:
    global _csrf_token, _session_cookies

    config = get_config()
    headers = _auth_headers(config)
    if extra_headers:
        headers.update(extra_headers)

    # Some gateways select/mandate the SAP client via the sap-client query
    # parameter during Basic Auth login, so send it on every request -- the
    # CSRF pre-flight, the business call, and the CSRF retry included. Copy
    # the caller's dict (never mutate it) and let an explicit sap-client win.
    request_params = dict(params or {})
    request_params.setdefault("sap-client", config.client)

    if not config.verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if method in ("POST", "PUT") and not _csrf_token:
        _csrf_token = _fetch_csrf_token(url, config, request_params)

    if method in ("POST", "PUT") and _csrf_token:
        headers["x-csrf-token"] = _csrf_token

    def _do() -> requests.Response:
        return _get_session().request(
            method=method,
            url=url,
            auth=HTTPBasicAuth(config.username, config.password),
            headers=headers,
            verify=config.verify_ssl,
            timeout=timeout,
            data=data,
            params=request_params,
            cookies=_session_cookies or {},
        )

    resp = _do()

    if resp.status_code == 403 and "CSRF" in (resp.text or ""):
        _csrf_token = _fetch_csrf_token(url, config, request_params)
        headers["x-csrf-token"] = _csrf_token
        resp = _do()

    resp.raise_for_status()
    return resp
