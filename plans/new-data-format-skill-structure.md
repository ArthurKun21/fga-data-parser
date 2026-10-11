# New data format: skill `ScriptFunction` restructure + enum casing

- **Branch:** `feat/new-data-format`
- **Status:** approved plan, ready for implementation
- **Scope:** `src/fga_data_parser/skill.py`, `enums.py`, `pipeline.py`, `pb.py`, `protos/fga_data_parser/*.proto`, `tests/`, `docs/fga_data_parser.md`

## Background

Commit `0ef7f14` redesigned `Skill` in `protos/fga_data_parser/common.proto`: the flat
`target` / `script_buttons` / `buttons` / `transform` fields were replaced by
`repeated ScriptFunction functions` with per-function optional payloads
(`choice2` / `choice3` / `np2` / `np3` / `transform`), and `TransformDetail`
became `{target (servant id), ascension}`. Only the protos changed — the Python
dataclasses, `pb.py`, and tests still use the old shape and break as soon as
the bindings are regenerated (`_skill_message` writes deleted fields;
`_noble_phantasm_message` references the removed nested `NoblePhantasm.CardType` enum).

## Raw-data facts the logic is built on (verified in cached `nice_servant.json`)

- **Choices** — `SelectAddInfo` items are `{title, btn: [{name, conds, (image, imageUrl)}]}`;
  there is **no `detail` key**, so `Choice2/3Detail.detail` maps from `title`, options from
  btn `name`s. Servant 2301100 has image-only buttons → no names → falls back to TargetAll
  (unchanged behavior).
- **Transform** — `transformServant` svals: target servant id under **capitalized `Value`**,
  ascension under `SetLimitCount` (205000 Ptolemaios → own id; 505600/505700 Prelati transform
  into each other). The old `priority`-based source ascension is gone from the model.
- **NP type change (user-confirmed rule)** — options = `funcPopupText` of every
  `commandTypeSelfTreasureDevice` function with `funcTargetTeam == "enemy"`
  (EMIYA 200100 → 2 options, Space Ishtar 1100900 → 3); `detail` = the base (`player`)
  function's `funcPopupText` (e.g. 宝具タイプチェンジ). The old `buffs[0].name` /
  `command_np_found` state machine is deleted.

## Step 1 — Dataclasses first

### `src/fga_data_parser/skill.py`

- Delete `ScriptButton`; rewrite `TransformDetail` → `{target: int, ascension: int}`.
- Add payload dataclasses mirroring the proto 1:1:
  - `Choice2Detail(detail, option_a, option_b)`
  - `Choice3Detail(detail, option_a, option_b, option_c)`
  - `NoblePhantasm2Update(detail, option_a, option_b)`
  - `NoblePhantasm3Update(detail, option_a, option_b, option_c)`
  - `ScriptFunction(target, choice2=None, choice3=None, np2=None, np3=None, transform=None)`
- `Skill` becomes `{id, num, name, detail, icon, cooldown, functions: list[ScriptFunction]}`.
- Rework `Skill.create(id, num, name, detail, icon, cooldown, scripts, functions)`
  (drop the `ascension` param):
  - scripts → `ScriptFunction(target=CHOICE_2/CHOICE_3, choice2/choice3=<detail=title,
    option_a/b/c=named btns>)`; other named-button counts logged + ignored as today.
  - functions → per-target entries in encounter order (`ptOne`→TARGET_ONE,
    `ptselectOneSub`→ORDER_CHANGE); `commandTypeSelfTreasureDevice` with
    `funcTargetTeam=="enemy"` collects `funcPopupText` as options, the non-enemy one
    provides the detail; 2 options → `CommandNPType2` entry with `np2`, 3 → `np3`,
    other counts dropped + debug log.
  - `transformServant` → Transform entry with
    `TransformDetail(target=svals[0]["Value"], ascension=svals[0]["SetLimitCount"])`
    when svals exist, else a bare Transform entry.
  - Default `ScriptFunction(target=TARGET_ALL)` when nothing derived;
    dedupe consecutive same-target entries (payload preserved).

### `src/fga_data_parser/enums.py`

Rename members to UPPER_SNAKE_CASE, **values unchanged** (JSON output casing stays the same):

| Enum | New members (values kept) |
| --- | --- |
| `SkillTarget` | `TARGET_ONE="TargetOne"`, `TARGET_ALL="TargetAll"`, `COMMAND_NP_TYPE_2="CommandNPType2"`, `COMMAND_NP_TYPE_3="CommandNPType3"`, `CHOICE_2="Choice2"`, `CHOICE_3="Choice3"`, `TRANSFORM="Transform"`, `ORDER_CHANGE="OrderChange"` |
| `CardType` | `BUSTER="buster"`, `ARTS="arts"`, `QUICK="quick"` (+ `from_atlas` returns updated) |
| `ServantFlag` | `NORMAL="normal"`, `IGNORE_COMBINE_LIMIT_SPECIAL="ignoreCombineLimitSpecial"`, `GOETIA="goetia"` |
| `CraftEssenceFlag` | `NORMAL`, `SVT_EQUIP_CAMPAIGN`, `SVT_EQUIP_CHOCOLATE`, `SVT_EQUIP_EVENT`, `SVT_EQUIP_EVENT_REWARD`, `SVT_EQUIP_EXP`, `SVT_EQUIP_FRIEND_SHIP`, `SVT_EQUIP_MANA_EXCHANGE`, `UNKNOWN` (Atlas string values kept) |

