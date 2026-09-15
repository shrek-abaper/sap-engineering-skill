"""Security regressions: redaction in logs and in HTTP error tracebacks."""
import base64
import io
import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_PATH = Path(__file__).resolve().parents[1] / "skills" / "sap-adt-cli" / "scripts"
sys.path.insert(0, str(SCRIPTS_PATH))

import requests  # noqa: E402

from lib import client  # noqa: E402
from lib import log_redaction  # noqa: E402
from lib.config import SapConfig  # noqa: E402

SECRET = "SUPER-SECRET-PW-9001"
BASIC_TOKEN = base64.b64encode(f"DEVUSER:{SECRET}".encode()).decode()


def make_config():
    return SapConfig(
        url="https://D01.example.com:8000",
        username="DEVUSER",
        password=SECRET,
        client="100",
    )


class RedactionTests(unittest.TestCase):
    def test_basic_auth_header_is_redacted(self):
        text = f"GET / HTTP/1.1\r\nAuthorization: Basic {BASIC_TOKEN}\r\n"
        out = log_redaction.redact(text)
        self.assertNotIn(BASIC_TOKEN, out)
        self.assertNotIn(SECRET, out)
        self.assertIn("Basic ***", out)

    def test_bearer_and_keyword_secrets_are_redacted(self):
        self.assertNotIn("abc.def.ghi", log_redaction.redact("Authorization: Bearer abc.def.ghi"))
        out = log_redaction.redact("login password=hunter2 and token: zzz, done")
        self.assertNotIn("hunter2", out)
        self.assertNotIn("zzz", out)

    def test_redaction_leaves_benign_text_intact(self):
        text = "HTTP 404 for GET https://D01.example.com/sap/bc/adt/programs"
        self.assertEqual(log_redaction.redact(text), text)

    def test_literal_secret_is_scrubbed_even_without_a_keyword(self):
        out = log_redaction.redact(f"echo {SECRET}", secret=SECRET)
        self.assertNotIn(SECRET, out)

    def test_logging_filter_redacts_emitted_records(self):
        stream = io.StringIO()
        logger = logging.getLogger(f"redaction_test_{id(self)}")
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        handler.addFilter(log_redaction.RedactingFilter(secret=SECRET))
        try:
            logger.warning("Authorization: Basic %s", BASIC_TOKEN)
            logger.info("plain literal %s", SECRET)
        finally:
            logger.removeHandler(handler)
        output = stream.getvalue()
        self.assertNotIn(BASIC_TOKEN, output)
        self.assertNotIn(SECRET, output)
        self.assertIn("Basic ***", output)


class HttpErrorLeakTests(unittest.TestCase):
    def _http_401(self):
        req = requests.PreparedRequest()
        req.headers = requests.structures.CaseInsensitiveDict(
            {"Authorization": f"Basic {BASIC_TOKEN}"}
        )
        resp = requests.models.Response()
        resp.status_code = 401
        resp._content = (
            b"<html><body>401 Unauthorized - Basic " + BASIC_TOKEN.encode() + b"</body></html>"
        )
        resp.request = req
        return requests.HTTPError("401 Client Error", response=resp)

    def test_401_traceback_contains_neither_password_nor_basic_token(self):
        config = make_config()
        with self.assertRaises(client.AdtHttpError) as ctx:
            with patch.object(client, "get_config", return_value=config), \
                 patch.object(client, "_get_session") as get_session:
                get_session.return_value.request.side_effect = self._http_401()
                client.make_adt_request(f"{config.url}/sap/bc/adt/x")
        tb = "".join(
            __import__("traceback").format_exception(type(ctx.exception), ctx.exception, ctx.exception.__traceback__)
        )
        self.assertNotIn(SECRET, tb)
        self.assertNotIn(BASIC_TOKEN, tb)
        self.assertIn("401", str(ctx.exception))

    def test_connection_error_traceback_does_not_leak_password(self):
        config = make_config()
        conn_err = requests.ConnectionError(f"boom {SECRET}")
        with self.assertRaises(client.AdtHttpError) as ctx:
            with patch.object(client, "get_config", return_value=config), \
                 patch.object(client, "_get_session") as get_session:
                get_session.return_value.request.side_effect = conn_err
                client.make_adt_request(f"{config.url}/sap/bc/adt/x")
        tb = "".join(
            __import__("traceback").format_exception(type(ctx.exception), ctx.exception, ctx.exception.__traceback__)
        )
        self.assertNotIn(SECRET, tb)


class VerboseCliTests(unittest.TestCase):
    def test_verbose_flag_configures_redacted_logging_without_error(self):
        sys.path.insert(0, str(SCRIPTS_PATH))
        from test_sap_adt_cli_config import load_cli_module
        from click.testing import CliRunner

        cli, _cfg = load_cli_module()
        result = CliRunner().invoke(cli.cli, ["--verbose", "credentials", "doctor"])
        self.assertEqual(result.exit_code, 0, result.output)


if __name__ == "__main__":
    unittest.main()
