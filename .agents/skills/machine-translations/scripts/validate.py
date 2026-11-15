#!/usr/bin/env python3
"""Validate the fgo-translate overwrite work queue (machine-translations skill).

The skill's authoritative gate, running the repo's own pipeline code:

1. `fgo_translate.pipeline.load_overwrite_translations` must accept the file.
2. The bytes must be exactly what the pipeline's writer produces — sorted
   top-level keys, 2-space indent, trailing newline, raw UTF-8 — proved by
   re-serializing the loaded table through the repo's real writer
   (`fga_data_parser.utils.write_data`) and comparing.
3. With --baseline, the only change against the pre-apply snapshot must be
   null -> non-empty-string fills: no added or removed entries or regions, no
   modified values.

The script itself uses only the standard library on top of the repo packages.

Run from the repo root (it imports the project packages):

    uv run .agents/skills/machine-translations/scripts/validate.py \
        [--file PATH] [--baseline PATH]

Prints a JSON verdict on stdout; diagnostics go to stderr. Exit codes:
0 pass; 1 validation failed (issues listed in the verdict); 2 could not run.
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from fga_data_parser.utils import write_data
    from fgo_translate.pipeline import (
        load_overwrite_translations,
        overwrite_translations_to_json,
    )
except ImportError:
    print(
        "validate: cannot import fgo_translate.pipeline — run from the repo root "
        "via `uv run .agents/skills/machine-translations/scripts/validate.py`",
        file=sys.stderr,
    )
    raise SystemExit(2) from None

REGIONS = ("cn", "tw", "na", "kr")


def writer_bytes(data: Any) -> bytes:
    """Serialize through the repo's own writer — the exact bytes the build writes."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "writer.json"
        write_data(path, data)
        return path.read_bytes()


def load_table(path: Path) -> tuple[dict[str, dict[str, str | None]] | None, list[str]]:
    """Run the repo loader; returns (table, issues)."""
    if not path.exists():
        return None, [f"{path}: file not found"]
    try:
        return load_overwrite_translations(path), []
    except (OSError, ValueError) as error:  # orjson.JSONDecodeError subclasses ValueError
        return None, [f"repo loader rejected the file: {error}"]


def check_round_trip(path: Path, table: dict[str, dict[str, str | None]]) -> list[str]:
    """The file must be byte-identical to the pipeline writer's output."""
    raw = path.read_bytes()
    expected = writer_bytes(overwrite_translations_to_json(table))
    if raw == expected:
        return []
    issues = [
        "file is not byte-identical to the pipeline writer's output "
        "(top-level keys sorted, 2-space indent, trailing newline, raw UTF-8)"
    ]
    # Known transitional cause: legacy "jp" echoes are dropped by the loader,
    # so their presence alone breaks the round trip even with intact formatting
    # — say so instead of sending the agent chasing formatting.
    raw_doc = json.loads(raw)
    if isinstance(raw_doc, dict) and isinstance(raw_doc.get("translations"), dict):
        resorted = writer_bytes({"translations": dict(sorted(raw_doc["translations"].items()))})
        if raw == resorted:
            legacy = [
                jp_text
                for jp_text, entry in raw_doc["translations"].items()
                if isinstance(entry, dict) and "jp" in entry
            ]
            if legacy:
                sample = ", ".join(repr(key) for key in legacy[:3])
                issues.append(
                    f"{len(legacy)} legacy jp-echo entries ({sample}...) — the next "
                    "fgo-translate run rewrites them away; no formatting drift detected"
                )
    return issues


def check_baseline(
    baseline: dict[str, dict[str, str | None]],
    current: dict[str, dict[str, str | None]],
) -> tuple[list[str], dict[str, int]]:
    """Against the pre-apply snapshot, only null -> non-empty-string is allowed."""
    issues: list[str] = []
    fills = {region: 0 for region in REGIONS}
    for jp_text in sorted(set(baseline) - set(current)):
        issues.append(f"entry removed: {jp_text!r}")
    for jp_text in sorted(set(current) - set(baseline)):
        issues.append(f"entry added: {jp_text!r}")
    for jp_text in sorted(set(baseline) & set(current)):
        before, after = baseline[jp_text], current[jp_text]
        for region in sorted(set(before) | set(after)):
            if region not in before:
                issues.append(f"region {region!r} appeared in entry {jp_text!r}")
            elif region not in after:
                issues.append(f"region {region!r} disappeared from entry {jp_text!r}")
            elif before[region] is None and isinstance(after[region], str):
                fills[region] += 1
            elif before[region] != after[region]:
                issues.append(
                    f"region {region!r} of entry {jp_text!r} was modified: "
                    f"{before[region]!r} -> {after[region]!r}"
                )
    return issues, fills


def count_nulls(table: dict[str, dict[str, str | None]]) -> dict[str, int]:
    """Null region counts over the loader table (legacy jp keys are dropped)."""
    nulls = {region: 0 for region in REGIONS}
    for entry in table.values():
        for region, value in entry.items():
            if value is None:
                nulls[region] += 1
    return nulls


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the fgo-translate overwrite work queue against the "
            "pipeline's own loader and writer."
        ),
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=Path("overwrite_translations.json"),
        help="path to the overwrite work queue (default: ./overwrite_translations.json)",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        metavar="PATH",
        help=("pre-apply snapshot (from apply.py --backup): only null -> string fills may differ"),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    issues: list[str] = []

    table, loader_issues = load_table(args.file)
    issues.extend(loader_issues)

    round_trip_ok = False
    if table is not None:
        round_trip_issues = check_round_trip(args.file, table)
        round_trip_ok = not round_trip_issues
        issues.extend(round_trip_issues)

    fills_per_region: dict[str, int] | None = None
    baseline_ok: bool | None = None
    if args.baseline is not None:
        baseline_table, baseline_issues = load_table(args.baseline)
        issues.extend(f"baseline: {issue}" for issue in baseline_issues)
        if table is not None and baseline_table is not None:
            baseline_findings, fills_per_region = check_baseline(baseline_table, table)
            baseline_ok = not baseline_findings
            issues.extend(baseline_findings)

    nulls = count_nulls(table) if table is not None else None
    verdict: dict[str, object] = {
        "ok": not issues,
        "file": str(args.file),
        "checks": {
            "loader": table is not None,
            "byte_round_trip": round_trip_ok,
            "baseline": baseline_ok,
        },
        "nulls": nulls,
        "total_nulls": sum(nulls.values()) if nulls is not None else None,
        "issues": issues,
    }
    if fills_per_region is not None:
        verdict["fills_per_region"] = fills_per_region
        verdict["fills_total"] = sum(fills_per_region.values())

    sys.stdout.buffer.write(
        (json.dumps(verdict, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    )
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
