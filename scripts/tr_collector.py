#!/usr/bin/env python3
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

_COLLECTOR_VERSION = "1.0.0"


def _ensure_deps():
    deps = [
        ("click", "click>=8.1.0"),
        ("requests", "requests>=2.31.0"),
        ("urllib3", "urllib3>=2.0.0"),
    ]
    missing = [spec for mod, spec in deps if not importlib.util.find_spec(mod)]
    if not missing:
        return
    print(f"[setup] Installing: {', '.join(missing)}", file=sys.stderr)
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet"] + missing, check=True)
    print("[setup] Done.", file=sys.stderr)


_ensure_deps()

sys.path.insert(0, _SCRIPTS_DIR)

import click
from lib.config import run_configure_wizard, get_config
from lib import handlers


@click.group()
def cli():
    pass


@cli.command()
def configure():
    run_configure_wizard()


@cli.command()
def ping():
    result = handlers.ping()
    if result.is_error:
        click.echo(result.text, err=True)
        sys.exit(1)
    click.echo(result.text)


@cli.command()
@click.argument("tr_id")
@click.option("--output-dir", "-o", default=None, help="Output directory (default: ./review_package/<TR_ID>/)")
@click.option("--verbose", "-v", is_flag=True, help="Show each object fetch result")
def collect(tr_id: str, output_dir: str, verbose: bool):
    config = get_config()

    out_path = Path(output_dir) if output_dir else Path("review_package") / tr_id
    out_path.mkdir(parents=True, exist_ok=True)
    sources_path = out_path / "sources"
    sources_path.mkdir(exist_ok=True)

    click.echo(f"Collecting TR {tr_id} from {config.url} ...")

    raw = handlers.get_transport_objects(tr_id)
    if raw.is_error:
        click.echo(f"ERROR fetching object list: {raw.text}", err=True)
        sys.exit(1)

    objects = handlers.parse_transport_objects(raw.text)
    if not objects:
        click.echo("WARNING: TR object list is empty or could not be parsed.", err=True)

    click.echo(f"Found {len(objects)} object(s). Fetching source code ...")

    enriched = []
    errors = 0

    for obj in objects:
        pgmid = obj["pgmid"]
        obj_type = obj["object_type"]
        obj_name = obj["object_name"]

        result = handlers.fetch_source_for_object(pgmid, obj_type, obj_name)

        safe_name = f"{obj_type}_{obj_name}".replace("/", "_").replace("\\", "_")
        source_file = f"sources/{safe_name}.abap"

        if result.is_error:
            errors += 1
            if verbose:
                click.echo(f"  FAIL  {obj_type}/{obj_name}: {result.text}", err=True)
            enriched.append({**obj, "source_fetched": False, "source_file": None, "fetch_error": result.text})
        elif result.text.startswith("[NO_SOURCE]") or result.text.startswith("[UNSUPPORTED]"):
            if verbose:
                click.echo(f"  SKIP  {obj_type}/{obj_name}: {result.text.split(']', 1)[-1].strip()}")
            enriched.append({**obj, "source_fetched": False, "source_file": None, "fetch_error": result.text})
        else:
            (sources_path / f"{safe_name}.abap").write_text(result.text, encoding="utf-8")
            if verbose:
                click.echo(f"  OK    {obj_type}/{obj_name} → {source_file}")
            enriched.append({**obj, "source_fetched": True, "source_file": source_file, "fetch_error": None})

    fetched = sum(1 for o in enriched if o["source_fetched"])

    manifest = {
        "meta": {
            "tr_id": tr_id,
            "sap_url": config.url,
            "sap_client": config.client,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "collector_version": _COLLECTOR_VERSION,
        },
        "objects": enriched,
        "summary": {
            "total_objects": len(enriched),
            "sources_fetched": fetched,
            "fetch_errors": errors,
        },
    }

    manifest_path = out_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    click.echo(f"\nDone. {fetched}/{len(enriched)} sources fetched. {errors} error(s).")
    click.echo(f"Review Package: {out_path.resolve()}")
    click.echo(f"Manifest:       {manifest_path.resolve()}")


if __name__ == "__main__":
    cli()
