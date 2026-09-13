# fgo_translate — how it works and why

`src/fgo_translate` builds a flat JP-text -> translated-text table from the
public name mappings of the [Chaldea](https://github.com/chaldea-center/chaldea)
app, covering servant/CE/mystic-code names, skill names and descriptions,
noble Phantasm names and descriptions, and buff texts. Output is
`fgo_translate.json` (human-readable) then `fgo_translate.pb` (a
`FgoTranslate` message), same pattern as fga_data_parser.

## How Chaldea's translation system actually works

Researched from `chaldea-center/chaldea-data` (the published data artifact) and
`chaldea-center/chaldea` (the Flutter app). Key facts:

- **Mapping tables are keyed by the Atlas JP text**, not by entity id. Values
  hold exactly five region keys — `JP`, `CN`, `TW`, `NA`, `KR` — where `JP` is
  always `null` in the raw JSON (the key itself is the JP name; the app
  restores it at load). There is no `en` key: the English game region is `NA`.
- The tables this tool folds in: `svt_names`, `entity_names` (enemies/NPCs),
  `ce_names`, `mc_names`, `skill_names`, `skill_detail`, `td_names` (noble
  Phantasm names), `td_detail`, `buff_names`, `buff_detail`. All live in
  `mappings/` of chaldea-data and use the same value schema.
- `skill_detail` / `td_detail` keys are the raw templated JP texts (with
  `[{0}]` placeholders), matching Atlas skill/NP description templates — so
  consumers can look descriptions up directly from Atlas data.
- The app downloads sharded copies from `data.chaldea.center`
  (`mappingData.1-3.json` = all `mappings/*.json` merged, then
  `mappingPatch.json` deep-merged on top with patch values winning) and
  normalizes private-use characters in every file: `\ue000` -> `{jin}`
  (spoiler "神"), `\ue001` -> 鯖, `\ue002` -> 辿, `\ue00b` -> 槌,
  `\ue003`-`\ue00a` -> ▓. Our pipeline reproduces this normalization on keys,
  values, and the merge, so keys match regardless of source form.
- App-side resolution (for reference, `lib/models/gamedata/mappings.dart`):
  servants try `svtNames -> entityNames -> ceNames`, retrying with the
  fullwidth middle dot (`･` -> `・`); CEs and mystic codes are single-table
  lookups; the chosen value is the first non-null region in the user's
  priority order, falling back to the JP name.
- chaldea-data is a machine-published artifact repo (single squashed commit by
  github-actions); the generator that scrapes MoonCell/Fandom/Atlas is private.
  `override_mappings.json` is already merged upstream into `mappings/`, so we
  ignore it; `dist/mappingPatch.json` we merge ourselves because the app does.

## Our design decisions

- **One flat `map<string, TranslationProto>`** keyed by JP text, exactly as
  specified: it covers names, skills, NPs, buffs, and any future text kind
  with a single lookup, and Chaldea's per-table fallback chains collapse into
  it naturally (all tables share one namespace).
- **Merge policy**: tables are processed in `TABLE_NAMES` order; the first
  table to claim a JP key sets its regions and later tables only *fill
  missing regions* (never overwrite). The patch is merged last and *wins*.
  Patch sections outside `TABLE_NAMES` are ignored.
- **Faithful output**: regions without a Chaldea translation are omitted from
  the JSON and left unset (empty string) in the pb — matching Chaldea's own
  dist files. Consumers implement the fallback themselves: first non-null
  region in their priority order, else `jp`. (JP is always present; it equals
  the key.)
- The tool needs **only a chaldea-data checkout** (`--chaldea-data`), not the
  Atlas caches — the table is self-contained. The release workflow checks the
  repo out with `fetch-depth: 1` into `chaldea-data/`, which is gitignored and
  must never be committed.

## Consumer recipe (app-identical lookup)

```python
entry = translations.get(jp) or translations.get(jp.replace("･", "・"))
name = entry.na if entry and entry.na else jp   # per your region priority
```

## Future ideas

- **More tables**: `quest_names`, `event_names`, `item_names`,
  `costume_names`, `cc_names`, `summon_names`, `func_popuptext`, ... are all
  the same shape — add one line to `TABLE_NAMES`.
- **Collision policy**: if a JP key ever appears in two tables with conflicting
  region values, the first table wins and others only fill gaps. If that ever
  produces a wrong translation, consider emitting per-table maps instead.
- **Resolved output variant**: an option that pre-fills every region with the
  priority-resolved name (no fallback logic for consumers) if wanted.
- **Coverage report**: the release workflow could log how many entries carry
  each region (at build time: CN ~15.4k, TW ~14.7k, NA ~14.1k, KR ~13.4k of
  16.1k entries) to spot regressions in upstream data.
- **Validation against Atlas**: NA/KR columns could be cross-checked against
  Atlas `nice/NA` exports since those names are officially localized.
