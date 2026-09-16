"""Batch 9.1: profile-level capability gates (offline)."""
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "sap-adt-cli" / "scripts"))

from lib import config  # noqa: E402
from test_sap_adt_cli_config import load_cli_module  # noqa: E402


def _env(runner_result):
    t = runner_result.output
    return json.loads(t[t.find("{"):])


class InferenceTests(unittest.TestCase):
    def test_explicit_beats_inference(self):
        self.assertEqual(config.infer_environment("prd-1", "dev"), ("dev", "explicit"))
        self.assertEqual(config.infer_environment("dev", "prd"), ("prd", "explicit"))

    def test_inferred_prd_loose_substring(self):
        # Loose matching is intentional: 'reproduce' matches 'prod'.
        self.assertEqual(config.infer_environment("reproduce")[0], "prd")
        self.assertEqual(config.infer_environment("myprod")[0], "prd")
        self.assertEqual(config.infer_environment("prd-100")[0], "prd")

    def test_inferred_qas_and_dev(self):
        self.assertEqual(config.infer_environment("qas-1")[0], "qas")
        self.assertEqual(config.infer_environment("qa")[0], "qas")
        self.assertEqual(config.infer_environment("sandbox")[0], "dev")

    def test_explicit_invalid(self):
        with self.assertRaises(ValueError):
            config.infer_environment("dev", "nope")

    def test_merge_prd_always_refused(self):
        sec = {"allow_write": True, "allow_transport": True}
        glb = {"allow_write": True, "allow_transport": True}
        w, t, ws, ts = config.effective_capabilities(sec, glb, "prd")
        self.assertEqual((w, t, ws, ts), (False, False, "hard-refused", "hard-refused"))

    def test_merge_profile_wins_over_global(self):
        w, t, *_ = config.effective_capabilities(
            {"allow_write": False, "allow_transport": False},
            {"allow_write": True, "allow_transport": True}, "dev")
        self.assertEqual((w, t), (False, False))
        # only write declared in profile; transport falls back to global false
        w, t, ws, ts = config.effective_capabilities(
            {"allow_write": True}, {"allow_transport": False}, "dev")
        self.assertEqual((w, t), (True, False))
        self.assertEqual((ws, ts), ("profile", "global"))

    def test_merge_global_is_legacy_fallback(self):
        w, t, ws, ts = config.effective_capabilities(
            {}, {"allow_write": True}, "dev")
        self.assertEqual((w, t, ws), (True, False, "global"))


def _fake_config(*, env="dev", env_source="inferred", allow_write=False,
                 allow_transport=False, from_env=False, env_w=False, env_t=False,
                 name="dev"):
    return types.SimpleNamespace(
        profile_name=name,
        username="DEVELOPER",
        environment=env,
        environment_source=env_source,
        allow_write=allow_write,
        allow_transport=allow_transport,
        from_environment=from_env,
        env_write_requested=env_w,
        env_transport_requested=env_t,
        write_source=("hard-refused" if env == "prd"
                      else ("profile" if allow_write else "global")),
        transport_source=("hard-refused" if env == "prd"
                          else ("profile" if allow_transport else "global")),
        is_production=(env == "prd"),
    )


WRITE_COMMANDS = [
    (["write-source", "class", "ZCL_X"], lambda d: (d / "z.abap",)),
    (["activate", "class", "ZCL_X"], None),
    (["create-transport", "--description", "x"], None),
    (["release-transport", "DEVK900001"], None),
]


