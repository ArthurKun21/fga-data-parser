# fga_data_parser — how it works and why

`src/fga_data_parser` converts raw Fate/Grand Order data from the Atlas Academy
API into data files (JSON for humans, protobuf for applications) that FGA
tooling consumes. This document records the data-format knowledge and design
decisions discovered while building it, plus ideas for future work.

## Data flow

```
Atlas Academy API (export/{region}/nice_servant|nice_mystic_code|nice_equip.json)
  -> download_data (httpx stream -> temp file -> atomic rename, 3 retries)
  -> read_data (orjson)
  -> pipeline.build_* (raw dicts -> dataclass models)
  -> write_data (JSON, orjson OPT_INDENT_2) + write_bytes (protobuf, deterministic)
```

The CLI fetches every region by default (`--regions`, default
JP/CN/TW/KR/NA) and caches the raw Atlas exports next to the outputs
(`--output-dir`, default cwd), reusing them unless `--force` is passed. JP
keeps the primary unsuffixed file names and the `.pb` outputs; other regions
write `.{region}`-suffixed JSON only, which feed the translation join in
fgo-translate (see docs/fgo_translate.md). Both entry points are console
scripts: `fga-data-parser` and `fgo-translate`.

## Atlas data-format knowledge (hard-won, do not re-derive)

### Noble Phantasm card encoding changed to numeric IDs

Atlas used to encode NP `card` as `"buster"|"arts"|"quick"`; it now emits the
game's internal IDs as strings. Confirmed four ways (Artoria's Excalibur NP has
`"card":"2"`, plus three servants' deck arrays):

- **1 = Arts, 2 = Buster, 3 = Quick**

`CardType.from_atlas()` accepts both encodings and raises on anything else.
If Atlas ever changes encoding again, the run fails loudly by design.

### Servant flags and the goetia outlier

Servant `flag` is a string with exactly three known values (`normal`,
`ignoreCombineLimitSpecial`, `goetia`), encoded as `ServantFlag`. The
`goetia`-flagged servant (Goetia) is not playable-typed, so it is filtered out
by the playable-type check before flag parsing ever sees it.

### Servant assets

`extraAssets` groups (`charaGraph`, `faces`, `commands`, `status`) each hold
sub-dicts keyed by stage: `ascension` (always), `costume` (when costumes
exist), `transformGroup` (only seen under `faces`, for transform servants like
Prelati — captured as `transform_group` on the shared `ServantAssetGroup`).

**Special case:** servants with `collection_no == 0` (not yet obtainable —
e.g. Prelati, Jekyll & Hyde, Flora, Aozaki Aoko at build time) get an empty
`chara_graph`; all other groups are kept.

### Append passives

`appendPassive` items are `{num, priority, skill, unlockMaterials}`; skill nums
seen are 100–104 (Extra Attack + the three appends). A few servants (e.g. Mash)
have none.

### Mystic code skills

The Atlas export reports `num: 0` for every mystic-code skill (an Atlas bug);
the pipeline uses the skill's position as the number instead
(`_parse_skills(..., num_from_index=True)`).

### Skill script choices

Skills with an interactive selection carry a `script.SelectAddInfo` list — one
`{title, btn: [...]}` item per skill level (always 10 items). Button entries
usually have `{name, conds}`. There is no `detail` key anywhere in the raw
shape, so the `SelectAddInfo` title becomes the choice payload's `detail` and
the btn `name`s become its options (2 → Choice2, 3 → Choice3; other counts are
dropped).

Art-only buttons (servant 2301100 skill 2535550) carry only
`{conds, image, imageUrl}` with no `name` at all. Such a button falls back to
the first buff `detail` of the first function whose `svals[0].ActSelectIndex`
equals its 0-based btn index — the btn position and the ActSelectIndex value
label the same branch (see ActSelectIndex below), so the buff detail describes
what that choice does (e.g. 2301100: 宝具を全体攻撃宝具に変更する /
宝具を単体攻撃宝具に変更する). Buttons that resolve to neither a name nor a
buff detail are dropped.

### transformServant svals

The transform target's servant id lives in `svals[0]["Value"]` — capitalized,
never lowercase — and its ascension in `svals[0]["SetLimitCount"]`. Most
transform skills target the owning servant (Ptolemaios, Melusine); the Prelati
pair (505600/505700) transform into each other. The skill's `priority` (the
ascension its slot belongs to) is not part of the model anymore.

### Command NP type changes

`commandTypeSelfTreasureDevice` functions come as one player-team base plus
2–3 enemy-team variants. The variants' `funcPopupText` values (e.g.
宝具タイプチェンジ：Arts) are the options and the base's `funcPopupText`
(e.g. 宝具タイプチェンジ) the payload detail; buffs are not read for this.
2 options → CommandNPType2, 3 → CommandNPType3, other counts are dropped.

### ActSelectIndex (choice-gated actions)

