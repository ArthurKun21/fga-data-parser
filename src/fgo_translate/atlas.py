"""Cross-reference the parser's per-region outputs into translation entries.

The parser writes parsed JSON per region (JP unsuffixed, others .{region});
entities line up across regions by collection number or id and skills by id
with a num/position fallback, so every text field the parser emits can be
paired with its official per-region text. The keys are exactly the JP texts in
the parser outputs — FGA-facing renames and dedupe suffixes included — so
consumer lookups against the parser data hit the table directly.
"""

import logging
from pathlib import Path
from typing import Any

from fga_data_parser.utils import read_data

from .pipeline import REGIONS, normalize_text

logger = logging.getLogger(__name__)

# Parser output stems that anchor the translation keys and the pruning.
_PARSED_STEMS = ("servant_data", "mystic_code_data", "craft_essence_data")

# Text fields of the parsed script-function payloads (choice popups and NP
# type updates); functions align by position across regions because they hold
# one skill's targeting actions in execution order.
_PAYLOAD_FIELDS = {
    "choice2": ("detail", "option_a", "option_b"),
    "choice3": ("detail", "option_a", "option_b", "option_c"),
    "np2": ("detail", "option_a", "option_b"),
    "np3": ("detail", "option_a", "option_b", "option_c"),
}


def build_atlas_entries(data_dir: Path) -> dict[str, dict[str, str]]:
    """Build normalized JP-text -> {region: text} entries from parsed outputs.

    Returns an empty map when no JP output exists: without JP keys there is
    nothing to cross-reference and the caller falls back to Chaldea only.
    """
    flat: dict[str, dict[str, str]] = {}
    _collect_servants(flat, _load_per_region(data_dir, "servant_data"))
    _collect_craft_essences(flat, _load_per_region(data_dir, "craft_essence_data"))
    _collect_mystic_codes(flat, _load_per_region(data_dir, "mystic_code_data"))
    return flat


def collect_used_texts(data_dir: Path) -> set[str] | None:
    """Normalized JP texts appearing in the parser's JP outputs.

    The translation table is pruned to these keys, so every string value
    counts: keys are game text while the remaining leaves (icon URLs,
    class_name, flag, ...) never collide with table keys, which keeps the
    scan correct when the parser grows new text fields. Returns None when no
    parsed outputs exist so the caller can skip pruning.
    """
    used: set[str] = set()
    for stem in _PARSED_STEMS:
        path = data_dir / f"{stem}.json"
        if path.exists():
            _collect_strings(read_data(path), used)
    return used or None


def _collect_strings(node: Any, used: set[str]) -> None:
    if isinstance(node, str):
        used.add(normalize_text(node))
    elif isinstance(node, list):
        for item in node:
            _collect_strings(item, used)
    elif isinstance(node, dict):
        for value in node.values():
            _collect_strings(value, used)


def _load_per_region(data_dir: Path, stem: str) -> dict[str, list[dict[str, Any]]]:
    """Load the parser outputs per region; JP is the translation-key source.

    Regions whose output is missing (e.g. the parser ran with --regions JP)
    are skipped and simply contribute no values.
    """
    per_region: dict[str, list[dict[str, Any]]] = {}
    jp_path = data_dir / f"{stem}.json"
    if not jp_path.exists():
        logger.info("No parsed JP data at %s; skipping %s cross-referencing", jp_path, stem)
        return per_region
    per_region["jp"] = read_data(jp_path)
    for region in REGIONS:
        path = data_dir / f"{stem}.{region}.json"
        if path.exists():
            per_region[region] = read_data(path)
        else:
            logger.debug("No parsed %s output at %s", region, path)
    return per_region


def _index_by(
    per_region: dict[str, list[dict[str, Any]]], key: str
) -> dict[str, dict[int, dict[str, Any]]]:
    """Index each non-JP region's entities by collection number or id."""
    return {
        region: {entity[key]: entity for entity in entities}
        for region, entities in per_region.items()
        if region != "jp"
    }


