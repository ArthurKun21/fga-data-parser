#!/usr/bin/env python3
"""Census of the fgo-translate overwrite work queue (machine-translations skill).

Reads the overwrite work queue with the same structural rules as
`fgo_translate.pipeline.load_overwrite_translations` and reports entry counts
and pending null regions as JSON on stdout, so the batch plan and the subagent
slices come from one deterministic tool instead of ad-hoc Python.

Standard library only — no dependencies to install.

Usage (from the repo root):

    uv run .agents/skills/machine-translations/scripts/inventory.py \
        [--file PATH] [--slices N [--slices-dir DIR]] [--snapshot PATH]

With --slices, the pending keys — entries holding at least one null region —
are partitioned into N slice files shaped exactly like the fills input of
apply.py: {"<jp text>": {"<region>": null}}.

Exit codes: 0 ok; 2 usage error; 3 structurally invalid file.
"""

import argparse
import json
import shutil
import sys
import tempfile
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
    loader as the authoritative check. Legacy "jp" echoes are tolerated and
    dropped from the result, like the loader does.
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


def pending_work(table: dict[str, dict[str, str | None]]) -> dict[str, dict[str, None]]:
    """Entries with at least one null region, holding only their null regions."""
    return {
        jp_text: {region: None for region, value in entry.items() if value is None}
        for jp_text, entry in table.items()
        if any(value is None for value in entry.values())
    }


def summarize(table: dict[str, dict[str, str | None]]) -> dict[str, int | dict[str, int]]:
    """Counts the census reports: entries and nulls per region.

    entries_all_null counts sourceless keys — all four regions present and
    null, i.e. the build had no coverage for them at all.
    """
    nulls = {region: 0 for region in REGIONS}
    pending = 0
    all_null = 0
    for entry in table.values():
        entry_nulls = [region for region, value in entry.items() if value is None]
        for region in entry_nulls:
            nulls[region] += 1
        if entry_nulls:
            pending += 1
            if len(entry) == len(REGIONS) and all(value is None for value in entry.values()):
                all_null += 1
    return {
        "total_entries": len(table),
        "pending_entries": pending,
        "entries_all_null": all_null,
        "nulls": nulls,
        "total_nulls": sum(nulls.values()),
    }


def write_slices(
    work: dict[str, dict[str, None]], count: int, out_dir: Path
) -> list[dict[str, str | int]]:
    """Partition the pending keys into count slice files of deterministic chunks."""
    out_dir.mkdir(parents=True, exist_ok=True)
    keys = sorted(work)
    size, remainder = divmod(len(keys), count)
    slices: list[dict[str, str | int]] = []
    start = 0
    for index in range(count):
        chunk = keys[start : start + size + (1 if index < remainder else 0)]
        start += len(chunk)
        path = out_dir / f"slice-{index + 1:02d}-of-{count:02d}.json"
        path.write_bytes(json_bytes({key: work[key] for key in chunk}))
        slices.append({"path": str(path), "keys": len(chunk)})
    return slices


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Census of the fgo-translate overwrite work queue.",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=Path("overwrite_translations.json"),
        help="path to the overwrite work queue (default: ./overwrite_translations.json)",
    )
    parser.add_argument(
        "--slices",
        type=int,
        metavar="N",
        help="also write N slice files partitioning the pending keys (subagent fan-out)",
    )
    parser.add_argument(
        "--slices-dir",
        type=Path,
        metavar="DIR",
        help="directory for the slice files (default: a fresh temp directory)",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        metavar="PATH",
        help="also copy the file's raw bytes to PATH (pre-state backup)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        table = load_table(args.file)
    except (OSError, ValueError) as error:  # json.JSONDecodeError subclasses ValueError
        print(f"inventory: cannot read {args.file}: {error}", file=sys.stderr)
        return 3

    summary: dict[str, object] = {"file": str(args.file), **summarize(table)}

    try:
        if args.snapshot is not None:
            args.snapshot.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(args.file, args.snapshot)
            summary["snapshot"] = str(args.snapshot)
        if args.slices is not None:
            if args.slices < 1:
                print("inventory: --slices must be >= 1", file=sys.stderr)
                return 2
            work = pending_work(table)
            out_dir = args.slices_dir or Path(tempfile.mkdtemp(prefix="ot-slices-"))
            count = min(args.slices, len(work))
            summary["slices_dir"] = str(out_dir)
            summary["slices"] = write_slices(work, count, out_dir) if count else []
    except OSError as error:
        print(f"inventory: {error}", file=sys.stderr)
        return 2

    sys.stdout.buffer.write(json_bytes(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
