"""Build a JP-text -> translated-text table from the Chaldea mappings.

Mirrors how the Chaldea app resolves translations: mapping tables are keyed by
the Atlas JP text and hold per-region translations (JP/CN/TW/NA/KR),
private-use characters are normalized, and a patch file is deep-merged on top
with patch values winning. All tables are folded into one flat map keyed by
the JP text so consumers can translate any game text (names, skills, noble
Phantasms, buffs, ...) with a single lookup; missing regions fall back to the
jp text on the consumer side.
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


def build_translations(chaldea_dir: Path) -> dict[str, Translation]:
    """Build the flat JP-text -> Translation map from a chaldea-data checkout."""
    flat: dict[str, dict[str, str]] = {}
    for table_name in TABLE_NAMES:
        raw = read_data(chaldea_dir / "mappings" / f"{table_name}.json")
        for jp_text, regions in raw.items():
            _merge_regions(flat.setdefault(_normalize_text(jp_text), {}), regions, fill_only=True)

    patch_path = chaldea_dir / "dist" / "mappingPatch.json"
    if patch_path.exists():
        patch = read_data(patch_path)
        for table_name, entries in patch.items():
            if table_name not in TABLE_NAMES:
                continue
            for jp_text, regions in entries.items():
                # Patch values win, like the app's deep merge.
                _merge_regions(flat.setdefault(_normalize_text(jp_text), {}), regions)
    else:
        logger.debug("No mapping patch at %s", patch_path)

    return {key: _translation(key, regions) for key, regions in flat.items()}


def translations_to_json(
    translations: dict[str, Translation],
) -> dict[str, dict[str, dict[str, str]]]:
    """Convert the flat table to the JSON output shape (keys sorted)."""
    return {
        "translations": {
            jp_text: translation.to_json() for jp_text, translation in sorted(translations.items())
        }
    }


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


def _normalize_text(text: str) -> str:
    return text.translate(_PUA_REPLACEMENTS)
