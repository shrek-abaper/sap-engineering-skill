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

# ------------------- 5. docs layout: inward-only, links resolve -------------------
# The skill directory must be distributable on its own: no file inside it
# may reference a path outside it, and every relative Markdown link must
# resolve. SKILL.md additionally never points at the human-facing docs/
# history folder (operational contract stays <= one hop deep).

SKILL_ROOT = ROOT / "skills" / "sap-adt-cli"
SKILL_DOCS = SKILL_ROOT / "docs"
HANDOFF = SKILL_DOCS / "refactor-handoff.md"
SUMMARY = SKILL_DOCS / "refactor-summary.md"
ADT_API = SKILL_ROOT / "references" / "adt_api.md"

_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_MD_TICKET_PATH_RE = re.compile(r"`([^`\n]+?\.md)`")


def _md_reference_targets(text: str):
    for m in _MD_LINK_RE.finditer(text):
        yield m.group(1).strip()
    for m in _MD_TICKET_PATH_RE.finditer(text):
        tok = m.group(1).strip()
        # Bare prose like `x.md` is a same-directory reference; only treat
        # tokens that look like paths.
        if "/" in tok or tok.endswith(".md"):
            yield tok


# README files are monorepo presentation, not the agent contract: they may
# link exactly two repository-root resources (which must still exist).
# Everything else — SKILL.md, references/, docs/, in-skill test docs — must
# resolve inside the skill directory.
_README_ROOT_ALLOWLIST = {"setup-opencode-abap-cli.bat", "LICENSE"}

for md in SKILL_ROOT.rglob("*.md"):
    text = md.read_text(encoding="utf-8")
    is_readme = md.name.lower().startswith("readme")
    for target in _md_reference_targets(text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = target.split("#", 1)[0]
        if not target:
            continue
        resolved = (md.parent / target).resolve()
        try:
            resolved.relative_to(SKILL_ROOT.resolve())
        except ValueError:
            within_repo = True
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                within_repo = False
            allowed = (is_readme
                       and within_repo
                       and Path(target).name in _README_ROOT_ALLOWLIST)
            if not allowed:
                failures.append(
                    f"[docs-layout] {md.relative_to(ROOT)} references "
                    f"outside the skill directory: {target}")
            elif not resolved.exists():
                failures.append(
                    f"[docs-layout] allowlisted root link missing in "
                    f"{md.relative_to(ROOT)}: {target}")
            continue
        if not resolved.exists():
            failures.append(f"[docs-layout] broken link in "
                            f"{md.relative_to(ROOT)}: {target}")

skill_text = SKILL.read_text(encoding="utf-8")
if re.search(r"docs/[A-Za-z0-9_.-]+\.md", skill_text):
    failures.append("[docs-layout] SKILL.md must not link into docs/ "
                    "(operational contract is one hop; move the behavior "
                    "rule into references/ instead)")

# ---------- 6. cross-document numbers: facts, commands, codes, kinds ----------

def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    rest = text[start:]
    m = re.search(r"\n## ", rest[1:])
    return rest[: m.start() + 1] if m else rest


# Protocol fact count: adt_api.md table vs handoff §3 list vs summary list,
# plus the word-number in the two headings.
_NUM_WORDS = {"six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
              "eleven": 11, "twelve": 12, "thirteen": 13}

adt_api_text = ADT_API.read_text(encoding="utf-8")
fact_rows = [int(n) for n in re.findall(
    r"^\|\s*(\d+)\s*\|",
    _section(adt_api_text, "## Verified protocol facts"), re.M)]
n_facts = max(fact_rows)
if sorted(fact_rows) != list(range(1, n_facts + 1)):
    failures.append(f"[cross-docs] adt_api.md fact table not a contiguous 1..N: {fact_rows}")

handoff_text = HANDOFF.read_text(encoding="utf-8")
handoff_facts = [int(n) for n in re.findall(
    r"^(\d+)\. ", _section(handoff_text, "## 3."), re.M)]
summary_text = SUMMARY.read_text(encoding="utf-8")
summary_facts = [int(n) for n in re.findall(
    r"^(\d+)\. \*\*", _section(summary_text, "verified ADT protocol facts"), re.M)]
expected_fact_numbers = list(range(1, n_facts + 1))
if handoff_facts != expected_fact_numbers or summary_facts != expected_fact_numbers:
    failures.append(
        f"[cross-docs] protocol fact list drift (must be a contiguous "
        f"1..{n_facts}): adt_api={fact_rows}, handoff §3={handoff_facts}, "
        f"summary={summary_facts}")

for label, text in (("handoff", handoff_text), ("summary", summary_text)):
    m = re.search(
        r"(?im)^(?:##\s+(?:\d+\.\s*)?)?(\w+)\s+verified (?:ADT )?protocol facts",
        text)
    if m and _NUM_WORDS.get(m.group(1).lower()) != n_facts:
        failures.append(f"[cross-docs] {label} fact heading says "
                        f"{m.group(1)} but table/list has {n_facts}")

# Current totals derived from code must appear verbatim in the canonical
# statements of every doc that states them (historical batch-table rows are
# not matched by these anchored patterns).
n_commands = len(registered)
n_codes = len(errors.ALL_CODES)
n_kinds = len(parser_modules)

if f"All {n_codes} codes" not in skill_text:
    failures.append(f"[cross-docs] SKILL.md missing canonical 'All {n_codes} codes'")
m = re.search(r"(\d+) Click commands, (\d+) parser modules, (\d+) error codes",
              handoff_text)
if not m or tuple(map(int, m.groups())) != (n_commands, n_kinds, n_codes):
    failures.append("[cross-docs] handoff §2 totals must read "
                    f"'{n_commands} Click commands, {n_kinds} parser modules, "
                    f"{n_codes} error codes'")
m = re.search(r"(\d+) codes / (\d+) commands / (\d+) kinds /\s*"
              r"(\d+) command", summary_text)
if not m or tuple(map(int, m.groups())) != (n_codes, n_commands, n_kinds, 21):
    failures.append("[cross-docs] summary CI line must read "
                    f"'{n_codes} codes / {n_commands} commands / {n_kinds} "
                    "kinds / 21 command→kind declarations'")

# Exit-tier table in SKILL.md: every code appears exactly once and the
# tier-1 row lists precisely the codes EXIT_CODE_MAP maps to 1.
tier_section = _section(skill_text, "## Error codes and exit tiers")
tier_codes = set()
tier1 = set()
for line in tier_section.splitlines():
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) >= 3 and re.fullmatch(r"\d", cells[0]):
        codes_here = set(re.findall(r"`([A-Z_]+)`", cells[2]))
        tier_codes |= codes_here
        if cells[0] == "1":
            tier1 = codes_here
expected_tier1 = {c for c, t in errors.EXIT_CODE_MAP.items() if t == 1}
if tier1 != expected_tier1:
    failures.append(f"[cross-docs] tier-1 row {sorted(tier1)} != code map "
                    f"{sorted(expected_tier1)}")
if tier_codes != set(errors.ALL_CODES):
    failures.append("[cross-docs] SKILL tier table code union != ALL_CODES")

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