## Step 2 — Proto enum renames + comment fixes (field numbers untouched)

- `common.proto` `SkillTarget`: `TARGET_ONE, TARGET_ALL, COMMAND_NP_TYPE_2,
  COMMAND_NP_TYPE_3, CHOICE_2, CHOICE_3, TRANSFORM, ORDER_CHANGE`;
  `CardType`: `BUSTER, ARTS, QUICK`.
- `servant.proto` `Servant.ServantFlag`: `NORMAL, IGNORE_COMBINE_LIMIT_SPECIAL, GOETIA`.
- `craft_essence.proto` `CraftEssence.CraftEssenceFlag`: `NORMAL, SVT_EQUIP_*, UNKNOWN`.
- `common.proto` comment fix: `TransformDetail` comment `svals/<N>/value` → `svals/<N>/Value`;
  fix the `CardType` comment's mis-indented second line.

## Step 3 — Regenerate bindings

`uv run python scripts/generate_proto.py` (globs all `protos/fga_data_parser/*.proto` —
no script change needed).

## Step 4 — Proto generation (`src/fga_data_parser/pb.py`)

- `_noble_phantasm_message`: `servant_pb2.NoblePhantasm.CardType` → `common_pb2.CardType`.
- Rewrite `_skill_message` to emit `functions=[...]`; add `_script_function_message`
  setting `target` plus per-payload fields `choice2.detail/optionA/optionB`,
  `choice3.*` (+optionC), `np2.*`, `np3.*`, `transform.target/ascension`
  (generated bindings keep the camelCase field names).
- All enum conversions stay mechanical `.Value(member.name)` — member renames keep them aligned.

## Step 5 — Tests

- `tests/test_skill.py`: rewrite for `ScriptFunction` payloads; `command_np_functions`
  helper becomes base (`funcPopupText`, `funcTargetTeam="player"`) + enemy variants with
  `funcPopupText`; transform tests use `svals=[{"Value": 100100, "SetLimitCount": 3}]`;
  no `ascension` param; renamed enum members throughout.
- `tests/test_pb.py`: `make_skill()` exercises choice2 / TARGET_ONE / np3 / transform
  entries; assertions on `functions[i].target`, payload fields (`optionA`…), `HasField`
  presence; `np.card_type == common_pb2.CardType.BUSTER`; transform-payload-absent test
  replaces the `target_ascension` one.
- `tests/test_pipeline.py`: `skill.target == [TargetAll]` →
  `skill.functions == [ScriptFunction(target=SkillTarget.TARGET_ALL)]`; renamed members.

## Step 6 — Docs

`docs/fga_data_parser.md`: drop the `Skill.buttons`/StringList and
`TransformDetail.target_ascension` schema notes; document the ScriptFunction design;
add the raw-data facts above (SelectAddInfo shape + title→detail, capitalized `Value`,
image-only buttons of servant 2301100, enemy-`funcPopupText` NP options).

## Step 7 — Verify

1. `uv run pytest`
2. `uv run ruff format .`
3. `uv run ruff check .`
4. No-network smoke run `uv run fga-data-parser` on the cached exports, spot-checking output:
   - 203300 Ashwatthaman (choice2, options 無敵/ガッツ)
   - 205000 Ptolemaios (transform target=205000 ascension=3)
   - 505600 → 505700 Prelati (cross-servant transform)
   - 200100 EMIYA (np2 with 2 popup options)
   - 1100900 Space Ishtar (np3 with 3)
   - 2301100 Jade Rabbit (no choice → TargetAll)

## Notes

- Per AGENTS.md: never commit, never stage — the user reviews and commits.
- Generated `*_pb2.py` / `*_pb2.pyi` stay gitignored; regenerate after any `.proto` change.
- **Deviation during implementation:** with both `SkillTarget` and `CardType`
  top-level in `common.proto`, their `UNSPECIFIED = 0` values collide (proto
  enum values share package scope under C++ scoping rules). The zero values
  are prefixed with the enum name (`SKILL_TARGET_UNSPECIFIED`,
  `CARD_TYPE_UNSPECIFIED`) — the standard protobuf fix. Nested enums
  (`ServantFlag`, `CraftEssenceFlag`) keep plain `UNSPECIFIED` since nesting
  scopes them.
