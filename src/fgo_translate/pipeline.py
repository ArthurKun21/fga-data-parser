"""Build a JP-text -> translated-text table.

Two sources merge into one flat map keyed by the Atlas JP text so consumers
can translate any game text (names, skills, noble Phantasms, buffs, ...) with
a single lookup; missing regions fall back to the jp text on the consumer side:

- Cross-referenced Atlas text (see the atlas module): official per-region game
  text from the parser's outputs, keyed by the exact JP strings consumers look
  up. It wins where present.
- The Chaldea app's mappings: mapping tables keyed by the Atlas JP text and
  holding per-region translations (JP/CN/TW/NA/KR) fill the gaps, and a patch
  file is deep-merged on top with patch values winning, like the app does.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fga_data_parser.utils import read_data

logger = logging.getLogger(__name__)

# Region keys of the TranslationProto message; the JSON output uses the same
# keys. The JP region is the key itself and is not stored separately.
REGIONS = ("cn", "tw", "na", "kr")

# Mapping tables folded into the flat translation map. Keys are the Atlas JP
# text (names, skill descriptions with [{0}] placeholders, ...).
TABLE_NAMES = (
    "svt_names",
    "entity_names",
    "ce_names",
    "mc_names",
    "skill_names",
    "skill_detail",
    "td_names",
    "td_detail",
    "buff_names",
    "buff_detail",
)

# Private-use characters the app normalizes in every downloaded file.
_PUA_REPLACEMENTS = {
    ord("\ue000"): "{jin}",
    ord("\ue001"): "鯖",
    ord("\ue002"): "辿",
    ord("\ue00b"): "槌",
    **{ord(chr(code_point)): "▓" for code_point in range(0xE003, 0xE00B)},
}


@dataclass
class Translation:
    """Translated text for one JP string; None regions fall back to jp."""

    jp: str
    cn: str | None = None
    tw: str | None = None
    na: str | None = None
    kr: str | None = None

    def to_json(self) -> dict[str, str]:
        fields = {"jp": self.jp, "cn": self.cn, "tw": self.tw, "na": self.na, "kr": self.kr}
        return {region: name for region, name in fields.items() if name is not None}


def build_translations(
    chaldea_dir: Path,
    atlas_entries: dict[str, dict[str, str]] | None = None,
    used_texts: set[str] | None = None,
) -> dict[str, Translation]:
    """Build the flat JP-text -> Translation map.

    atlas_entries are the cross-referenced Atlas entries from the parser's
    per-region outputs (see atlas.build_atlas_entries); official regional text
    wins where present, the Chaldea tables only fill gaps, and the mapping
    patch still wins last like the app's deep merge. used_texts prunes the
    final table to the JP texts the parser outputs contain (see
    atlas.collect_used_texts); None keeps every key.
    """
    flat: dict[str, dict[str, str]] = {}
    if atlas_entries:
        flat.update(atlas_entries)
        # Propagate the Atlas keys to both spellings before the Chaldea
        # tables merge, so official text claims both spellings.
        _register_middle_dot_aliases(flat)
    else:
        logger.info("No Atlas-derived entries; building from the Chaldea mappings only")

    for table_name in TABLE_NAMES:
        raw = read_data(chaldea_dir / "mappings" / f"{table_name}.json")
        for jp_text, regions in raw.items():
            _merge_regions(flat.setdefault(normalize_text(jp_text), {}), regions, fill_only=True)

    patch_path = chaldea_dir / "dist" / "mappingPatch.json"
    if patch_path.exists():
        patch = read_data(patch_path)
        for table_name, entries in patch.items():
            if table_name not in TABLE_NAMES:
                continue
            for jp_text, regions in entries.items():
                # Patch values win, like the app's deep merge.
                _merge_regions(flat.setdefault(normalize_text(jp_text), {}), regions)
    else:
        logger.debug("No mapping patch at %s", patch_path)

    _register_middle_dot_aliases(flat)

    if used_texts is not None:
        pruned = {key: regions for key, regions in flat.items() if key in used_texts}
        logger.info("Pruned %d keys unused by the parser outputs", len(flat) - len(pruned))
        flat = pruned

    translations = {key: _translation(key, regions) for key, regions in flat.items()}
    _log_coverage(translations)
    return translations


def translations_to_json(
    translations: dict[str, Translation],
) -> dict[str, dict[str, dict[str, str]]]:
    """Convert the flat table to the JSON output shape (keys sorted)."""
    return {
        "translations": {
            jp_text: translation.to_json() for jp_text, translation in sorted(translations.items())
        }
    }


def load_overwrite_translations(path: Path) -> dict[str, dict[str, str | None]]:
    """Load the manual overwrite table; a missing file is an empty table.

    Entries hold only the regions the build is missing: null while unfilled,
    the provided translation once filled. The file is hand-edited, so
    structural mistakes fail loudly instead of silently dropping manual
    translations. Entries from before the null format that echo the jp text
    are tolerated and ignored — the key is the jp text itself.
    """
    if not path.exists():
        return {}
    raw = read_data(path)
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


def apply_overwrite_translations(
    translations: dict[str, Translation],
    overwrite: dict[str, dict[str, str | None]],
) -> dict[str, dict[str, str | None]]:
    """Fill missing regions from the overwrite table; return the table to persist.

    Existing values are never replaced. A persisted entry holds only the
    regions missing from the freshly built table — null while unfilled, the
    applied value once filled, because the next run rebuilds the table from
    the Chaldea data and would lose the value otherwise. Keys the build fully
    translated itself, and keys unknown to it, are dropped as clutter.
    """
    updated: dict[str, dict[str, str | None]] = {}
    fills = 0
    for jp_text, translation in translations.items():
        entry = overwrite.get(jp_text, {})
        missing = [region for region in REGIONS if getattr(translation, region) is None]
        for region in missing:
            value = entry.get(region)
            if value is not None:
                setattr(translation, region, value)
                fills += 1
        if missing:
            updated[jp_text] = {region: getattr(translation, region) for region in missing}
    logger.info("Overwrite translations: applied %d fills, %d entries pending", fills, len(updated))
    return updated


def overwrite_translations_to_json(
    overwrite: dict[str, dict[str, str | None]],
) -> dict[str, dict[str, dict[str, str | None]]]:
    """Convert the overwrite table to the JSON output shape (keys sorted)."""
    return {"translations": dict(sorted(overwrite.items()))}


def _translation(jp_text: str, regions: dict[str, str]) -> Translation:
    return Translation(
        jp=jp_text,
        cn=regions.get("cn"),
        tw=regions.get("tw"),
        na=regions.get("na"),
        kr=regions.get("kr"),
    )


def _merge_regions(entry: dict[str, str], regions: dict[str, Any], *, fill_only: bool = False):
    """Merge normalized region values into an entry.

    Null/non-string values are dropped. With fill_only, existing regions are
    kept (later tables only fill gaps); otherwise patch values win.
    """
    for region, name in regions.items():
        normalized = region.lower()
        if normalized not in REGIONS or not isinstance(name, str):
            continue
        if fill_only and normalized in entry:
            continue
        entry[normalized] = name


# The parser keeps Atlas' halfwidth katakana middle dot (魔術礼装･カルデア)
# while the Chaldea tables use the fullwidth ・; without aliasing, keys from
# one source would never merge with or be found via the other.
_HALF_WIDTH_DOT = "･"
_FULL_WIDTH_DOT = "・"


def _register_middle_dot_aliases(flat: dict[str, dict[str, str]]) -> None:
    """Register every entry under both middle-dot spellings (fill-only)."""
    for key, regions in list(flat.items()):
        if _HALF_WIDTH_DOT in key:
            alias = key.replace(_HALF_WIDTH_DOT, _FULL_WIDTH_DOT)
        elif _FULL_WIDTH_DOT in key:
            alias = key.replace(_FULL_WIDTH_DOT, _HALF_WIDTH_DOT)
        else:
            continue
        for region, value in regions.items():
            flat.setdefault(alias, {}).setdefault(region, value)


def _log_coverage(translations: dict[str, Translation]) -> None:
    counts = {
        region: sum(1 for translation in translations.values() if getattr(translation, region))
        for region in REGIONS
    }
    summary = ", ".join(f"{region}: {count}" for region, count in counts.items())
    logger.info("Translation coverage: %d keys (%s)", len(translations), summary)


def normalize_text(text: str) -> str:
    return text.translate(_PUA_REPLACEMENTS)
