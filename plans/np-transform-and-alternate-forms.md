# NP transforms (`NoblePhantasmTarget`) + servant `alternate_forms_id`

- **Branch:** `feat/new-data-format`
- **Status:** approved plan, ready for implementation
- **Scope:** `protos/fga_data_parser/common.proto`, `servant.proto`, `src/fga_data_parser/enums.py`, `servant.py`, `pipeline.py`, `pb.py`, `tests/`, `docs/fga_data_parser.md`

## Design

1. **`NoblePhantasmTarget` enum** — top-level in `common.proto` (user decision), values
   prefixed because a bare `TRANSFORM` collides with `SkillTarget.TRANSFORM` under proto's
   C++ scoping: `NOBLE_PHANTASM_TARGET_UNSPECIFIED = 0; NOBLE_PHANTASM_TARGET_TRANSFORM = 1;`.
   `NoblePhantasm` gains `NoblePhantasmTarget target = 5;`. Python StrEnum member mirrors the
   value name (`NOBLE_PHANTASM_TARGET_TRANSFORM = "Transform"`) so `.Value(member.name)`
   stays mechanical; JSON output shows the clean `"Transform"`, `null` for ordinary NPs.
2. **`Servant.alternate_forms_id`** — `repeated int32 alternate_forms_id = 12;` in
   servant.proto; dataclass `alternate_forms_id: list[int] = field(default_factory=list)`,
   sorted ascending.
3. **Detection** — `_build_nps` marks the NP `target=TRANSFORM` when the raw NP's
   `functions` contain `funcType: "transformServant"` (verified encoding: Aoko 2501400's
   NP 2501401 → 2501500; Jekyll 600700's NPs 600701+600702 → 600710; NP svals use 5 levels ×
   `svals2`–`svals5` overcharge lists, Value constant — only funcType is needed).
4. **Alternate forms** — `build_servants` collects transform edges from each raw servant's
   **skills and NPs** (`transformServant` `svals[0]["Value"]`, excluding self-transforms
   where Value == own id, e.g. Ptolemaios/Melusine ascension swaps), then applies
   **bidirectional closure** so both forms reference each other even when the data is
   one-way (user decision: skills + NPs, bidirectional).

## Raw-data facts this rests on (verified in cached `nice_servant.json`)

- Transform is expressed solely as `funcType: "transformServant"` — 7 skill functions + 3 NP
  functions; the target id lives only in svals `Value`. No other change/swap mechanism
  exists in NP functions (`addFieldChangeToField` is field alteration, unrelated).
- Cross-servant pairs: 505600↔505700 and 1002000↔1002100 (skills, bidirectional in data);
  2501400→2501500 and 600700→600710 (NPs, **one-way** — 2501500 has zero back-references,
  600710 links back only via `skillSvts`/`functvals`). All four hidden alternates are
  `type: "normal"` (so they are parsed into the output) with `collectionNo: 0`.
- The only dedicated Atlas field is `script.transformInfo`
  (`saveTransform`/`saveTransformDefault`, Prelati pair only) — not general enough; derive
  from transform functions instead. `svtChange`/`overwrites` are quest-conditional variants,
  not alternate forms.
- Self-transforms (205000 Ptolemaios, 304800 Melusine) have `Value == own id` → excluded
  from alternate forms.

## Implementation

1. **Plan file** → `plans/np-transform-and-alternate-forms.md` (this document).
2. **Protos** — `common.proto`: the new enum; `servant.proto`: `NoblePhantasm.target = 5`,
   `Servant.alternate_forms_id = 12`; regenerate bindings.
3. **`enums.py`** — `NoblePhantasmTarget` StrEnum (single member, value `"Transform"`).
4. **`servant.py`** — `NoblePhantasm.target: NoblePhantasmTarget | None = None`;
   `Servant.alternate_forms_id`.
5. **`pipeline.py`** — `_noble_phantasm_target(raw_np)` helper used by `_build_nps`;
   `_transform_target_ids(raw_servant)` scanning skills + NPs; collect edges in
   `build_servants`'s loop, then a closure pass sets `alternate_forms_id` (sorted, both
   directions).
6. **`pb.py`** — `_noble_phantasm_message` sets `target` only when the dataclass field is
   not None; `_servant_message` passes `alternate_forms_id`.
7. **Tests** — `test_pipeline.py`: NP with/without transform function; Prelati-shaped pair
   referencing each other; Aoko-shaped one-way NP pair where the alternate still gets the
   reverse reference; self-transform yields `[]`. `test_pb.py`: `make_servant` gets
   `alternate_forms_id=[600710]` (+ round-trip assert); dedicated NP-target round trip
   asserting value + `HasField` for TRANSFORM and unset (0) for a plain NP.
8. **Docs** (`docs/fga_data_parser.md`) — "Noble Phantasm transforms" and "Alternate forms"
   subsections with the facts above (one-way→synthesized-reverse rule, hidden
   `collectionNo: 0` forms being type normal, unused `transformInfo` field); update the
   shared-types bullet to include `NoblePhantasmTarget`.

## Verify

1. `uv run pytest`
2. `uv run ruff format .` + `uv run ruff check .`
3. No-network `uv run fga-data-parser` smoke run spot-checking `servant_data.json`:
   - 2501400: NP target `"Transform"`, `alternate_forms_id == [2501500]`;
     2501500: `[2501400]` (synthesized)
   - 600700: both NPs target `"Transform"`, `alternate_forms_id == [600710]`;
     600710: `[600700]`, its NPs (600711/600712, empty functions) target null
   - 505600↔505700 and 1002000↔1002100 reference each other; 205000/304800 stay `[]`
   - Scan the raw export once for `transformServant` under `appendPassive` functions to
     confirm that path genuinely has none (we don't scan it).

## Notes

- **Deviation (user-authored proto):** while this plan was being drawn up, servant.proto
  was edited directly by the user and is the source of truth: `NoblePhantasmTarget` lives
  top-level in **servant.proto** (not common.proto) with a single value, `NoblePhantasm`
  carries `repeated NoblePhantasmTarget targets = 5` (plural), and `alternate_forms_id`
  is field number **100** with its own comment. Only fix applied to that proto: the value
  is named `NOBLE_PHANTASM_TARGET_TRANSFORM` — a bare `TRANSFORM` collides with
  `SkillTarget.TRANSFORM` in package scope, and proto3 requires the first enum value to be
  zero. The Python dataclass mirrors the repeated `targets` field
  (`targets: list[NoblePhantasmTarget]`), and the generated enum is referenced via
  `servant_pb2.NoblePhantasmTarget`.
- Per AGENTS.md: never commit, never stage — the user reviews and commits.
- Generated `*_pb2.py` / `*_pb2.pyi` stay gitignored; regenerate after any `.proto` change.
