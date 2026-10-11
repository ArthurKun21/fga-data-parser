# Costume/form-locked skills & NPs (`equipWithTargetCostume`)

- **Branch:** `feat/handle-costume-locked-skills-and-np`
- **Status:** approved plan, ready for implementation
- **Scope:** `protos/fga_data_parser/common.proto`, `servant.proto`, `src/fga_data_parser/skill.py`, `servant.py`, `pipeline.py`, `pb.py`, `tests/`, `docs/fga_data_parser.md`

## Design

1. **`Skill.limit_counts` / `NoblePhantasm.limit_counts`** — `list[int]`, sorted and
   deduped: the limitCount stages the entry is active in (0–4 ascension, 11+ costume);
   `[]` = ungated. Always present in the JSON output (same precedent as `functions`,
   `targets`, `alternate_forms_id`). Proto3 `repeated int32`: `Skill.limit_counts = 8`
   in common.proto, `NoblePhantasm.limit_counts = 6` in servant.proto (user decision:
   the raw gate list, not a `costume_locked` bool — a bool cannot represent the
   ascension-form gates the game models with the same condType).
2. **Detection** — targeted scan for `condType == "equipWithTargetCostume"`, taking
   `condNum` (strict indexing; always present in observed data). Plain string compare,
   no enum: the file carries many other condTypes (questClear, svtLimit, shopFlagOn,
   dates, …) that stay deliberately uncaptured — same precedent as the uncaptured
   button-level `conds` noted under ActSelectIndex.
3. **Sources** — skills: `skills[].skillSvts[].releaseConditions` (nice_skill entries
   carry no top-level releaseConditions at all). NPs: top-level
   `noblePhantasms[].releaseConditions` **plus** `noblePhantasms[].npSvts[].releaseConditions`
   (top-level alone loses conditions — see raw-data facts).
4. **Semantics documented, not modeled** — conditions OR across skillSvts/npSvts
   entries; within one entry's list, same-`condGroup` conditions are AND'd (observed
   only as costume+questClear pairs, whose questClear half is ignored). `condTargetId`
   is always the servant's own svtId.

## Raw-data facts this rests on (verified in cached `nice_servant.json` and `chaldea-data/dist/baseSkills.json` / `baseTds.json`)

- Condition shape: `{"idx", "condType", "condTargetId", "condNum", "condGroup"}`.
  `condNum` is the required limitCount ("display limitCount" per chaldea-center/chaldea
  `skill.dart`); costumes occupy limitCounts 11+; `condTargetId` is the servant's own id.
- Affected servants in JP data — exact expected unions after the scan:
  - Mash 800100 — skills 459550→[12,13], 460250→[12,13,18], 457000→[12,13],
    744450→[12,13,18], 2162350→[12,13,18], 970660→[19], 2476450→[17,19,20],
    2550→[17,20], 133550→[17,19,20]; NPs 800105→[12,13], 800106→[12,13],
    800107→[17,20], 800196→[18], 800197→[19].
  - Melusine 304800 — skill 888575→[3,13] (two equip conditions, condGroup 0 vs 1);
    NP 304802→[3,13].
  - Ptolemaîos 205000 — skill 2281675→[3]; NP 205002→[3].
  - Elisabeth Báthory 306200 — NPs 306202→[3], 306204→[3].
  - U-Olga Marie 4000100 — skills 2512650/2513450/2514650→[3].
- **NP gotcha**: the nice export's top-level `noblePhantasms[].releaseConditions` keeps
  only one condition where `npSvts[]` carries several (Mash 800105/800106 drop condNum
  12; 800107 drops 17). File-wide: 10 equip conditions top-level vs 13 in npSvts —
  npSvts is a superset here, but the scan unions both sources for safety.
- condType histogram in these paths (whole file): skillSvts releaseConditions =
  equipWithTargetCostume 78, questClear 14, svtLimit 2; NP top-level = equip 10,
  questClear 7; NP npSvts = equip 13, questClear 7. Everything else in the file
  (extraPassive, skillAdd, classPassive, overwrites, script) has no
  equipWithTargetCostume at all.
- Ungated entries carry `releaseConditions: []` (skills via every skillSvts entry; NPs
  top-level), so empty-means-ungated is safe. Mystic-code skills have no skillSvts and
  naturally yield `[]`.

## Implementation

1. **Plan file** → `plans/costume-locked-skills-and-nps.md` (this document).
2. **Protos** — common.proto `Skill`: `repeated int32 limit_counts = 8;`;
   servant.proto `NoblePhantasm`: `repeated int32 limit_counts = 6;` with comments;
   regenerate bindings (`uv run python scripts/generate_proto.py`).
