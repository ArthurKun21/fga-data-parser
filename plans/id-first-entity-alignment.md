# Fix wrong cross-region translations: id-first entity alignment

## Problem

`フランチェスカ・プレラーティ` (Francesca Prelati) was translated as `Aozaki Aoko` in
`fgo_translate.json` instead of Chaldea's correct `Francesca Prélat`.

**Root cause** (verified against the cached parser outputs): in
`src/fgo_translate/atlas.py`, servants and craft essences align across regions
by `collection_no` only (`_index_by` — a last-wins dict comprehension). JP has
four servants with `collection_no: 0` (Francesca 505700, Jekyll & Hyde 600710,
Flora 1002100, Aoko 2501500); NA's last zero-collection entry is
`Aozaki Aoko` (2501500), so all four JP names were paired with Aoko and
recorded in every region. The merge policy then made it unfixable downstream:
Atlas values beat the Chaldea tables, and the tables merge with
`fill_only=True` — the correct `svt_names.json` row (`Francesca Prélat`)
could only fill gaps, and there were none left. Confirmed in the produced
`fgo_translate.json`: all four JP names carried Aoko's CN/TW/NA/KR text.

## Design decisions

- **Pair by `id` first.** Atlas ids are shared across regions and unique
  within one (verified: no duplicate top-level ids in any of the five
  `servant_data.*.json`; same holds for CEs/MCs). A JP servant's id hits the
  same entity in every region that has it — exactly the parser-derived,
  non-blind source of translations.
- **Fallback to `collection_no`, but never on 0.** Covers entities a region
  still hosts under an older id (same collectionNo, id drift). Non-zero
  collection numbers are unique per region (verified); `collection_no: 0`
  means "unnumbered" and many distinct servants share it, so it must never
  pair entities — that is the bug. JP zero-collection servants that no other
  region has (Francesca) simply get no Atlas value, letting Chaldea's
  community translation fill in — the intended behavior.
- **No Chaldea/JSON blind copying, no parser changes.** The parser's
  per-region outputs stay the value source; Chaldea mappings keep only
  filling genuine gaps. `fga_data_parser`, the `.proto` files, and
  `chaldea-data/` are untouched; no binding regeneration needed.
- `_align` (skills/NPs) already pairs by id first and stays unchanged.

## Implementation

### 1. `src/fgo_translate/atlas.py`

- Replace `_index_by` with `_pair_entities(jp_items, other_items) ->
  list[tuple[jp, other]]`:
  1. Index the other region by `id`; walk JP entries, pairing on `id` and
     marking matched other-ids.
  2. For unmatched JP entries, pair with leftover other entities sharing the
     same **non-zero** `collection_no` (both sides; zero never matches).
     Entities without `collection_no` (mystic codes) reduce to pure id
     matching — same behavior as today.
- Use `_pair_entities` in `_collect_servants`, `_collect_craft_essences`, and
  `_collect_mystic_codes` (loop `for region, entities in per_region.items()`
  skipping `jp`, then iterate the pairs). Delete `_index_by` (only those
  three call sites).

### 2. Tests — `tests/test_fgo_translate.py`

- Extend the shared `write_atlas_data` fixture with the real shape of the
  bug: JP gets Francesca (`id: 505700, collection_no: 0`) and Aoko
  (`id: 2501500, collection_no: 0`); NA gets only Aoko
  (`id: 2501500, collection_no: 0, name: "Aozaki Aoko"`).
- Extend `write_chaldea_data`'s `svt_names` with
  `"フランチェスカ・プレラーティ": {"NA": "Francesca Prélat", ...}`.
- New/updated assertions:
  - `build_atlas_entries`: `"フランチェスカ・プレラーティ"` absent (no wrong
    NA value), `entries["蒼崎青子"] == {"na": "Aozaki Aoko"}` (correct id
    pair), no servant paired via `collection_no` 0.
  - End-to-end `build_translations` (with pruning): the Francesca key gets
    `na == "Francesca Prélat"` from Chaldea, not Aoko.
  - Collection-number fallback for id drift: JP `{"id": 100, collection_no: 7}`
    pairs with NA `{"id": 200, collection_no: 7}`; id wins when both exist.
- Keep existing assertions green (the existing fixture servants share ids
  across regions, so id-first pairing yields the same results).

### 3. Docs — `docs/fgo_translate.md`

Update the "Cross-referenced Atlas text" section: servants/CEs/MCs align by
`id` first (shared across regions), falling back to `collection_no` for
numbered entities; `collection_no: 0` never pairs (many distinct servants
share it — Francesca Prelati / Aozaki Aoko incident).

## Verification

1. `uv run pytest`, `uv run ruff check .`, `uv run ruff format .` then
   `--check`.
2. Re-run `uv run fgo-translate` against the existing cached outputs and
   `chaldea-data/`, then grep `fgo_translate.json`:
   - `フランチェスカ・プレラーティ` → `na: "Francesca Prélat"`,
     `cn: "弗兰切斯卡·普勒拉蒂"`.
   - `ヘンリー・ジキル＆ハイド` → `na: "Henry Jekyll & Hyde"` (was Aoko).
   - `蒼崎青子` → still `Aozaki Aoko` (correctly paired now, not by accident).
   - `フローラ` → Chaldea value or JP fallback, never Aoko's.
3. Compare the logged per-region coverage counts before/after; expect no
   losses — the four poisoned keys either gain correct values or drop to
   Chaldea-filled ones.
