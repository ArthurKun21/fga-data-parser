# Choice detail fallback: label unnamed buttons from buff details

- **Branch:** `fix/missing-skill-options`
- **Status:** approved plan, ready for implementation
- **Scope:** `src/fga_data_parser/skill.py`, `tests/test_skill.py`, `tests/test_pipeline.py`, `docs/fga_data_parser.md`

## Problem

`Skill._check_for_choice_from_scripts` builds `Choice2Detail`/`Choice3Detail` only from
`script/SelectAddInfo/<0>/btn/<N>/name`. Jade Rabbit (2301100, collectionNo 448) skill 2
(2535550) has 2 buttons that carry only `conds`/`image`/`imageUrl` — no `name` key — so
both are dropped, 0 options survive, and no choice entry is produced (`Choice2Detail`
stays null on the proto).

## New fallback pattern

When a button's `name` is missing/empty, resolve its label from the functions:

1. The count of `btn` entries still decides CHOICE_2 (2) vs CHOICE_3 (3) and therefore
   which `ActSelectIndex` values (0, 1, or 0/1/2) to look for.
2. For button index `i`, find the first raw function whose `svals[0].ActSelectIndex == i`
   (ActSelectIndex is a plain int, byte-identical across all per-level svals entries; the
   existing `_act_select_index` helper already reads exactly this).
3. Take that function's `buffs[0].detail` string as the replacement label; if it is empty,
   keep scanning further functions gated to the same index.
4. Buttons with a real `name` keep it; buttons that resolve to nothing are still dropped
   (preserves current behavior for skills with no usable data).

**No `.proto` / `pb.py` change needed** — the `Choice2Detail`/`Choice3Detail` fields
already exist; only population changes.

## Raw-data facts this rests on (verified in `nice_servant.json` + `chaldea-data/dist`)

- 2535550 is the only skill of 2301100 with `SelectAddInfo`; its 10 per-level script
  entries are byte-identical, and both `btn` objects lack `name` entirely (keys are
  exactly `conds`/`image`/`imageUrl` — art buttons `btn_select_003/004`).
- `btn` array index == `ActSelectIndex` value across all 17 SelectAddInfo skills in JP
  `baseSkills.json` (verified on 2273450, 2468551, 2619550); unconditional functions
  simply omit ActSelectIndex.
- Jade Rabbit's gated functions: `ActSelectIndex: 0` → fn 22872 (`addStateShort`) with
  buff 5911 (detail "宝具を全体攻撃宝具に変更する", change NP to AoE); `ActSelectIndex: 1`
  → fn 22871 with buff 5910 ("宝具を単体攻撃宝具に変更する", change NP to single-target).
- `buffs/<0>/detail` is a plain string on the buff object in nice-format function data
  (the parser's input); `baseSkills.json` strips buffs but is not this parser's input.

## Implementation

1. **Plan file** → `plans/choice-detail-fallback-from-buffs.md` (this document).
2. **`src/fga_data_parser/skill.py`** — pass `functions` through:
   `Skill.create` calls `_check_for_choice_from_scripts(scripts, functions)`; in the
   button loop use `enumerate(button_info)` and fall back to a new static helper
   `_buff_detail_for_index(functions, index) -> str` returning the first non-empty
   `buffs[0].detail` among functions whose `_act_select_index(function) == index`, else
   `""`. Update the docstring.
3. **`tests/test_skill.py`** (dict fixtures + dataclass-equality asserts):
   - 2 unnamed buttons + functions with `svals: [{"ActSelectIndex": 0|1}]` and
     `buffs: [{"detail": ...}]` → `CHOICE_2` with both buff details (Jade-Rabbit-shaped).
   - 3 buttons / ASI 0,1,2 → `CHOICE_3`.
   - Mixed: btn 0 named in script, btn 1 unnamed → option_a from script name, option_b
     from buff detail.
   - Unnamed button with no matching function/buff detail → still dropped → `TARGET_ALL`
     (existing `test_empty_button_names_are_skipped` keeps passing: no functions).
4. **`tests/test_pipeline.py`** — one end-to-end test: raw servant with a
   Jade-Rabbit-like skill asserting `servant.skills[0].functions[0].choice2.option_a`
   equals the buff detail.
5. **`docs/fga_data_parser.md`** — extend the SelectAddInfo section with the fallback
   rule (btn index ↔ `svals[0].ActSelectIndex`, `buffs[0].detail` as label source,
   2301100 as the example).

## Verify

1. `uv run pytest`
2. `uv run ruff format .` && `uv run ruff check .`
3. Smoke run `uv run fga-data-parser`; spot-check `servant_data.json`: servant 2301100
   skill 2 now carries `choice2` populated from the two buff details.

## Notes

- Per AGENTS.md: never commit, never stage — the user reviews and commits.
- No proto regeneration required (no `.proto` change).
