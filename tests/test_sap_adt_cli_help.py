"""Task-oriented root help preserves Click command paths and nested help."""
import re
import unittest
from unittest.mock import patch

import click
from click.testing import CliRunner

from test_sap_adt_cli_config import load_cli_module


class HelpTests(unittest.TestCase):
    def setUp(self):
        self.module, self.config = load_cli_module()
        self.runner = CliRunner()

    def help_result(self, args=None, **kwargs):
        with patch.object(self.module, "load_config", side_effect=AssertionError("config read")):
            result = self.runner.invoke(self.module.cli, args or ["--help"], **kwargs)
        self.assertEqual(result.exit_code, 0, result.output)
        return result

    def sections(self, **kwargs):
        text = self.help_result(**kwargs).output
        headings = list(re.finditer(r"^([A-Z][^\n]+):\n", text, re.MULTILINE))
        return {
            match.group(1): text[match.end():headings[i + 1].start()
                                if i + 1 < len(headings) else len(text)]
            for i, match in enumerate(headings) if match.group(1) != "Options"
        }

    def command_names(self, section):
        return re.findall(r"^  ([a-z][a-z0-9-]*)\s+", section, re.MULTILINE)

    def test_setup_commands_are_first_in_workflow_order(self):
        sections = self.sections()
        self.assertEqual(list(sections), [
            "Setup and maintenance", "Find objects", "Read and change source",
            "Inspect data and types", "Test and diagnose",
            "Compare source versions", "Transport requests",
        ])
        self.assertEqual(self.command_names(sections["Setup and maintenance"]),
                         ["configure", "profile", "credentials", "status",
                          "discovery", "update"])
        self.assertEqual(self.command_names(sections["Test and diagnose"]),
                         ["syntax-check", "run-atc", "run-unit-test", "list-feeds",
                          "query-feed", "get-dump", "debug"])
        self.assertEqual(self.command_names(sections["Compare source versions"]),
                         ["get-versions", "get-version-source", "diff-versions"])
        self.assertEqual(self.command_names(sections["Transport requests"]),
                         ["list-transports", "get-transport", "transport",
                          "create-transport", "release-transport"])

    def test_every_visible_command_has_one_registered_group_and_appears_once(self):
        sections = self.sections()
        names = [name for section in sections.values()
                 for name in self.command_names(section)]
        expected = {name for name, command in self.module.cli.commands.items()
                    if not command.hidden}
        self.assertEqual(set(names), expected)
        self.assertEqual(len(names), len(expected))
        for name in expected:
            command = self.module.cli.commands[name]
            with self.subTest(command=name):
                order, title = command.help_group
                self.assertIsInstance(order, int)
                self.assertIsInstance(command.help_order, int)
                self.assertIn(name, self.command_names(sections[title]))
                self.assertTrue(command.short_help)

    def test_source_reading_is_alphabetical_then_writing_and_activation(self):
        names = self.command_names(self.sections()["Read and change source"])
        self.assertEqual(names[-2:], ["write-source", "activate"])
        self.assertEqual(names[:-2], sorted(names[:-2]))
        self.assertIn("get-source", names[:-2])
        self.assertIn("get-function-group", names[:-2])
        self.assertNotIn("get-table", names)
        self.assertIn("get-table", self.command_names(
            self.sections()["Inspect data and types"]))

    def test_future_commands_are_not_dropped_and_hidden_commands_stay_hidden(self):
        for name in ("zzz-inspect", "aaa-inspect"):
            self.module.cli.command(
                name, help_group=self.module._DATA_HELP,
                short_help="Inspect more data.")(lambda: None)
        self.module.cli.add_command(click.Command("hidden-command", hidden=True))
        sections = self.sections()
        names = self.command_names(sections["Inspect data and types"])
        self.assertEqual(names[0], "aaa-inspect")
        self.assertEqual(names[-2:], ["zzz-inspect", "run-sql"])
        self.assertNotIn("hidden-command", self.help_result().output)

    def test_nested_groups_keep_their_existing_help(self):
        for group in ("profile", "credentials", "transport", "debug"):
            with self.subTest(group=group):
                result = self.help_result([group, "--help"])
                self.assertIn("Commands:", result.output)
                for title in self.sections():
                    self.assertNotIn(f"{title}:", result.output)

    def test_narrow_no_color_help_wraps_without_losing_commands_or_risks(self):
        expected = {name for name, command in self.module.cli.commands.items()
                    if not command.hidden}
        for width in (40, 60, 100):
            with self.subTest(width=width):
                result = self.help_result(
                    terminal_width=width, color=False, env={"NO_COLOR": "1"})
                self.assertNotIn("\x1b[", result.output)
                sections = self.sections(
                    terminal_width=width, color=False, env={"NO_COLOR": "1"})
                names = [name for body in sections.values()
                         for name in self.command_names(body)]
                self.assertEqual(set(names), expected)
                self.assertEqual(len(names), len(expected))
                options = result.output.split("Options:\n", 1)[1].split(
                    "Setup and maintenance:\n", 1)[0]
                for line in options.splitlines():
                    if not line.lstrip().startswith("-"):
                        self.assertLessEqual(len(line), width)
                for body in sections.values():
                    self.assertTrue(all(len(line) <= width
                                        for line in body.splitlines()))
                for warning in ("[WRITE]", "[IRREVERSIBLE]", "[RUNS ABAP]",
                                "[MAY RUN ABAP]", "[SELECT ONLY]", "[LOCAL UPDATE]"):
                    self.assertIn(warning, result.output)

    def test_risk_labels_lead_short_descriptions_and_details_remain_available(self):
        for name, warning in (
            ("write-source", "[WRITE]"), ("activate", "[WRITE]"),
            ("create-transport", "[WRITE]"), ("release-transport", "[IRREVERSIBLE]"),
            ("run-unit-test", "[RUNS ABAP]"), ("debug", "[MAY RUN ABAP]"),
            ("run-sql", "[SELECT ONLY]"), ("update", "[LOCAL UPDATE]"),
        ):
            with self.subTest(command=name):
                self.assertTrue(self.module.cli.commands[name].short_help.startswith(warning))
        for name, detail in (
            ("write-source", "allow_write"),
            ("release-transport", "allow_transport"),
            ("run-unit-test", "--risk-level"),
            ("debug", "allow_debug"),
            ("configure", "Credential resolution"),
        ):
            with self.subTest(command=name):
                self.assertIn(detail, self.help_result([name, "--help"]).output)

    def test_debug_help_explains_independent_permission_and_cleanup(self):
        self.assertIn("allow_debug", self.help_result().output)
        config_help = self.help_result(["configure", "--help"]).output
        self.assertIn("--allow-debug / --no-allow-debug", config_help)
        self.assertIn("independent of writes", config_help)
        debug_help = self.help_result(["debug", "--help"]).output
        self.assertIn("not a read-only", debug_help)
        self.assertIn("status/detach/cleanup", debug_help)


if __name__ == "__main__":
    unittest.main()