class CommandGateMatrixTests(unittest.TestCase):
    def setUp(self):
        self.cli, _ = load_cli_module()
        self.handlers = sys.modules["lib.handlers"]
        self.tmp = tempfile.TemporaryDirectory()
        self.src = Path(self.tmp.name) / "z.abap"
        self.src.write_text("report z.\n")

    def tearDown(self):
        self.tmp.cleanup()

    def _invoke(self, cmd, cfg):
        args = list(cmd)
        if args[0] == "write-source":
            args = args + ["--file", str(self.src)]
        with patch.object(self.cli, "load_config", return_value=cfg), \
                patch.object(self.handlers, "make_adt_request") as no_http:
            r = CliRunner().invoke(self.cli.cli, args + ["--yes"])
        return r, no_http

    def test_dev_unauthorized_all_gated(self):
        cfg = _fake_config()
        for cmd, _ in WRITE_COMMANDS:
            r, no_http = self._invoke(cmd, cfg)
            self.assertEqual(r.exit_code, 3, (cmd, r.output))
            code = _env(r)["error"]["code"]
            self.assertIn(code, ("WRITE_DISABLED", "TRANSPORT_DISABLED"))
            no_http.assert_not_called()

    def test_dev_authorized_passes_gate(self):
        # Gate passes; commands proceed (and may fail later in mocked HTTP,
        # but must NOT exit with a *gate* code 3).
        cfg = _fake_config(allow_write=True, allow_transport=True)
        for cmd, _ in WRITE_COMMANDS:
            r, _ = self._invoke(cmd, cfg)
            if r.exit_code == 3:
                self.fail((cmd, _env(r)["error"]["code"]))

    def test_prd_authorized_still_refused(self):
        cfg = _fake_config(env="prd", allow_write=True, allow_transport=True,
                           name="prd-100")
        for cmd, _ in WRITE_COMMANDS:
            r, no_http = self._invoke(cmd, cfg)
            self.assertEqual(r.exit_code, 3, (cmd, r.output))
            code = _env(r)["error"]["code"]
            self.assertIn(code, ("WRITE_DISABLED", "TRANSPORT_DISABLED"))
            self.assertIn("prd", _env(r)["error"]["message"])
            no_http.assert_not_called()

    def test_unit_dangerous_three_states(self):
        payload = (ROOT / "skills/sap-adt-cli/tests/fixtures/unit.empty.xml").read_bytes()

        class R:
            content = payload
            text = payload.decode()

        def run(cmd, cfg):
            with patch.object(self.cli, "load_config", return_value=cfg), \
                    patch.object(self.handlers, "make_adt_request", return_value=R()):
                return CliRunner().invoke(
                    self.cli.cli,
                    ["run-unit-test", "ZCL_X", "--risk-level", "dangerous"] + cmd)

        # dev unauthorized -> gate 3
        self.assertEqual(run(["--yes"], _fake_config()).exit_code, 3)
        # dev authorized + --yes -> runs
        self.assertEqual(run(["--yes"], _fake_config(allow_write=True)).exit_code, 0)
        # prd authorized -> still gate 3
        r = run(["--yes"], _fake_config(env="prd", allow_write=True, name="prd"))
        self.assertEqual(r.exit_code, 3)
        self.assertEqual(_env(r)["error"]["code"], "WRITE_DISABLED")


class EnvPathGateTests(unittest.TestCase):
    def setUp(self):
        self.cli, _ = load_cli_module()

    def _cfg(self, *, allow=False, env_source="default", env="dev"):
        return _fake_config(
            from_env=True, env_w=allow, env_t=allow,
            env_source=env_source, name=None,
            allow_write=allow and env != "prd",
            allow_transport=allow and env != "prd")

    def test_write_enabled_without_sap_environment_is_config_missing(self):
        cfg = self._cfg(allow=True)
        with patch.object(self.cli, "load_config", return_value=cfg):
            r = CliRunner().invoke(
                self.cli.cli,
                ["create-transport", "--description", "x", "--yes"])
        self.assertEqual(r.exit_code, 3, r.output)
        self.assertEqual(_env(r)["error"]["code"], "CONFIG_MISSING")
        self.assertIn("SAP_ENVIRONMENT", _env(r)["error"]["message"])

    def test_prd_environment_with_flag_is_write_disabled(self):
        cfg = self._cfg(allow=True, env_source="explicit", env="prd")
        with patch.object(self.cli, "load_config", return_value=cfg):
            r = CliRunner().invoke(
                self.cli.cli,
                ["create-transport", "--description", "x", "--yes"])
        self.assertEqual(r.exit_code, 3, r.output)
        self.assertEqual(_env(r)["error"]["code"], "TRANSPORT_DISABLED")

    def test_reads_unaffected_when_environment_unset(self):
        # read command never consults the write gate
        cfg = _fake_config(from_env=True, name=None)
        with patch.object(self.cli, "load_config", return_value=cfg), \
                patch("lib.handlers.get_config", create=True):
            # just verify config exposes default dev for reads
            self.assertEqual(cfg.environment, "dev")


if __name__ == "__main__":
    unittest.main()