Functions whose svals carry `ActSelectIndex` only execute when the player picks
the SelectAddInfo choice button with that 0-based index. The value is identical
across all 10 per-level svals entries, only takes 0–2, is always smaller than
the button count, and only appears on skills that have SelectAddInfo. It is
stored per `ScriptFunction` entry (`act_select_index`; unset = unconditional)
— the same transform mechanic can be gated on different buttons for different
servants (the Prelati pair on button 1, 1002100 on button 0), and index 0 is
real data, hence the proto field is `optional int32`. Most gated functions
(44 of 50) are plain buff/NP effects outside this parser's targeting model, so
they are not captured; the choice option names already label each branch.
Button-level `conds` (e.g. Kukulkan's `{"cond": "STAR_HIGHER", "value": 10}`)
gate button availability — a separate mechanism that stays uncaptured.

### Form/costume-gated skills and NPs (releaseConditions)

Skill and NP entries can be pinned to specific servant stages via `releaseConditions`
with `condType: "equipWithTargetCostume"`: the entry only exists while the servant is
in that stage — `condNum` is the required limitCount (0–4 ascensions, 11+ costumes)
and `condTargetId` is the servant's own id. Skills gate exclusively through
`skills[].skillSvts[].releaseConditions` (nice_skill entries carry no top-level
releaseConditions at all); NPs gate through `noblePhantasms[].releaseConditions` and
`noblePhantasms[].npSvts[].releaseConditions`. The parser unions the `condNum` values
of all such conditions into `locked` gate entries — `{"costume": limitCount}` for
costume stages (11+) and `{"ascension": limitCount}` for ascension stages (0–4),
sorted by limitCount, `[]` = ungated — so ungated base kits and gated variants that
share a `num` stay distinguishable by id + gate list.

Semantics: conditions are OR'd across `skillSvts`/`npSvts` entries; within one entry's
list, same-`condGroup` conditions are AND'd — observed only as costume + `questClear`
pairs (Mash's Ordeal Call skills), whose quest-clear half is ignored.
**NP gotcha:** the top-level NP `releaseConditions` drops conditions that `npSvts[]`
still carries (Mash NP 800105 shows only costume 13 top-level; npSvts has {12, 13}),
so both sources must be scanned.

Affected servants in JP data (as of 2026-10): Mash 800100 (9 skills, 5 NPs — Ortenaus/
Paladdin/swimsuit stages 12, 13, 17–20), Melusine 304800 (skill 888575, NP 304802 —
dragon ascension 3 OR costume 13), Ptolemaîos 205000 (skill 2281675, NP 205002 —
ascension 3), Elisabeth Báthory 306200 (NPs 306202/306204 — ascension 3), U-Olga Marie
4000100 (all 3 skills — ascension 3). Deliberately uncaptured: every other
release-condition mechanism — `questClear`/`svtLimit` inside these lists (like the
button `conds` above) and the unrelated `releaseConditions` under `extraPassive`,
`skillAdd`, `classPassive`, `overwrites` and `script.overwriteClassImageId`
(shopFlagOn, dates, exchange types — no `equipWithTargetCostume` there).

### Not-yet-live entries (empty `functions`)

Skills and NPs whose `functions` list is empty are placeholders for entries that are
not live yet — newly released servants ship full kits this way while still locked.
The parser drops them (`_parse_skills`, `_build_nps`) instead of emitting dead
entries. Verified in the JP export: servant 600710's NP 600711 and Mash's base NP
800100 (Lord Chaldeas) are `"functions": []` while their sibling entries carry
functions; 7 such entries existed as of 2026-10. A missing `functions` key counts as
empty too, though the export always includes the key. Mystic-code skills have no
empty entries today, but the filter applies to them through the shared
`_parse_skills` regardless, and their index-based `num` stays contiguous over the
kept skills.

### Noble Phantasm transforms

A handful of NPs swap the servant into an alternate form after firing (Aoko
2501400's 逆行銀河・赤方偏移, Jekyll & Hyde's 密やかなる罪の遊戯 in both its
base and strengthened copies). The mechanism is the same `transformServant`
funcType used by skills, but inside the NP's `functions`; the target id lives
in svals `Value` (NP functions carry five per-level entries plus `svals2`–
`svals5` per-overcharge lists — the value is constant across all of them).
Such NPs are marked in `NoblePhantasm.targets`; unlike `SkillTarget` the
`NoblePhantasmTarget` enum is not UI-facing, so it only carries the transform
value for now.

### Alternate forms

Servants that transform into a *different* servant id are alternate forms:
the skill-based Prelati pair (505600↔505700) and Flora pair (1002000↔1002100),
plus the NP-based Aoko (2501400→2501500) and Jekyll & Hyde (600700→600710)
pairs. Self-transforms (Ptolemaios, Melusine — svals `Value` equals the
servant's own id) are ascension swaps, not alternate forms. The references in
`alternate_forms_id` are written bidirectionally even when the raw data only
transforms one way: the hidden alternate entries all have `collectionNo: 0`
but are `type: normal`, so they are parsed, and 2501500/600710 get synthesized
back-references. Atlas's only dedicated field, `script.transformInfo`
(`saveTransform`/`saveTransformDefault`), exists solely on the Prelati pair
and is not used; `svtChange`/`overwrites` are quest-conditional variants, not
forms.

### Name fixes and dedupe

`_fix_name` applies FGA-facing renames (Altria→Artoria, BB (Summer),
Kishinami Hakunon, Ereshkigal (Summer)). These match the JP export's name
strings and are applied **only when `build_servants` runs with the default
`region="JP"`** — the other regions' outputs feed the translation table as
values (see docs/fgo_translate.md), so their official text must survive
untouched (NA really does ship "Altria"). Duplicate names get ` (<class>)`
suffixes with a counter loop so JP output names are guaranteed unique —
exercised by real data (Flora in two classes); non-JP outputs skip the dedupe
for the same reason.

## Schema decisions

- **Output keys are snake_case and id-stable** (`nps`, `collection_no`,
  `functions`, ...). This was a deliberate breaking change from the
  original camelCase shape; anything downstream consumes the new schema.
- **Skill targeting is a list of `ScriptFunction` entries**, replacing the old
  flat `target` list plus `script_buttons`/`buttons`/`transform` fields. Each
  entry carries one `SkillTarget` and at most one payload (`choice2`,
  `choice3`, `np2`, `np3`, `transform`) as an explicit `optional` message, so
  an entry without a payload round-trips as unset instead of an empty message.
- **Shared types live top-level** (`Skill`, `ScriptFunction` with its payload
  messages, `SkillTarget`, `CardType` in `common.proto`;
  `NoblePhantasmTarget` in `servant.proto`), while single-message flags
  (`Servant.ServantFlag`, `CraftEssence.CraftEssenceFlag`) stay nested in
  their messages.
- **Proto enum values are UPPER_SNAKE_CASE** and mirror the Python StrEnum
  member names, making conversion a plain `Value(member.name)` lookup. StrEnum
  values keep their existing casing so the JSON output is unchanged. Proto
  enum values share package scope (C++ scoping rules), so top-level enums
  prefix colliding value names with their enum name
  (`SKILL_TARGET_UNSPECIFIED`, `CARD_TYPE_UNSPECIFIED`,
  `NOBLE_PHANTASM_TARGET_TRANSFORM`).
- **`TransformDetail`** records the transform target's servant id (`target`,
  from raw svals `Value`) and its ascension (`ascension`, from raw svals
  `SetLimitCount`).
- **`locked` on skills and NPs is a repeated `SkillLocked` message, not a flat
  int list or bool**: the game reuses the `equipWithTargetCostume` condType for
  plain ascension-form gates (Ptolemaîos, Elisabeth, U-Olga Marie), so each gate
  records which side it belongs to (`costume` for stages 11+, `ascension` for
  0–4; the other side is 0/unset — the user-authored proto shape).
- **NPs carry Atlas' resolved `detail`** (level-dependent values already
  filled in; the raw `unmodifiedDetail` keeps the `[{0}]` placeholders and is
  not emitted), mirroring the skill field.
- **Entries with an empty `functions` list are dropped at parse time** — they are
  placeholders for not-yet-released servants, not real kits (see "Not-yet-live
  entries" above). Exclusion happens before model construction, so the models and
  proto schema are unaffected.
- Image dicts are `map<string, string>` — protobuf maps are unordered by
  spec, and serialization uses `SerializeToString(deterministic=True)` so
  output is byte-stable across runs (JSON keeps insertion order; pb does not).
- `option java_package` is set for future Java/Kotlin consumers; it has zero
  effect on the Python codegen (only the embedded descriptor blob changes).

## Robustness rules

- Downloads stream to a temp file and rename atomically; a failed download can
  never poison the cache, and `raise_for_status()` prevents HTTP error bodies
  being cached as data.
- `read_data`/`write_data` propagate exceptions — silent empty outputs are a
  bug class we explicitly removed.
- Enums are strict: an unknown Atlas value raises instead of passing through.
  When that happens, add the member (and a test), do not loosen the parsing.

## Future ideas

- **Ascension overwrite names**: `ascensionAdd.overWriteServantName` and
  battle names are not captured; FGA battle scripts may want them.
- **Skill cooldown edge**: `max(cooldown, default=0)` currently guards empty
  lists; if FGA cares about per-level cooldowns, the raw list could be kept.
- **`transformGroup`** currently only appears in `faces`; the field is on all
  four asset groups and will capture it elsewhere automatically if Atlas adds
  it.
- **Command codes / other entity types** ( Atlas also exports
  `nice_command_code.json`) would follow the same pattern if needed.
