# fgo_translate — how it works and why

`src/fgo_translate` builds a flat JP-text -> translated-text table covering
exactly the JP texts that appear in the parser's data files
(`servant_data.json`, `mystic_code_data.json`, `craft_essence_data.json`).
Two sources merge into it:

- **Cross-referenced Atlas text** (`atlas.py`): the parser's own per-region
  outputs paired up entity-by-entity, giving the *official* game text of every
  region (CN/TW/KR/NA) for each JP string.
- **The public name mappings of the [Chaldea](https://github.com/chaldea-center/chaldea)
  app**, which fill the gaps Atlas cannot cover (community translations for
  content a region has not received yet, JP-only entities).

Output is `fgo_translate.json` (human-readable) then `fgo_translate.pb` (a
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

## Cross-referenced Atlas text

`fga-data-parser` fetches all five regions (`--regions`, default JP/CN/TW/KR/NA)
and writes parsed JSON per region: JP keeps the unsuffixed names
(`servant_data.json`), other regions get a lowercase suffix
(`servant_data.na.json`, JSON only, no `.pb`). `atlas.build_atlas_entries`
pairs those outputs up:

- Servants, craft essences and mystic codes align by `id` first (Atlas ids
  are shared across regions and unique within one), falling back to the
  collection number for entities the other region still hosts under a
  different id — but `collection_no` 0 never pairs: "unnumbered" is shared by
  many distinct servants (Francesca Prelati, Aozaki Aoko, ...), and pairing on
  it once translated every unnumbered JP servant as Aozaki Aoko. Skills /
  append passives / CE skills match by id first too, falling back to `num` +
  list order for id spaces that are not (mystic code skills). Script-function
  payloads (choice popups, NP type updates) align by function position.
- The **keys are the exact JP texts in the parser's JP output** — FGA-facing
  renames (Altria -> Artoria), "BB (Summer)", and dedupe suffixes like
  "Same Name (saber)" included — so a consumer that looks up the text it read
  from the parser data always hits the table. The parser only applies those
  fixes for JP (`build_servants(region=...)`); regional outputs keep their
  official text because it becomes the table's values.
- Descriptions are Atlas' resolved `detail` (level-dependent values filled
  in), not the templated `unmodifiedDetail`.
- A region that has not received an entity or skill yet simply contributes no
  value for it — the Chaldea mappings may still fill it (community
  translations for JP-only content).

## Our design decisions

- **One flat `map<string, TranslationProto>`** keyed by JP text, exactly as
  specified: it covers names, skills, NPs, buffs, and any future text kind
  with a single lookup, and Chaldea's per-table fallback chains collapse into
  it naturally (all tables share one namespace).
- **Merge policy — Atlas first**: official regional text from the parser's
  outputs wins where present; the Chaldea tables only *fill missing regions*
  (and add keys Atlas cannot cover); the patch is merged last and *wins*, like
  the app's deep merge. Within one source, the first writer of a key claims a
  region and later writers only fill gaps. Patch sections outside
  `TABLE_NAMES` are ignored.
- **Middle-dot aliases**: the parser keeps Atlas' halfwidth katakana middle
  dot (`魔術礼装･カルデア`) while Chaldea keys use the fullwidth `・`; every
  entry is registered under both spellings (fill-only) so one lookup key
  covers consumers written against either source.
- **Pruned to the parser's texts**: the final table keeps only keys that
  appear in the three data files (any string value counts; the remaining
  leaves — icon URLs, class ids, flags — never collide with table keys).
  Chaldea rows for used texts survive (JP-only servants have no regional data
  and rely on Chaldea's community translations), while buff texts and noble
  Phantasm details the parser does not emit are dropped. Chaldea `skill_detail`
  rows drop too unless a description has no level scaling: their keys are the
  templated `[{0}]` texts while parser descriptions are the resolved `detail`
  field, so the two only coincide without placeholders. Without parsed
  outputs nothing is pruned (Chaldea-only fallback keeps its full table).
- **Faithful output**: regions without any translation are omitted from the
  JSON and left unset (empty string) in the pb. Consumers implement the
  fallback themselves: first non-null region in their priority order, else
  `jp`. (JP is always present; it equals the key.) Build-time coverage counts
  per region are logged for spotting regressions.
- The tool needs a **chaldea-data checkout** (`--chaldea-data`) and, for the
  Atlas-derived source, the **parser's per-region outputs** (`--atlas-data`,
  default: current directory). Missing parsed outputs degrade gracefully to a
  Chaldea-only table. `chaldea-data/` is gitignored and must never be
  committed.

## Consumer recipe

```python
entry = translations.get(jp) or translations.get(jp.replace("･", "・"))
name = entry.na if entry and entry.na else jp   # per your region priority
```

Both middle-dot spellings resolve to the same translation; the retry is only
belt-and-suspenders for tables built before aliasing existed.

## Future ideas

- **More tables**: `quest_names`, `event_names`, `item_names`,
  `costume_names`, `cc_names`, `summon_names`, `func_popuptext`, ... are all
  the same shape — add one line to `TABLE_NAMES`.
- **Collision policy**: if a JP key ever appears in two tables with conflicting
  region values, the first writer wins and others only fill gaps. If that ever
  produces a wrong translation, consider emitting per-table maps instead.
- **Resolved output variant**: an option that pre-fills every region with the
  priority-resolved name (no fallback logic for consumers) if wanted.
- **Buff and NP-detail translations**: the parser does not emit buff texts or
  noble Phantasm details, so pruning drops them from the sidecar; emitting
  those fields from the parser would bring them back through the same
  cross-referencing.
