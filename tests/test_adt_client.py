"""Tests for the shared ADT HTTP client (sap_adt.adt.client).

Focus of this suite: every ADT request -- including the CSRF-token fetch and
its 403-triggered retry -- must carry the client as the ``sap-client`` query
parameter, because some NetWeaver gateways authenticate/mandate the client via
the URL parameter rather than (or in addition to) the ``X-SAP-Client`` header.

The transport collector reuses this client with an explicitly injected config
(``set_config``); the tests exercise that override path.

No real SAP system is contacted: the requests session and config are mocked.
"""
import unittest
from unittest.mock import MagicMock, patch

import requests
from requests.auth import HTTPBasicAuth

from sap_adt.adt import client as client_module  # noqa: E402
from sap_adt.adt.client import AdtHttpError  # noqa: E402
from sap_adt.config import SapConfig  # noqa: E402

URL = "https://sap.example.com:8000/sap/bc/adt/discovery"


def _make_response(status=200, text="", csrf_token=None, cookies=None, raise_exc=None):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.headers = {"x-csrf-token": csrf_token} if csrf_token else {}
    resp.cookies = cookies if cookies is not None else {}
    if raise_exc is not None:
        resp.raise_for_status.side_effect = raise_exc
    else:
        resp.raise_for_status.return_value = None
    return resp


def _is_csrf(call) -> bool:
    headers = call.kwargs.get("headers") or {}
    return headers.get("x-csrf-token") == "fetch"


