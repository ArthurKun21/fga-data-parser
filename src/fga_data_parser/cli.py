import argparse
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.logging import RichHandler

from .pb import craft_essences_to_bytes, mystic_codes_to_bytes, servants_to_bytes
from .pipeline import build_craft_essences, build_mystic_codes, build_servants
from .utils import download_data, read_data, write_bytes, write_data

logger = logging.getLogger(__name__)

# All five game servers; JP first because it anchors the translation table.
REGIONS = ("JP", "CN", "TW", "KR", "NA")
SERVANT_URL = "https://api.atlasacademy.io/export/{region}/nice_servant.json"
MYSTIC_CODE_URL = "https://api.atlasacademy.io/export/{region}/nice_mystic_code.json"
CRAFT_ESSENCE_URL = "https://api.atlasacademy.io/export/{region}/nice_equip.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="fga-data-parser",
        description="Convert raw Atlas Academy data into data files for FGA.",
    )
    parser.add_argument(
        "--regions",
        nargs="+",
        choices=REGIONS,
        default=REGIONS,
        help="game servers to fetch data from (default: all regions)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-download the raw data even if it is already cached",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="directory for the cached raw data and generated files (default: current directory)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="enable debug logging",
    )
    return parser.parse_args(argv)


def setup_logging(*, verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging(verbose=args.verbose)

    for region in args.regions:
        _parse_region(args.output_dir, region, force=args.force)

    return 0


def _region_file(output_dir: Path, stem: str, region: str) -> Path:
    """JP keeps the unsuffixed primary names; other regions feed the
    translation join and only need JSON."""
    if region == "JP":
        return output_dir / f"{stem}.json"
    return output_dir / f"{stem}.{region.lower()}.json"


def _write_proto(
    output: Path, models: Any, to_bytes: Callable[[Any], bytes], *, region: str
) -> Path | None:
    """Only JP gets protobuf outputs; other regions are intermediate data."""
    if region != "JP":
        return None
    pb_output = output.with_suffix(".pb")
    write_bytes(pb_output, to_bytes(models))
    return pb_output


def _parse_region(output_dir: Path, region: str, *, force: bool) -> None:
    servant_file = _region_file(output_dir, "nice_servant", region)
    download_data(servant_file, SERVANT_URL.format(region=region), force=force)
    servants = build_servants(read_data(servant_file), region=region)
    servant_output = _region_file(output_dir, "servant_data", region)
    write_data(servant_output, servants)
    servant_pb_output = _write_proto(servant_output, servants, servants_to_bytes, region=region)
    logger.info(
        "Wrote %d servants to %s", len(servants), _outputs(servant_output, servant_pb_output)
    )

    mystic_code_file = _region_file(output_dir, "nice_mystic_code", region)
    download_data(mystic_code_file, MYSTIC_CODE_URL.format(region=region), force=force)
    mystic_codes = build_mystic_codes(read_data(mystic_code_file))
    mystic_code_output = _region_file(output_dir, "mystic_code_data", region)
    write_data(mystic_code_output, mystic_codes)
    mystic_code_pb_output = _write_proto(
        mystic_code_output, mystic_codes, mystic_codes_to_bytes, region=region
    )
    logger.info(
        "Wrote %d mystic codes to %s",
        len(mystic_codes),
        _outputs(mystic_code_output, mystic_code_pb_output),
    )

    craft_essence_file = _region_file(output_dir, "nice_equip", region)
    download_data(craft_essence_file, CRAFT_ESSENCE_URL.format(region=region), force=force)
    craft_essences = build_craft_essences(read_data(craft_essence_file))
    craft_essence_output = _region_file(output_dir, "craft_essence_data", region)
    write_data(craft_essence_output, craft_essences)
    craft_essence_pb_output = _write_proto(
        craft_essence_output, craft_essences, craft_essences_to_bytes, region=region
    )
    logger.info(
        "Wrote %d craft essences to %s",
        len(craft_essences),
        _outputs(craft_essence_output, craft_essence_pb_output),
    )


def _outputs(json_output: Path, pb_output: Path | None) -> str:
    return f"{json_output} and {pb_output}" if pb_output else str(json_output)