def _align(
    jp_items: list[dict[str, Any]], other_items: list[dict[str, Any]]
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Pair entries across regions by id, falling back to num (list order).

    Skill/NP ids are shared across regions; the num pass covers id spaces that
    are not (e.g. mystic code skills). JP entries the other region does not
    have yet (e.g. a fresh JP upgrade) stay unmatched and are dropped.
    """
    other_by_id = {item["id"]: item for item in other_items if item.get("id")}
    matched_ids = set()
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    unmatched: list[dict[str, Any]] = []
    for jp_item in jp_items:
        other = other_by_id.get(jp_item.get("id"))
        if other is None:
            unmatched.append(jp_item)
            continue
        matched_ids.add(other["id"])
        pairs.append((jp_item, other))

    remaining_by_num: dict[int, list[dict[str, Any]]] = {}
    for item in other_items:
        if item.get("id") in matched_ids:
            continue
        remaining_by_num.setdefault(item.get("num", 0), []).append(item)
    for jp_item in unmatched:
        queue = remaining_by_num.get(jp_item.get("num", 0))
        if queue:
            pairs.append((jp_item, queue.pop(0)))
    return pairs


def _record(flat: dict[str, dict[str, str]], jp_text: str, region: str, value: str) -> None:
    """Record one aligned text pair; when two entities share the same JP text
    the first wins, like the Chaldea tables."""
    if not jp_text or not value:
        return
    flat.setdefault(normalize_text(jp_text), {}).setdefault(region, value)


def _record_texts(
    flat: dict[str, dict[str, str]],
    jp_entry: dict[str, Any],
    other_entry: dict[str, Any],
    region: str,
    fields: tuple[str, ...],
) -> None:
    for field in fields:
        _record(flat, jp_entry.get(field, ""), region, other_entry.get(field, ""))


def _collect_servants(
    flat: dict[str, dict[str, str]], per_region: dict[str, list[dict[str, Any]]]
) -> None:
    jp_servants = per_region.get("jp")
    if not jp_servants:
        return
    others = _index_by(per_region, "collection_no")
    for servant in jp_servants:
        for region, index in others.items():
            other = index.get(servant["collection_no"])
            if other is None:
                continue
            _record(flat, servant["name"], region, other["name"])
            for jp_skill, other_skill in _align(servant["skills"], other["skills"]):
                _record(flat, jp_skill["name"], region, other_skill["name"])
                _record(flat, jp_skill["detail"], region, other_skill["detail"])
                _collect_script_payloads(flat, jp_skill, other_skill, region)
            for jp_np, other_np in _align(servant["nps"], other["nps"]):
                _record(flat, jp_np["name"], region, other_np["name"])
            for jp_skill, other_skill in _align(
                [entry["skill"] for entry in servant["append_passives"]],
                [entry["skill"] for entry in other["append_passives"]],
            ):
                _record_texts(
                    flat, jp_skill, other_skill, region, ("name", "original_name", "detail")
                )


def _collect_script_payloads(
    flat: dict[str, dict[str, str]],
    jp_skill: dict[str, Any],
    other_skill: dict[str, Any],
    region: str,
) -> None:
    # strict=False: a region whose skill logic diverged may carry fewer
    # functions; the extra JP payloads simply get no regional text.
    for jp_function, other_function in zip(
        jp_skill.get("functions", []), other_skill.get("functions", []), strict=False
    ):
        for key, fields in _PAYLOAD_FIELDS.items():
            jp_payload = jp_function.get(key)
            other_payload = other_function.get(key)
            if jp_payload is None or other_payload is None:
                continue
            _record_texts(flat, jp_payload, other_payload, region, fields)


def _collect_craft_essences(
    flat: dict[str, dict[str, str]], per_region: dict[str, list[dict[str, Any]]]
) -> None:
    jp_craft_essences = per_region.get("jp")
    if not jp_craft_essences:
        return
    others = _index_by(per_region, "collection_no")
    for craft_essence in jp_craft_essences:
        for region, index in others.items():
            other = index.get(craft_essence["collection_no"])
            if other is None:
                continue
            _record_texts(flat, craft_essence, other, region, ("name", "original_name"))
            for jp_skill, other_skill in _align(craft_essence["skills"], other["skills"]):
                _record_texts(
                    flat, jp_skill, other_skill, region, ("name", "original_name", "detail")
                )


def _collect_mystic_codes(
    flat: dict[str, dict[str, str]], per_region: dict[str, list[dict[str, Any]]]
) -> None:
    jp_mystic_codes = per_region.get("jp")
    if not jp_mystic_codes:
        return
    others = _index_by(per_region, "id")
    for mystic_code in jp_mystic_codes:
        for region, index in others.items():
            other = index.get(mystic_code["id"])
            if other is None:
                continue
            _record(flat, mystic_code["name"], region, other["name"])
            for jp_skill, other_skill in _align(mystic_code["skills"], other["skills"]):
                _record_texts(flat, jp_skill, other_skill, region, ("name", "detail"))
