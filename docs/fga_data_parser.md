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

The CLI caches the raw Atlas exports next to the outputs (`--output-dir`,
default cwd) and reuses them unless `--force` is passed. Both entry points are
console scripts: `fga-data-parser` and `fgo-translate`.

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

### Name fixes and dedupe

`_fix_name` applies FGA-facing renames (Altria→Artoria, BB (Summer),
Kishinami Hakunon, Ereshkigal (Summer)). These match the JP export's name
strings; if NA-region parsing is ever added, revisit them (NA names are
already localized). Duplicate names get ` (<class>)` suffixes with a counter
loop so output names are guaranteed unique — exercised by real data (Flora in
two classes).

## Schema decisions

- **Output keys are snake_case and id-stable** (`nps`, `collection_no`,
  `target_ascension`, ...). This was a deliberate breaking change from the
  original camelCase shape; anything downstream consumes the new schema.
- **Protobuf enums are nested in their messages** (`Servant.ServantFlag`,
  `Skill.SkillTarget`, `NoblePhantasm.CardType`): proto enum values share
  package scope (C++ scoping rules), so two top-level enums both containing
  `Normal` collide. Nesting also lets value names mirror the Python StrEnum
  member names, making conversion a plain `Value(member.name)` lookup. Each
  nested enum has `UNSPECIFIED = 0` for proto3's zero value.
- **`Skill.buttons`** (`list[list[str]]`) is wrapped in a `StringList` message
  (protobuf has no repeated repeated).
- **`TransformDetail.target_ascension`** is `optional int32` so "unknown"
  round-trips as unset rather than a fake `0`.
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

- **NA region output**: `--region NA` already builds the URLs; name fixes and
  translations need revisiting for English names (see above).
- **Ascension overwrite names**: `ascensionAdd.overWriteServantName` and
  battle names are not captured; FGA battle scripts may want them.
- **Skill cooldown edge**: `max(cooldown, default=0)` currently guards empty
  lists; if FGA cares about per-level cooldowns, the raw list could be kept.
- **`transformGroup`** currently only appears in `faces`; the field is on all
  four asset groups and will capture it elsewhere automatically if Atlas adds
  it.
- **Command codes / other entity types** ( Atlas also exports
  `nice_command_code.json`) would follow the same pattern if needed.