class SapClientParameterTests(unittest.TestCase):
    def setUp(self):
        # Reset module-level cached state so tests do not influence each other.
        client_module._csrf_token = None
        client_module._session = None
        client_module._session_cookies = None
        client_module._active_config = None

        self.cfg = SapConfig(
            url="https://sap.example.com:8000",
            username="alice",
            password="secret-pw",
            client="100",
            verify_ssl=True,
        )
        self.session = MagicMock()
        self.csrf_tokens = []
        self.csrf_cookies = None
        self.responses = []

        def _route(method=None, url=None, headers=None, **kwargs):
            if (headers or {}).get("x-csrf-token") == "fetch":
                token = self.csrf_tokens.pop(0) if self.csrf_tokens else "TOKEN-1"
                return _make_response(200, csrf_token=token,
                                      cookies=self.csrf_cookies)
            if self.responses:
                return self.responses.pop(0)
            return _make_response(200)

        self.session.request.side_effect = _route
        patch.object(client_module, "_get_session", return_value=self.session).start()
        # The connection is injected explicitly (transport collection path).
        client_module.set_config(self.cfg)
        self.addCleanup(patch.stopall)
        self.addCleanup(self._reset_module_globals)

    def _reset_module_globals(self):
        client_module._csrf_token = None
        client_module._session = None
        client_module._session_cookies = None
        client_module._active_config = None

    def _calls(self):
        return self.session.request.call_args_list

    def _business_calls(self):
        return [c for c in self._calls() if not _is_csrf(c)]

    def _csrf_calls(self):
        return [c for c in self._calls() if _is_csrf(c)]

    # --- Tests 1-4: sap-client defaulting on the business request ---------

    def test_get_without_params_adds_sap_client_and_keeps_header(self):
        client_module.make_adt_request(URL)

        # GET never needs a CSRF pre-flight.
        self.assertEqual(self._csrf_calls(), [])

        kwargs = self._business_calls()[0].kwargs
        self.assertEqual(kwargs["method"], "GET")
        self.assertEqual(kwargs["params"], {"sap-client": "100"})
        # The header must remain for gateways that rely on it.
        self.assertEqual(kwargs["headers"]["X-SAP-Client"], "100")

    def test_existing_params_are_kept_alongside_sap_client(self):
        client_module.make_adt_request(URL, params={"foo": "bar"})

        kwargs = self._business_calls()[0].kwargs
        self.assertEqual(kwargs["params"], {"foo": "bar", "sap-client": "100"})

    def test_explicit_sap_client_is_not_overridden_by_config(self):
        client_module.make_adt_request(URL, params={"sap-client": "200"})

        kwargs = self._business_calls()[0].kwargs
        self.assertEqual(kwargs["params"], {"sap-client": "200"})
        # Header still reflects the configured client.
        self.assertEqual(kwargs["headers"]["X-SAP-Client"], "100")

    def test_caller_params_dict_is_not_mutated(self):
        original_params = {"foo": "bar"}

        client_module.make_adt_request(URL, params=original_params)

        self.assertEqual(original_params, {"foo": "bar"})
        self.assertIsNot(self._business_calls()[0].kwargs["params"], original_params)

    # --- Test 5: CSRF pre-flight uses the same query parameters -----------

    def test_post_csrf_fetch_uses_same_params_as_business_request(self):
        client_module.make_adt_request(URL, method="POST", params={"foo": "bar"})

        csrf = self._csrf_calls()
        self.assertEqual(len(csrf), 1)
        self.assertEqual(csrf[0].kwargs["method"], "GET")
        self.assertEqual(csrf[0].kwargs.get("params"),
                         {"foo": "bar", "sap-client": "100"})
        self.assertEqual(csrf[0].kwargs["headers"]["X-SAP-Client"], "100")

        req = self._business_calls()[0].kwargs
        self.assertEqual(req["method"], "POST")
        self.assertEqual(req["params"], {"foo": "bar", "sap-client": "100"})
        self.assertEqual(req["headers"]["x-csrf-token"], "TOKEN-1")

    # --- Test 6: 403 + CSRF retry keeps the parameters --------------------

    def test_csrf_retry_refetches_with_sap_client_and_preserves_params(self):
        self.responses = [
            _make_response(403, text="CSRF token validation failed"),
            _make_response(200),
        ]
        self.csrf_tokens = ["TOKEN-1", "TOKEN-2"]

        client_module.make_adt_request(URL, method="POST", params={"foo": "bar"})

        expected_params = {"foo": "bar", "sap-client": "100"}
        csrf = self._csrf_calls()
        self.assertEqual(len(csrf), 2)
        for call in csrf:
            self.assertEqual(call.kwargs.get("params"), expected_params)

        business = self._business_calls()
        self.assertEqual(len(business), 2)
        for call in business:
            self.assertEqual(call.kwargs.get("params"), expected_params)
            self.assertEqual(call.kwargs["method"], "POST")
        self.assertEqual(business[-1].kwargs["headers"]["x-csrf-token"], "TOKEN-2")

    def test_csrf_retry_keeps_explicit_sap_client(self):
        self.responses = [
            _make_response(403, text="CSRF"),
            _make_response(200),
        ]
        self.csrf_tokens = ["TOKEN-1", "TOKEN-2"]

        client_module.make_adt_request(
            URL, method="PUT", params={"foo": "bar", "sap-client": "200"}
        )

        expected_params = {"foo": "bar", "sap-client": "200"}
        for call in self._csrf_calls():
            self.assertEqual(call.kwargs.get("params"), expected_params)
        for call in self._business_calls():
            self.assertEqual(call.kwargs.get("params"), expected_params)
        # Explicit query value wins; header stays at the configured client.
        self.assertEqual(self._csrf_calls()[0].kwargs["headers"]["X-SAP-Client"], "100")

    # --- Test 7: existing behaviour must not regress ----------------------

    def test_passes_auth_method_verify_timeout_data_and_merged_headers(self):
        client_module.make_adt_request(
            URL,
            method="GET",
            timeout=45,
            data=b"<payload/>",
            extra_headers={"Accept": "application/xml"},
        )

        kwargs = self._business_calls()[0].kwargs
        self.assertIsInstance(kwargs["auth"], HTTPBasicAuth)
        self.assertEqual(kwargs["auth"].username, "alice")
        self.assertEqual(kwargs["auth"].password, "secret-pw")
        self.assertEqual(kwargs["method"], "GET")
        self.assertIs(kwargs["verify"], True)
        self.assertEqual(kwargs["timeout"], 45)
        self.assertEqual(kwargs["data"], b"<payload/>")
        self.assertEqual(kwargs["headers"]["X-SAP-Client"], "100")
        self.assertEqual(kwargs["headers"]["Accept"], "application/xml")
        self.assertEqual(kwargs["cookies"], {})

    def test_ssl_verification_setting_is_passed_through(self):
        self.cfg.verify_ssl = False
        client_module.make_adt_request(URL)
        self.assertIs(self._business_calls()[0].kwargs["verify"], False)

    def test_cookies_from_csrf_fetch_are_sent_on_business_request(self):
        self.csrf_cookies = {"JSESSIONID": "abc"}
        client_module.make_adt_request(URL, method="POST")

        self.assertEqual(
            self._business_calls()[0].kwargs["cookies"],
            {"JSESSIONID": "abc"},
        )

    def test_http_error_is_propagated(self):
        resp = _make_response(500)
        resp.raise_for_status.side_effect = requests.HTTPError(
            "500 Server Error", response=resp
        )
        self.responses = [resp]
        with self.assertRaises(AdtHttpError) as ctx:
            client_module.make_adt_request(URL)
        self.assertEqual(ctx.exception.status, 500)


if __name__ == "__main__":
    unittest.main()
