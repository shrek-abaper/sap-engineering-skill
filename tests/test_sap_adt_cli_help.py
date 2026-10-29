"""Root help groups local setup above the ADT command list."""
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

    def sections(self):
        with patch.object(self.module, "load_config", side_effect=AssertionError("config read")):
            result = self.runner.invoke(self.module.cli, ["--help"])
        self.assertEqual(result.exit_code, 0, result.output)
        _, commands = result.output.split("Setup and maintenance:", 1)
        return commands.split("ADT commands:", 1)

    def command_names(self, section):
        return re.findall(r"^  ([a-z][a-z0-9-]*)\s+", section, re.MULTILINE)

    def test_setup_commands_are_first_in_workflow_order(self):
        setup, adt = self.sections()
        self.assertEqual(self.command_names(setup),
                         ["configure", "profile", "credentials", "status", "update"])
        self.assertIn("get-program", self.command_names(adt))
        self.assertIn("transport", self.command_names(adt))
        self.assertNotIn("configure", self.command_names(adt))

    def test_every_visible_command_appears_once_and_adt_stays_sorted(self):
        setup, adt = self.sections()
        names = self.command_names(setup) + self.command_names(adt)
        expected = {name for name, command in self.module.cli.commands.items()
                    if not command.hidden}
        self.assertEqual(set(names), expected)
        self.assertEqual(len(names), len(expected))
        self.assertEqual(self.command_names(adt), sorted(self.command_names(adt)))

    def test_future_commands_are_not_dropped_and_hidden_commands_stay_hidden(self):
        self.module.cli.add_command(click.Command("new-adt", help="New ADT capability."))
        self.module.cli.add_command(click.Command("hidden-command", hidden=True))
        _, adt = self.sections()
        self.assertIn("new-adt", self.command_names(adt))
        self.assertNotIn("hidden-command", adt)

    def test_nested_groups_keep_their_existing_help(self):
        for group in ("profile", "credentials", "transport"):
            with self.subTest(group=group):
                result = self.runner.invoke(self.module.cli, [group, "--help"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertIn("Commands:", result.output)
                self.assertNotIn("Setup and maintenance:", result.output)
                self.assertNotIn("ADT commands:", result.output)


if __name__ == "__main__":
    unittest.main()
