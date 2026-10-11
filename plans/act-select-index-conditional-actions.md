# Conditional actions: gate `ScriptFunction` on `ActSelectIndex`

- **Branch:** `feat/new-data-format`
- **Status:** approved plan, ready for implementation
- **Scope:** `protos/fga_data_parser/common.proto`, `src/fga_data_parser/skill.py`, `pb.py`, `tests/`, `docs/fga_data_parser.md`

## Design

Add a per-entry execution condition to `ScriptFunction`: an `optional int32 act_select_index`
— the 0-based index of the `SelectAddInfo` choice button that gates the action. The choice
entry executes first; each following entry executes only when the button with that index is
picked, and is skipped otherwise. Unset = unconditional. The choice entry itself and the
default TargetAll entry never carry a condition.

**Proto** (`common.proto`, `ScriptFunction`): `optional int32 act_select_index = 7;` —
appended as a new field; `optional` is mandatory because index **0** is meaningful
(verified: servant 1002100's transform is gated on button 0, and a plain int32 would erase
0 vs unset on the wire).

**Dataclass** (`ScriptFunction`): `act_select_index: int | None = None`, placed right
after `target`.

## Raw-data facts this rests on (verified in cached `nice_servant.json`)

- `ActSelectIndex` lives in svals and is **byte-identical across all 10 per-level entries**
  of a function (50/50) — read it once from `svals[0]`. Values are only 0, 1, 2 and always
  strictly less than the skill's button count.
- It **only ever coexists with `SelectAddInfo`** (18/18 skills); the same `funcId` can appear
  twice within one skill at different indices (2301100's fn 460/470 at index 0 and 1), so
  entries are keyed by position, not funcId.
- 50 gated functions across 18 skills. Only 6 are actions we already model
  (4 `transformServant` + 2 `ptOne`); the other 44 are plain buff/NP/field functions
  (`addState*`, `lossStar`, `gainNp`, `subState`, `addFieldChangeToField`) that stay
  unmodeled — per the agreed scope, only SkillTarget actions get gated, and the choice
  `optionA/B/C` names already label each branch.
- `commandTypeSelfTreasureDevice` (0/10) and `ptselectOneSub` (0 occurrences) never carry
  ActSelectIndex today → the aggregated np2/np3 entry gets no condition (noted as a known
  limitation in docs).
- Key examples: Prelati 505600/505700 — transform gated on index 1, button 0 ("入れ替えない")
  is a no-op branch; 1002000/1002100 — the same transform mechanic gated on **different**
  indices (1 and 0), which is exactly why the condition must live per-entry; Kukulkan
  2501100 — unconditional base effects plus an index-1 branch (lossStar + buffs, and two
  `ptOne` functions that become gated TargetOne entries).

## Implementation

1. **Plan file** → `plans/act-select-index-conditional-actions.md` (this document, with the
   scope note: button `conds` like Kukulkan's `STAR_HIGHER` gate button *availability* — a
   separate mechanism that stays uncaptured).
2. **`protos/fga_data_parser/common.proto`** — add the commented
   `optional int32 act_select_index = 7;` to `ScriptFunction`; regenerate bindings.
3. **`src/fga_data_parser/skill.py`** — add the dataclass field; add a small
   `_act_select_index(function)` helper reading `svals[0]["ActSelectIndex"]`; attach it to
   the `ptOne`/`ptselectOneSub` entries and in `_transform_function`; leave the command-NP
   entry as-is. `_dedupe_functions` now merges consecutive entries only when **both**
   `target` and `act_select_index` match (so Kukulkan's unconditional TargetOne and gated
   TargetOne stay distinct), keeping the payload-merge behavior.
4. **`src/fga_data_parser/pb.py`** — in `_script_function_message`, set
   `message.act_select_index` only when not None.
5. **Tests** — `test_skill.py`: transform with ASI (Prelati-shaped svals), `ptOne` with ASI,
   same target with different ASI not deduped, same target + same ASI still deduped,
   absent → None. `test_pb.py`: round-trip `act_select_index == 1` with `HasField`, a
   dedicated index-0 case asserting `HasField("act_select_index")` and value 0 (the
   plain-int32 footgun), and unset on bare entries; `make_skill` gets the condition on its
   transform entry.
6. **Docs** (`docs/fga_data_parser.md`) — new "ActSelectIndex" subsection with the facts
   above, the 44/50 unmodeled-functions note, and the conds-vs-ASI distinction.

## Verify

1. `uv run pytest`
2. `uv run ruff format .` + `uv run ruff check .`
3. No-network `uv run fga-data-parser` smoke run spot-checking `servant_data.json`:
   - 505600 / 505700: `[Choice2, Transform(target=<other Prelati>, ascension=0, act_select_index=1)]`
   - 1002100: transform entry with `act_select_index=0` (and 1002000 with 1)
   - 2501100 skill 2190650: `[Choice2, TargetOne (unconditional), TargetOne(act_select_index=1)]`
   - 203300 stays `[Choice2]` and 2301100 stays `[TargetAll]` (their gated functions are
     unmodeled self-buffs)

## Notes

- Per AGENTS.md: never commit, never stage — the user reviews and commits.
- Generated `*_pb2.py` / `*_pb2.pyi` stay gitignored; regenerate after any `.proto` change.