3. **`skill.py`** — `Skill` dataclass gains `limit_counts: list[int] =
   field(default_factory=list)`; `Skill.create` gains an explicit `limit_counts`
   keyword param (documented in its Args) passed through to the constructor.
4. **`servant.py`** — `NoblePhantasm` gains the same field.
5. **`pipeline.py`** — module constant `EQUIP_WITH_TARGET_COSTUME` next to
   `PLAYABLE_TYPES`; helper `_equip_costume_limit_counts(release_conditions:
   list[list[dict[str, Any]] | None]) -> list[int]` (union of condNum, sorted);
   `_parse_skills` computes it from `[e.get("releaseConditions") for e in
   raw.get("skillSvts", [])]`; `_build_nps` from `[raw.get("releaseConditions")] +
   [e.get("releaseConditions") for e in raw.get("npSvts", [])]`.
6. **`pb.py`** — `_skill_message` / `_noble_phantasm_message` set `limit_counts`.
7. **Tests** — `test_pipeline.py`: Mash-shaped gated skill (two skillSvts entries with
   {13} and {12} plus a questClear decoy → [12,13]); Melusine-shaped single entry
   ({3, group 0} + {13, group 1}) → [3,13]; ungated skill → []; NP gated via
   npSvts+top-level → [12,13]; NP gated only via top-level; plain NP → [].
   `test_skill.py`: `create_skill` helper passes `limit_counts`; passthrough test.
   `test_pb.py`: fixtures gain `limit_counts=[12,13]` and round-trip asserts including
   the empty default.
8. **Docs** (`docs/fga_data_parser.md`) — new "Form/costume-gated skills and NPs"
   section: mechanism, condNum semantics, affected-servant table, union rule, the
   npSvts-vs-top-level gotcha, and the deliberately uncaptured condTypes; mention
   `limit_counts` in the schema decisions.

## Verify

1. `uv run pytest`
2. `uv run ruff format .` + `uv run ruff check .`
3. Smoke run `uv run fga-data-parser` (JP served from cache; NA downloads) and
   spot-check `servant_data.json` against the expected-union table above; every other
   skill/NP must carry `limit_counts: []`.

## Revision: `SkillLocked` message (2026-10-11, user decision)

Replace the flat `repeated int32 limit_counts` with `repeated SkillLocked locked` so
costume locks and ascension locks are distinguishable instead of bare condNums.

1. **Proto (user-authored, source of truth)** — while this revision was being drawn
   up, common.proto was edited directly by the user and defines
   `message SkillLocked { int32 costume = 1; int32 ascension = 2; }`: exactly one
   side is set, the other reads 0 (unset). `Skill`'s field becomes
   `repeated SkillLocked locked = 8;` (same number, type swap — a deliberate
   breaking change to the unreleased schema). servant.proto `NoblePhantasm` mirrors
   it as `repeated SkillLocked locked = 6;`: NPs need the same differentiation
   (Melusine's NP is gated to ascension 3 OR costume 13; Ptolemaîos and Elisabeth
   NPs are ascension-only). The message is shared between Skill and NoblePhantasm.
2. **Classification** — derived at parse time: limitCount >= 11 fills `costume`,
   0–4 fills `ascension` (verified in the JP export: every costume gate observed is
   11+, every ascension gate is 3). Note: a hypothetical limitCount-0 gate would be
   indistinguishable from unset in the proto; none exists in the data.
3. **Python** — dataclass `SkillLocked(costume, ascension)` in skill.py with
   `int | None` sides (None = not that kind of gate, so JSON shows
   `{"costume": 12, "ascension": null}` instead of a misleading 0); `Skill.locked` /
   `NoblePhantasm.locked: list[SkillLocked]` replace `limit_counts`; `Skill.create`'s
   param renames to `locked`; the pipeline helper renames to `_equip_costume_locks`,
   returning sorted, deduped `SkillLocked`s (dedupe keyed by limit_count); pb.py
   sets only the non-None side (proto3 omits default 0 on the wire anyway).
4. **Tests/docs** — pipeline/skill/pb assertions switch to the structured form
   (Melusine → `[SkillLocked(ascension=3), SkillLocked(costume=13)]`); the docs
   section and the schema-decisions bullet are rewritten to the new shape.

## Notes

- Per AGENTS.md: never commit, never stage — the user reviews and commits.
- Generated `*_pb2.py` / `*_pb2.pyi` stay gitignored; regenerate after any `.proto` change.
- NA export is not locally cached; the parse is region-generic, so NA data flows
  through the same code path (Mash/Melusine/Ptolemaîos exist in NA too).
