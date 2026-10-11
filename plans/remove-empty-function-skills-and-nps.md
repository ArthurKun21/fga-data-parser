# Exclude skills/NPs whose `functions` is empty

- **Branch:** `feat/remove-empty-functions`
- **Status:** approved plan, ready for implementation
- **Scope:** `src/fga_data_parser/pipeline.py`, `tests/test_pipeline.py`, `docs/fga_data_parser.md`

## Design

1. **Rule** — a raw skill or Noble Phantasm whose `functions` list is empty (or the
   key is missing) is a placeholder for a not-yet-live entry — typically a newly
   released servant that is still locked — and is dropped at parse time. Exclusion
   happens before model construction, so models, protos, and `pb.py` are unchanged
   (no proto regen, no schema impact).
2. **Location** — all raw-JSON → model parsing lives in `pipeline.py`
   (`servant.py`/`mystic_code.py` are dataclass-only): `_parse_skills` (shared by
   servants and mystic codes) and `_build_nps` (servants only). That is where both
   filters go.
3. **`_parse_skills` filters before `enumerate`** so mystic-code skills
   (`num_from_index=True`) get contiguous numbers over the *kept* skills instead of
   gaps at dropped positions. Servant skills take `num` from raw data and are
   unaffected by the choice.
4. **`_build_nps` uses a guard clause** (`if not raw.get("functions"): continue`) —
   NP `num` comes from raw data, so there is no numbering concern.
5. **Missing key == empty list** (`not raw.get("functions")`): the nice export
   always carries the key today (0 missing), but treating absence as empty is the
   defensive reading of the rule.
6. **No logging on drop** — `pipeline.py` is a pure-transform module (its `logger`
   is unused); the behavior is documented in docstrings and `docs/` instead.
7. **Deliberately not filtered** — append passives and craft-essence skills: their
   models don't consume `functions` and they aren't in scope.

## Raw-data facts (verified in cached JP `nice_servant.json`, 2026-10)

- 19,414 `functions` keys; 7 empty (`"functions":[]`); 0 null; 0 missing.
- The 7 are the placeholder pattern: servant 600710's NP 600711 is empty while its
  NP 600712 carries functions; Mash 800100's base NP 800100 (Lord Chaldeas) is
  empty while 800101 is live; one empty skill sits in the record containing
  classPassive 34450; the rest end other servants' NP lists.
- Live gated entries (Mash skill 459550, Melusine skill 888575, …) always have
  non-empty `functions` — gating comes from `skillSvts`/`npSvts`
  `releaseConditions`, not from missing functions. Only not-yet-live placeholders
  are empty.
- `nice_mystic_code.json`: 84 `functions` keys, 0 empty — the mystic-code filter is
  preventive/consistency.

## Implementation

1. **Plan file** → `plans/remove-empty-function-skills-and-nps.md` (this document).
2. **`pipeline.py` `_parse_skills`** — iterate over
   `(r for r in raw_skills if r.get("functions"))`; docstring notes the drop.
3. **`pipeline.py` `_build_nps`** — guard clause on `not raw.get("functions")`;
   docstring notes the drop.
4. **`tests/test_pipeline.py`**:
   - Fixture repairs (synthetic fixtures omit/empty `functions` where real live
     entries always carry them, so they'd be wrongly dropped): `make_servant`
     default NP, `make_mystic_code` skill, both `raw_np` dicts in the
     `test_np_collects_stage_locks_*` tests, both `raw_skill` dicts in the
     `test_skill_collects_*` tests — each gains a non-empty `functions` list
     (e.g. `[{"funcType": "damage", "funcTargetType": "enemy"}]`).
   - New tests: `test_excludes_skills_without_functions` (live + placeholder skill
     with skillSvts locks → only live kept), `test_fully_locked_servant_parses_with_no_skills_and_nps`
     (600710-style new release → `skills == []`, `nps == []`),
     `test_excludes_nps_without_functions` (placeholder NP dropped, live NP kept),
     `test_np_missing_functions_key_is_dropped`, `test_mystic_code_excludes_skills_without_functions`
     ([live, empty, live] → kept nums `[0, 1]`).
5. **Docs** (`docs/fga_data_parser.md`) — note in the gated/locked section that
   empty-`functions` entries are excluded as placeholders of not-yet-released
   servants (examples: 600710's NP 600711, Mash's NP 800100); one-line mention in
   the schema-decisions section.

## Verify

1. `uv run pytest`
2. `uv run ruff check .` + `uv run ruff format .`
3. Smoke run `uv run fga-data-parser`; spot-check `servant_data.json`: servant
   600710's `nps` excludes 600711, Mash's excludes 800100, and no parsed skill/NP
   list contains a former empty-`functions` entry.

## Notes

- Per AGENTS.md: never commit, never stage — the user reviews and commits.
- No `.proto` change, so generated bindings need no regeneration.
- NA data flows through the same code path; the rule is region-generic.
