from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
import urllib3
from requests.auth import HTTPBasicAuth

from . import log_redaction
from .config import SapConfig, get_config

_session: Optional[requests.Session] = None
_csrf_token: Optional[str] = None
_session_cookies: Optional[dict] = None

# Query parameters whose values must never appear in error messages.
_SENSITIVE_QUERY_RE = ("token", "password", "passwd", "secret", "codepage")
_MAX_BODY_CHARS = 500


class AdtHttpError(Exception):
    """HTTP failure carrying only sanitized, safe-to-print information."""

    def __init__(self, message: str, *, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
    return _session


def _safe_url(url: str) -> str:
    """Strip sensitive query parameters before including a URL in any message."""
    try:
        parsed = urlparse(url)
        kept = [(k, v) for k, v in parse_qsl(parsed.query)
                if not any(s in k.lower() for s in _SENSITIVE_QUERY_RE)]
        return urlunparse(parsed._replace(query=urlencode(kept)))
    except ValueError:
        return url


def _redact(text, config: SapConfig) -> str:
    return log_redaction.redact(text, secret=config.password, username=config.username)


def _wrap_error(exc: Exception, config: SapConfig, method: str, url: str) -> AdtHttpError:
    """Translate requests exceptions into sanitized AdtHttpError instances."""
    safe_url = _safe_url(url)
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        response = exc.response
        body = _redact(response.text or "", config)[:_MAX_BODY_CHARS]
        return AdtHttpError(
            f"HTTP {response.status_code} for {method} {safe_url}: {body}".rstrip(": "),
            status=response.status_code,
        )
    message = _redact(str(exc), config)
    return AdtHttpError(f"{type(exc).__name__} for {method} {safe_url}: {message}")


def _request(config: SapConfig, method: str, url: str, **kwargs) -> requests.Response:
    try:
        return _get_session().request(method=method, url=url, **kwargs)
    except requests.RequestException as e:
        # Chain discarded ('from None'): a requests PreparedRequest repr in
        # the chain carries the Authorization header.
        raise _wrap_error(e, config, method, url) from None


def _auth_headers(config: SapConfig) -> dict:
    return {"X-SAP-Client": config.client}


def _fetch_csrf_token(url: str, config: SapConfig) -> str:
    global _session_cookies
    resp = _request(
        config,
        "GET",
        url,
        auth=HTTPBasicAuth(config.username, config.password),
        headers={**_auth_headers(config), "x-csrf-token": "fetch"},
        verify=config.verify_ssl,
        timeout=30,
    )
    token = resp.headers.get("x-csrf-token")
    if not token:
        raise AdtHttpError("No CSRF token received from SAP server")
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
    # Feed the live secret to the log filter so literal/Base64 leaks are
    # scrubbed even from libraries that log raw objects.
    log_redaction.set_secret(config.password, config.username)
    headers = _auth_headers(config)
    if extra_headers:
        headers.update(extra_headers)

    if not config.verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if method in ("POST", "PUT") and not _csrf_token:
        _csrf_token = _fetch_csrf_token(url, config)

    if method in ("POST", "PUT") and _csrf_token:
        headers["x-csrf-token"] = _csrf_token

    resp = _request(
        config,
        method,
        url,
        auth=HTTPBasicAuth(config.username, config.password),
        headers=headers,
        verify=config.verify_ssl,
        timeout=timeout,
        data=data,
        params=params,
        cookies=_session_cookies or {},
    )

    if resp.status_code == 403 and "CSRF" in (resp.text or ""):
        _csrf_token = _fetch_csrf_token(url, config)
        headers["x-csrf-token"] = _csrf_token
        resp = _request(
            config,
            method,
            url,
            auth=HTTPBasicAuth(config.username, config.password),
            headers=headers,
            verify=config.verify_ssl,
            timeout=timeout,
            data=data,
            params=params,
            cookies=_session_cookies or {},
        )

    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        raise _wrap_error(e, config, method, url) from None
    return resp
