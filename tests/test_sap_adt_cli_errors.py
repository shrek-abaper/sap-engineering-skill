"""Batch 4a tests for the closed error-code set and the single classifier."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "sap-adt-cli" / "scripts"
FIXTURES = ROOT / "skills" / "sap-adt-cli" / "tests" / "fixtures"
sys.path.insert(0, str(SCRIPTS))

from lib import errors  # noqa: E402
from lib.client import AdtHttpError  # noqa: E402
from lib.parsers.common import ParseError  # noqa: E402


class ClosedSetTests(unittest.TestCase):
    def test_sixteen_codes_complete_and_exclusive(self):
        self.assertEqual(len(errors.ALL_CODES), 16)
        self.assertEqual(len(set(errors.ALL_CODES)), 16)
        # Every code has an exit tier and nothing has a tier without a code.
        self.assertEqual(set(errors.EXIT_CODE_MAP), set(errors.ALL_CODES))
        self.assertTrue(all(v in (1, 2, 3, 4) for v in errors.EXIT_CODE_MAP.values()))

    def test_exit_tier_assignment(self):
        expected = {
            2: {errors.CONFIG_MISSING, errors.PROFILE_NOT_FOUND, errors.AUTH_FAILED},
            3: {errors.WRITE_DISABLED, errors.TRANSPORT_DISABLED,
                errors.CONFIRM_REQUIRED, errors.USER_ABORTED, errors.DML_REJECTED},
            4: {errors.OBJECT_NOT_FOUND},
            1: {errors.CSRF_EXPIRED, errors.SERVICE_NOT_ACTIVE, errors.BAD_REQUEST,
                errors.SERVER_ERROR, errors.LOCKED_BY_OTHER, errors.NETWORK_ERROR,
                errors.PARSE_FAILED},
        }
        for tier, codes in expected.items():
            for code in codes:
                self.assertEqual(errors.exit_code_for(code), tier, code)

    def test_decision_has_hint_and_envelope(self):
        d = errors.decision(errors.OBJECT_NOT_FOUND, "Resource CLASS X does not exist.",
                            http_status=404)
        self.assertEqual(d.exit_code, 4)
        self.assertTrue(d.hint)
        env = d.to_envelope("get-class", profile="dev")
        self.assertFalse(env["ok"])
        self.assertEqual(env["format_version"], 1)
        self.assertEqual(env["command"], "get-class")
        self.assertEqual(env["profile"], "dev")
        self.assertEqual(env["error"]["code"], "OBJECT_NOT_FOUND")
        self.assertEqual(env["error"]["http_status"], 404)


class GateClassifyTests(unittest.TestCase):
    def test_every_gate_is_tier_3(self):
        for code in errors.GATE_CODES:
            d = errors.classify(gate=code)
            self.assertEqual(d.exit_code, 3, code)
            self.assertEqual(d.code, code)

    def test_unknown_gate_rejected(self):
        with self.assertRaises(ValueError):
            errors.classify(gate="BOGUS")


class HttpClassifyTests(unittest.TestCase):
    def _fixture(self, name):
        return (FIXTURES / name).read_text(encoding="utf-8", errors="replace")

    def test_real_404_body_is_object_not_found_tier_4(self):
        body = self._fixture("error.404.xml")
        d = errors.classify(AdtHttpError(f"HTTP 404 for GET url: {body}", status=404))
        self.assertEqual(d.code, errors.OBJECT_NOT_FOUND)
        self.assertEqual(d.exit_code, 4)
        self.assertEqual(d.http_status, 404)

    def test_404_no_suitable_resource_is_bad_request(self):
        d = errors.classify(AdtHttpError("HTTP 404 for POST url: No suitable resource found",
                                         status=404))
        self.assertEqual(d.code, errors.BAD_REQUEST)
        self.assertEqual(d.exit_code, 1)

    def test_real_405_body_is_bad_request(self):
        body = self._fixture("error.405-usageReferences.raw.xml")
        d = errors.classify(AdtHttpError(f"HTTP 405 for GET url: {body}", status=405))
        self.assertEqual(d.code, errors.BAD_REQUEST)
        self.assertEqual(d.exit_code, 1)

    def test_405_legacy_whereused_text_is_bad_request(self):
        body = self._fixture("error.405-whereused-legacy.txt")
        d = errors.classify(http_status=405, body=body)
        self.assertEqual(d.code, errors.BAD_REQUEST)

    def test_406_415_400_are_bad_request(self):
        for status in (400, 406, 409, 415):
            d = errors.classify(http_status=status, body="x")
            self.assertEqual(d.code, errors.BAD_REQUEST, status)

    def test_csrf_403_distinct_from_auth_403(self):
        csrf = self._fixture("error.403-csrf.txt")
        d = errors.classify(AdtHttpError(f"HTTP 403: {csrf}", status=403))
        self.assertEqual(d.code, errors.CSRF_EXPIRED)
        self.assertEqual(d.exit_code, 1)
        d2 = errors.classify(AdtHttpError("HTTP 403: forbidden", status=403))
        self.assertEqual(d2.code, errors.AUTH_FAILED)
        self.assertEqual(d2.exit_code, 2)

    def test_401_is_auth_failed_tier_2(self):
        self.assertEqual(errors.classify(http_status=401).code, errors.AUTH_FAILED)

    def test_503_is_service_inactive_not_server_error(self):
        d = errors.classify(http_status=503, body="service unavailable")
        self.assertEqual(d.code, errors.SERVICE_NOT_ACTIVE)
        self.assertEqual(d.exit_code, 1)

    def test_unexpected_500_is_server_error_not_client_error(self):
        d = errors.classify(AdtHttpError(
            "HTTP 500 for POST url: Error while converting object references",
            status=500))
        self.assertEqual(d.code, errors.SERVER_ERROR)
        self.assertEqual(d.exit_code, 1)

    def test_423_is_locked(self):
        self.assertEqual(errors.classify(http_status=423).code, errors.LOCKED_BY_OTHER)

    def test_no_status_connection_failure_is_network_error(self):
        d = errors.classify(AdtHttpError(
            "ConnectionError for GET https://host/sap/bc/adt/...: timed out"))
        self.assertEqual(d.code, errors.NETWORK_ERROR)
        self.assertEqual(d.exit_code, 1)

    def test_config_and_profile_gates(self):
        self.assertEqual(errors.decision(errors.CONFIG_MISSING, "x").exit_code, 2)
        self.assertEqual(errors.decision(errors.PROFILE_NOT_FOUND, "x").exit_code, 2)


class LocalExceptionTests(unittest.TestCase):
    def test_parse_error_is_parse_failed_tier_1(self):
        d = errors.classify(ParseError("malformed XML"))
        self.assertEqual(d.code, errors.PARSE_FAILED)
        self.assertEqual(d.exit_code, 1)

    def test_value_error_is_bad_request(self):
        d = errors.classify(ValueError("--group is required for object type 'function'"))
        self.assertEqual(d.code, errors.BAD_REQUEST)
        self.assertEqual(d.exit_code, 1)

    def test_bare_message_falls_back_to_server_error(self):
        d = errors.classify(message="boom")
        self.assertEqual(d.code, errors.SERVER_ERROR)


if __name__ == "__main__":
    unittest.main()
