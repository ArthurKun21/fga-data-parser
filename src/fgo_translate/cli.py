"""CLI for building the translated-text data files."""

import argparse
import logging
from pathlib import Path

from fga_data_parser.cli import setup_logging
from fga_data_parser.utils import write_bytes, write_data

from .pb import translations_to_bytes
from .pipeline import build_translations, translations_to_json

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="fgo-translate",
        description="Build translated-text data files from the Chaldea mappings.",
    )
    parser.add_argument(
        "--chaldea-data",
        type=Path,
        default=Path.cwd() / "chaldea-data",
        help="path to the chaldea-center/chaldea-data checkout (default: ./chaldea-data)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="directory for the generated files (default: current directory)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="enable debug logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging(verbose=args.verbose)

    translations = build_translations(args.chaldea_data)

    json_output = args.output_dir / "fgo_translate.json"
    write_data(json_output, translations_to_json(translations))
    pb_output = json_output.with_suffix(".pb")
    write_bytes(pb_output, translations_to_bytes(translations))
    logger.info("Wrote %d translated texts to %s and %s", len(translations), json_output, pb_output)
    return 0
