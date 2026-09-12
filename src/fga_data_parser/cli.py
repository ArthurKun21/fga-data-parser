import argparse
import logging
from pathlib import Path

from rich.logging import RichHandler

from .pipeline import build_craft_essences, build_mystic_codes, build_servants
from .utils import download_data, read_data, write_data

logger = logging.getLogger(__name__)

REGIONS = ("JP", "NA")
SERVANT_URL = "https://api.atlasacademy.io/export/{region}/nice_servant.json"
MYSTIC_CODE_URL = "https://api.atlasacademy.io/export/{region}/nice_mystic_code.json"
CRAFT_ESSENCE_URL = "https://api.atlasacademy.io/export/{region}/nice_equip.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="fga-data-parser",
        description="Convert raw Atlas Academy data into data files for FGA.",
    )
    parser.add_argument(
        "--region",
        choices=REGIONS,
        default="JP",
        help="game server to fetch data from (default: JP)",
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

    servant_file = args.output_dir / "nice_servant.json"
    download_data(servant_file, SERVANT_URL.format(region=args.region), force=args.force)
    servants = build_servants(read_data(servant_file))
    servant_output = args.output_dir / "servant_data.json"
    write_data(servant_output, servants)
    logger.info("Wrote %d servants to %s", len(servants), servant_output)

    mystic_code_file = args.output_dir / "nice_mystic_code.json"
    download_data(mystic_code_file, MYSTIC_CODE_URL.format(region=args.region), force=args.force)
    mystic_codes = build_mystic_codes(read_data(mystic_code_file))
    mystic_code_output = args.output_dir / "mystic_code_data.json"
    write_data(mystic_code_output, mystic_codes)
    logger.info("Wrote %d mystic codes to %s", len(mystic_codes), mystic_code_output)

    craft_essence_file = args.output_dir / "nice_equip.json"
    download_data(
        craft_essence_file, CRAFT_ESSENCE_URL.format(region=args.region), force=args.force
    )
    craft_essences = build_craft_essences(read_data(craft_essence_file))
    craft_essence_output = args.output_dir / "craft_essence_data.json"
    write_data(craft_essence_output, craft_essences)
    logger.info("Wrote %d craft essences to %s", len(craft_essences), craft_essence_output)

    return 0
