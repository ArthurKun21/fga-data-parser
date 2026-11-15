#!/usr/bin/env python3
"""Merge translation fills into the fgo-translate overwrite work queue.

Reads a fills JSON — the strict-JSON format the skill's translation batches
return: {"<jp text>": {"na": "...", ...}} — and fills only regions that are
currently null, writing the file back byte-compatible with the pipeline's own
writer (2-space indent, newline-terminated; top-level order preserved — the
next fgo-translate run re-sorts). Existing values are never replaced: a
same-value fill is an idempotent no-op, a different value is a reported
conflict, and a fill for a key or region the queue does not track is rejected.

Standard library only — no dependencies to install.

Usage (from the repo root):

    uv run .agents/skills/machine-translations/scripts/apply.py --fills fills.json \
        [--file PATH] [--dry-run] [--backup PATH]

--backup copies the pre-apply bytes to PATH; pass it to validate.py --baseline
afterwards. --dry-run reports the same summary without writing anything.

Exit codes: 0 every fill applied or already present; 1 some fills rejected or
conflicted (listed in the JSON summary); 2 fills input missing or malformed;
3 structurally invalid work queue.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REGIONS = ("cn", "tw", "na", "kr")


def json_bytes(data: Any) -> bytes:
    """UTF-8 JSON bytes with 2-space indent and trailing newline.

    Matches the pipeline writer's bytes (orjson OPT_INDENT_2 |
    OPT_APPEND_NEWLINE) for this file's data shape — plain JSON objects of
    str/None. validate.py asserts that parity through the repo's real writer.
    """
    return json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"


def load_table(path: Path) -> dict[str, dict[str, str | None]]:
    """Load the overwrite table with the repo loader's rules.

    Mirrors fgo_translate.pipeline.load_overwrite_translations so the helper
    scripts gate the file like the build does; validate.py runs the real
    loader as the authoritative check. Used here as a structural gate before
    mutating the file.
    """
    raw = json.loads(path.read_bytes())
    if not isinstance(raw, dict) or not isinstance(raw.get("translations"), dict):
        raise ValueError(f"{path}: expected a {{'translations': {{...}}}} object")
    table: dict[str, dict[str, str | None]] = {}
    for jp_text, entry in raw["translations"].items():
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: entry {jp_text!r} must be an object")
        regions: dict[str, str | None] = {}
        for region, value in entry.items():
            if region == "jp":
                if not isinstance(value, str) or not value:
                    raise ValueError(f"{path}: entry {jp_text!r} jp must be a non-empty string")
                continue
            if region not in REGIONS:
                raise ValueError(f"{path}: entry {jp_text!r} has unknown region {region!r}")
            if value is not None and (not isinstance(value, str) or not value):
                raise ValueError(
                    f"{path}: entry {jp_text!r} region {region!r} must be null "
                    "or a non-empty string"
                )
            regions[region] = value
        table[jp_text] = regions
    return table


def apply_fills(
    translations: dict[str, dict[str, str | None]],
    fills: dict[str, dict[str, str]],
) -> dict[str, object]:
    """Fill null regions in place; return the summary of what happened.

    Only in-memory state changes; the caller decides whether to persist.
    Fills for regions absent from an entry are rejected — an entry tracks only
    the regions missing from the build, so such a region is not pending.
    """
    applied = {region: 0 for region in REGIONS}
    already_filled = 0
    conflicts: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []
    touched: set[str] = set()

    for jp_text, fill in fills.items():
        entry = translations.get(jp_text)
        if entry is None:
            rejected.append(
                {
                    "key": jp_text,
                    "region": "",
                    "reason": "unknown key (not in the work queue)",
                }
            )
            continue
        for region, value in fill.items():
            if region not in REGIONS:
                rejected.append(
                    {
                        "key": jp_text,
                        "region": region,
                        "reason": "unknown region (expected cn/tw/na/kr)",
                    }
                )
            elif not isinstance(value, str) or not value:
                rejected.append(
                    {
                        "key": jp_text,
                        "region": region,
                        "reason": "fill must be a non-empty string",
                    }
                )
            elif region not in entry:
                rejected.append(
                    {
                        "key": jp_text,
                        "region": region,
                        "reason": "region not pending for this key",
                    }
                )
            else:
                current = entry[region]
                if current is None:
                    entry[region] = value
                    applied[region] += 1
                    touched.add(jp_text)
                elif current == value:
                    already_filled += 1
                else:
                    conflicts.append(
                        {
                            "key": jp_text,
                            "region": region,
                            "existing": current,
                            "provided": value,
                        }
                    )

    # Rebuild touched entries so their region keys stay in the canonical
    # cn/tw/na/kr order the pipeline writes — inserting a filled region at the
    # dict tail would surface as diff noise on the next fgo-translate run.
    # Legacy "jp" echoes (tolerated and ignored by the loader) keep their
    # position at the tail; the next build rewrites them away.
    for jp_text in touched:
        entry = translations[jp_text]
        rebuilt = {region: entry[region] for region in REGIONS if region in entry}
        for key, value in entry.items():
            if key not in rebuilt:
                rebuilt[key] = value
        translations[jp_text] = rebuilt

    return {
        "applied": sum(applied.values()),
        "per_region": applied,
        "already_filled": already_filled,
        "conflicts": conflicts,
        "rejected": rejected,
    }


def count_nulls(translations: dict[str, dict[str, str | None]]) -> dict[str, int]:
    """Null region counts over the raw entries (legacy jp keys are not regions)."""
    nulls = {region: 0 for region in REGIONS}
    for entry in translations.values():
        for region, value in entry.items():
            if region in nulls and value is None:
                nulls[region] += 1
    return nulls


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge translation fills into the fgo-translate overwrite work queue.",
    )
    parser.add_argument(
        "--fills",
        required=True,
        help='fills JSON file ("-" for stdin): {"<jp text>": {"<region>": "..."}}',
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=Path("overwrite_translations.json"),
        help="path to the overwrite work queue (default: ./overwrite_translations.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report the would-be summary without writing anything",
    )
    parser.add_argument(
        "--backup",
        type=Path,
        metavar="PATH",
        help="copy the pre-apply bytes to PATH (use as validate.py --baseline)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        fills_bytes = (
            sys.stdin.buffer.read() if args.fills == "-" else Path(args.fills).read_bytes()
        )
    except OSError as error:
        print(f"apply: cannot read fills {args.fills}: {error}", file=sys.stderr)
        return 2
    try:
        fills = json.loads(fills_bytes)
    except ValueError as error:  # json.JSONDecodeError subclasses ValueError
        print(f"apply: fills is not valid JSON: {error}", file=sys.stderr)
        return 2
    if not isinstance(fills, dict) or not all(isinstance(fill, dict) for fill in fills.values()):
        print('apply: fills must be {"<jp text>": {"<region>": "..."}} objects', file=sys.stderr)
        return 2

    try:
        load_table(args.file)  # structural gate: the same rules the build's loader enforces
    except (OSError, ValueError) as error:
        print(f"apply: unusable work queue {args.file}: {error}", file=sys.stderr)
        return 3

    raw_bytes = args.file.read_bytes()
    raw = json.loads(raw_bytes)
    translations = raw["translations"]
    result = apply_fills(translations, fills)

    nulls = count_nulls(translations)
    summary: dict[str, object] = {
        "file": str(args.file),
        "dry_run": args.dry_run,
        **result,
        "nulls": nulls,
        "total_nulls": sum(nulls.values()),
    }

    if not args.dry_run and result["applied"]:
        try:
            if args.backup is not None:
                args.backup.parent.mkdir(parents=True, exist_ok=True)
                args.backup.write_bytes(raw_bytes)
                summary["backup"] = str(args.backup)
            args.file.write_bytes(json_bytes(raw))
        except OSError as error:
            print(f"apply: cannot write {args.file}: {error}", file=sys.stderr)
            return 2

    sys.stdout.buffer.write(json_bytes(summary))
    if result["rejected"] or result["conflicts"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
