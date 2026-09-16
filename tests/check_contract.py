#!/usr/bin/env python3
"""Contract self-consistency check (CI): SKILL.md vs. the implementation.

Verifies four invariants:

1. Every error code in SKILL.md is exactly lib.errors.ALL_CODES.
2. Every command in the SKILL.md index is a command actually registered
   with Click, and vice versa.
3. The kinds in the SKILL.md contract table match the implemented parsers.
4. The kind declared per command in the index matches the kind its handler
   returns (static analysis; no HTTP).

Exits 1 with a diff on any drift. Run: python3 tests/check_contract.py
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "sap-adt-cli" / "SKILL.md"
SCRIPTS = ROOT / "skills" / "sap-adt-cli" / "scripts"

sys.path.insert(0, str(SCRIPTS))

from lib import errors  # noqa: E402
from lib.parsers import __all__ as parser_modules  # noqa: E402

failures: list[str] = []


def section(text: str, heading: str) -> str:
    start = text.index(heading)
    rest = text[start:]
    m = re.search(r"\n## ", rest[1:])
    return rest[: m.start() + 1] if m else rest


def check(label: str, expected, actual):
    expected, actual = set(expected), set(actual)
    if expected != actual:
        failures.append(
            f"[{label}] drift\n  missing in SKILL: {sorted(actual - expected)}\n"
            f"  missing in code:  {sorted(expected - actual)}"
        )


# --------------------------------- 1. codes --------------------------------

skill = SKILL.read_text(encoding="utf-8")
code_section = section(skill, "## Error codes and exit tiers")
skill_codes = set(re.findall(r"`([A-Z][A-Z_]{3,})`", code_section))
check("error-codes", skill_codes, errors.ALL_CODES)

# ------------------------- 2. registered commands --------------------------

import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("sap_adt_cli", SCRIPTS / "sap_adt_cli.py")
cli_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli_mod)

registered: set[str] = set()
for name, cmd in cli_mod.cli.commands.items():
    if isinstance(cmd, type(cli_mod.cli)):  # click Group
        for sub in cmd.commands:
            registered.add(f"{name} {sub}")
    else:
        registered.add(name)

idx = section(skill, "## Command index")


def cells_of(line: str) -> list[str]:
    # respect Markdown-escaped pipes ("D\|R")
    parts = re.split(r"(?<!\\)\|", line)[1:-1]
    return [p.replace("\\|", "|").strip() for p in parts]


def expand_command_cell(cell: str) -> list[str]:
    cell = re.sub(r"\s*\[.*?\]\s*", "", cell.replace("`", ""))
    m_multi = re.match(r"(\w+)\s+([a-z|]+)$", cell.strip())
    if m_multi:
        group, alts = m_multi.groups()
        return [f"{group} {a}" for a in alts.split("|")]
    # "get-program / -class / -function --group G / ...": later tokens are
    # shorthand ("-class" -> get-class, prefix taken from the first token).
    out: list[str] = []
    prefix = ""
    for i, tok in enumerate(cell.split("/")):
        tok = tok.strip()
        if not tok:
            continue
        word = tok.split()[0]
        if i == 0:
            if "-" in word:
                prefix = word.split("-")[0] + "-"
            out.append(word)
        elif word.startswith("-"):
            out.append(prefix + word.lstrip("-"))
        else:
            out.append(word)
    return [w for w in out if re.fullmatch(r"[a-z][a-z0-9-]+", w)]


index_commands: set[str] = set()
for line in idx.splitlines():
    if line.startswith("| `"):
        index_commands.update(expand_command_cell(cells_of(line)[0]))

check("commands", index_commands, registered)

# --------------------------------- 3. kinds ---------------------------------

kind_section = section(skill, "## Output contract")
skill_kinds = set(re.findall(
    r"`(source|fields|objects|rows|records|findings|scalar|capabilities)`",
    kind_section))
implemented = set(parser_modules)
check("kinds", skill_kinds, implemented)

# ------------------ 4. command -> handler kind consistency ------------------

# Parse handlers.py: handler function -> kind literal it emits.
handler_src = (SCRIPTS / "lib" / "handlers.py").read_text(encoding="utf-8")
handler_tree = ast.parse(handler_src)

# Any function emitting a kind directly (_structured("kind", ...)).
emit_kind: dict[str, str] = {}
for node in ast.walk(handler_tree):
    if not isinstance(node, ast.FunctionDef):
        continue
    for n in ast.walk(node):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "_structured" and n.args
                and isinstance(n.args[0], ast.Constant)
                and isinstance(n.args[0].value, str)):
            emit_kind[node.name] = n.args[0].value
            break

# helpers like _source_result/_fields_result call _structured indirectly via
# being the one returning it; the loop above already captures them.

# Parse sap_adt_cli.py: command -> handler functions it calls.
cli_src = (SCRIPTS / "sap_adt_cli.py").read_text(encoding="utf-8")
cli_tree = ast.parse(cli_src)
command_handler: dict[str, set[str]] = {}
for node in ast.walk(cli_tree):
    if not isinstance(node, ast.FunctionDef):
        continue
    command_name = None
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        # @cli.command("x") / @profile_group.command("list")
        if isinstance(dec, ast.Call) and dec.args and isinstance(dec.args[0], ast.Constant):
            attr = target.attr if isinstance(target, ast.Attribute) else None
            if attr == "command":
                if isinstance(target.value, ast.Name) and target.value.id == "cli":
                    command_name = dec.args[0].value
                else:
                    grp = target.value.attr if isinstance(target.value, ast.Attribute) else None
                    command_name = f"{grp} {dec.args[0].value}" if grp else dec.args[0].value
    if not command_name:
        continue
    funcs = set()
    for n in ast.walk(node):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "handlers"):
            funcs.add(n.func.attr)
    if funcs:
        command_handler[command_name] = funcs


def actual_kinds(handler_names: set[str]) -> set[str]:
    """Resolve direct kinds and kinds via private helpers (_source_result)."""
    out: set[str] = set()
    by_name = {n.name: n for n in ast.walk(handler_tree) if isinstance(n, ast.FunctionDef)}
    for h in handler_names:
        if h in emit_kind:
            out.add(emit_kind[h])
            continue
        fn = by_name.get(h)
        if fn is None:
            continue
        for n in ast.walk(fn):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in emit_kind:
                out.add(emit_kind[n.func.id])
    return out


# Declared kinds from the index table ("| cmd ... | one-liner | kind |").
declared: dict[str, str] = {}
for line in idx.splitlines():
    if not line.startswith("| `"):
        continue
    cells = cells_of(line)
    if len(cells) < 3:
        continue
    kind = cells[2].strip("` ")
    if not kind or kind in ("—", "-", "gated"):
        continue
    for c in expand_command_cell(cells[0]):
        declared[c] = kind

for cmd, kind in sorted(declared.items()):
    handlers = command_handler.get(cmd)
    if not handlers:
        failures.append(f"[command-kind] {cmd}: not wired to any handler")
        continue
    got = actual_kinds(handlers)
    if kind not in got:
        failures.append(
            f"[command-kind] {cmd}: SKILL declares {kind}, handler(s) "
            f"{sorted(handlers)} emit {sorted(got) or 'no structured kind'}"
        )

if failures:
    print("Contract drift detected:\n")
    for f in failures:
        print("-", f, "\n")
    sys.exit(1)

print("contract OK:")
print(f"  {len(errors.ALL_CODES)} error codes consistent")
print(f"  {len(registered)} commands consistent")
print(f"  {len(implemented)} kinds ({', '.join(sorted(implemented))})")
print(f"  {len(declared)} command->kind declarations consistent")
