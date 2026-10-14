"""Tests for the sap-transport-gate ADT HTTP client (lib/client.py).

Focus of this suite: every ADT request -- including the CSRF-token fetch and
its 403-triggered retry -- must carry the client as the ``sap-client`` query
parameter, because some NetWeaver gateways authenticate/mandate the client via
the URL parameter rather than (or in addition to) the ``X-SAP-Client`` header.

No real SAP system is contacted: the requests session and config are mocked.
"""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests
from requests.auth import HTTPBasicAuth

ROOT = Path(__file__).resolve().parents[1]
_GATE_LIB = ROOT / "skills" / "sap-transport-gate" / "scripts" / "lib"

# Both skills ship a top-level package called ``lib``. Under ``unittest
# discover`` the sap-adt-cli tests run first and cache their ``lib`` in
# sys.modules, so a plain ``from lib.client import ...`` here would silently
# resolve to the *adt-cli* client. Load the transport-gate package under a
# unique, isolated name instead and leave the shared ``lib`` untouched.
_PKG_NAME = "_sap_transport_gate_lib_under_test"
_pkg = types.ModuleType(_PKG_NAME)
_pkg.__path__ = [str(_GATE_LIB)]
sys.modules[_PKG_NAME] = _pkg


def _load_submodule(short_name: str, file_name: str):
    full_name = f"{_PKG_NAME}.{short_name}"
    spec = importlib.util.spec_from_file_location(full_name, _GATE_LIB / file_name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


config_module = _load_submodule("config", "config.py")
client_module = _load_submodule("client", "client.py")

SapConfig = config_module.SapConfig

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


class SapClientParameterTests(unittest.TestCase):
    def setUp(self):
        # Reset module-level cached state so tests do not influence each other.
        client_module._csrf_token = None
        client_module._session = None
        client_module._session_cookies = None

        self.cfg = SapConfig(
            url="https://sap.example.com:8000",
            username="alice",
            password="secret-pw",
            client="100",
            verify_ssl=True,
        )
        self.session = MagicMock()
        self.session.request.return_value = _make_response(200)
        self.session.get.return_value = _make_response(200, csrf_token="TOKEN-1")

        patch.object(client_module, "_get_session", return_value=self.session).start()
        patch.object(client_module, "get_config", return_value=self.cfg).start()
        self.addCleanup(patch.stopall)
        self.addCleanup(self._reset_module_globals)

    def _reset_module_globals(self):
        client_module._csrf_token = None
        client_module._session = None
        client_module._session_cookies = None

    # --- Tests 1-4: sap-client defaulting on the business request ---------

    def test_get_without_params_adds_sap_client_and_keeps_header(self):
        client_module.make_adt_request(URL)

        # GET never needs a CSRF pre-flight.
        self.session.get.assert_not_called()

        kwargs = self.session.request.call_args.kwargs
        self.assertEqual(kwargs["method"], "GET")
        self.assertEqual(kwargs["params"], {"sap-client": "100"})
        # The header must remain for gateways that rely on it.
        self.assertEqual(kwargs["headers"]["X-SAP-Client"], "100")

    def test_existing_params_are_kept_alongside_sap_client(self):
        client_module.make_adt_request(URL, params={"foo": "bar"})

        kwargs = self.session.request.call_args.kwargs
        self.assertEqual(kwargs["params"], {"foo": "bar", "sap-client": "100"})

    def test_explicit_sap_client_is_not_overridden_by_config(self):
        client_module.make_adt_request(URL, params={"sap-client": "200"})

        kwargs = self.session.request.call_args.kwargs
        self.assertEqual(kwargs["params"], {"sap-client": "200"})
        # Header still reflects the configured client.
        self.assertEqual(kwargs["headers"]["X-SAP-Client"], "100")

    def test_caller_params_dict_is_not_mutated(self):
        original_params = {"foo": "bar"}

        client_module.make_adt_request(URL, params=original_params)

        self.assertEqual(original_params, {"foo": "bar"})
        self.assertIsNot(self.session.request.call_args.kwargs["params"], original_params)

    # --- Test 5: CSRF pre-flight uses the same query parameters -----------

    def test_post_csrf_fetch_uses_same_params_as_business_request(self):
        client_module.make_adt_request(URL, method="POST", params={"foo": "bar"})

        # One CSRF fetch before the POST.
        self.assertEqual(self.session.get.call_count, 1)
        get_kwargs = self.session.get.call_args.kwargs
        self.assertEqual(get_kwargs.get("params"), {"foo": "bar", "sap-client": "100"})
        self.assertEqual(get_kwargs["headers"]["x-csrf-token"], "fetch")
        self.assertEqual(get_kwargs["headers"]["X-SAP-Client"], "100")

        req_kwargs = self.session.request.call_args.kwargs
        self.assertEqual(req_kwargs["method"], "POST")
        self.assertEqual(req_kwargs["params"], {"foo": "bar", "sap-client": "100"})
        self.assertEqual(req_kwargs["headers"]["x-csrf-token"], "TOKEN-1")

    # --- Test 6: 403 + CSRF retry keeps the parameters --------------------

    def test_csrf_retry_refetches_with_sap_client_and_preserves_params(self):
        forbidden = _make_response(403, text="CSRF token validation failed")
        ok = _make_response(200)
        self.session.request.side_effect = [forbidden, ok]
        self.session.get.side_effect = [
            _make_response(200, csrf_token="TOKEN-1"),
            _make_response(200, csrf_token="TOKEN-2"),
        ]

        client_module.make_adt_request(URL, method="POST", params={"foo": "bar"})

        expected_params = {"foo": "bar", "sap-client": "100"}
        # Both the initial fetch and the post-403 re-fetch carry the params.
        self.assertEqual(self.session.get.call_count, 2)
        for get_call in self.session.get.call_args_list:
            self.assertEqual(get_call.kwargs.get("params"), expected_params)

        # Both business attempts carry the params; the retry uses the new token.
        self.assertEqual(self.session.request.call_count, 2)
        for request_call in self.session.request.call_args_list:
            self.assertEqual(request_call.kwargs.get("params"), expected_params)
            self.assertEqual(request_call.kwargs["method"], "POST")
        self.assertEqual(
            self.session.request.call_args.kwargs["headers"]["x-csrf-token"],
            "TOKEN-2",
        )

    def test_csrf_retry_keeps_explicit_sap_client(self):
        forbidden = _make_response(403, text="CSRF")
        ok = _make_response(200)
        self.session.request.side_effect = [forbidden, ok]
        self.session.get.side_effect = [
            _make_response(200, csrf_token="TOKEN-1"),
            _make_response(200, csrf_token="TOKEN-2"),
        ]

        client_module.make_adt_request(
            URL, method="PUT", params={"foo": "bar", "sap-client": "200"}
        )

        expected_params = {"foo": "bar", "sap-client": "200"}
        for get_call in self.session.get.call_args_list:
            self.assertEqual(get_call.kwargs.get("params"), expected_params)
        for request_call in self.session.request.call_args_list:
            self.assertEqual(request_call.kwargs.get("params"), expected_params)
        # Explicit query value wins; header stays at the configured client.
        self.assertEqual(
            self.session.get.call_args.kwargs["headers"]["X-SAP-Client"], "100"
        )

    # --- Test 7: existing behaviour must not regress ----------------------

    def test_passes_auth_method_verify_timeout_data_and_merged_headers(self):
        client_module.make_adt_request(
            URL,
            method="GET",
            timeout=45,
            data=b"<payload/>",
            extra_headers={"Accept": "application/xml"},
        )

        kwargs = self.session.request.call_args.kwargs
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
        self.assertIs(self.session.request.call_args.kwargs["verify"], False)

    def test_cookies_from_csrf_fetch_are_sent_on_business_request(self):
        self.session.get.return_value = _make_response(
            200, csrf_token="TOKEN-1", cookies={"JSESSIONID": "abc"}
        )
        client_module.make_adt_request(URL, method="POST")

        self.assertEqual(
            self.session.request.call_args.kwargs["cookies"],
            {"JSESSIONID": "abc"},
        )

    def test_http_error_is_propagated(self):
        self.session.request.return_value = _make_response(
            500, raise_exc=requests.HTTPError("500 Server Error")
        )
        with self.assertRaises(requests.HTTPError):
            client_module.make_adt_request(URL)


if __name__ == "__main__":
    unittest.main()
