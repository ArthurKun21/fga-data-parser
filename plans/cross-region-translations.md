# Cross-region translations from Atlas exports

## Problem

Every text field in `servant_data.json` / `craft_essence_data.json` / `mystic_code_data.json` is raw JP Atlas text copied verbatim. The `fgo_translate` sidecar is built **only** from Chaldea mappings, keyed by *pristine* JP text — so lookups fail for parser-mutated names (Altria→Artoria, "BB (Summer)", `(Saber)` dedupe suffixes) and Chaldea has coverage gaps (CN ~15.4k, NA ~14.1k of 16.1k entries). Result: consumers of `protos/fga_data_parser` + `protos/translations` get missing or wrong translations.

Fix: fetch the same three Atlas URL templates for all five regions (`export/{JP,CN,TW,KR,NA}/nice_*.json` — verified to exist with localized official text and cross-region-consistent `id`/`collectionNo`), and let `fgo_translate` join them into the sidecar.

## Design decisions

- **Sidecar schema unchanged** — `fgo_translate.proto` untouched; keys stay JP text, `cn/tw/na/kr` values get filled from official regional text.
- **Keys come from the parsed JP outputs** so they match exactly what consumers look up (mutated names included); region values are official regional text aligned per entity/field.
- **Merge policy: Atlas first** — official Atlas regional text wins where that region has the content; Chaldea tables fill gaps; `mappingPatch.json` still wins last (app behavior).
- Skill/CE-skill description values use Atlas' resolved `detail` (level-dependent values filled in, no `[{0}]` placeholders).
- Non-JP regions output **JSON only** (no extra `.pb`); JP keeps current unsuffixed names so the release workflow's four artifacts are unchanged.

## Implementation

### 1. `src/fga_data_parser` — multi-region fetch & parse

- `cli.py`: `REGIONS = ("JP", "CN", "TW", "KR", "NA")`; replace `--region` with `--regions` (nargs `"*"`, choices=REGIONS, default all five). Loop regions, JP first.
- Naming: JP keeps `nice_servant.json` cache and `servant_data.json`/`.pb` outputs (compat); other regions write `nice_servant.{region}.json` caches and `servant_data.{region}.json` (lowercase region, JSON only, no `.pb`). Same pattern for mystic codes and craft essences.
- `pipeline.py`: `build_servants(...)` gains a `region` param; `_fix_name` / `_dedupe_name` apply **only for JP** — regional values must stay official text (e.g. NA "Altria Pendragon" must not be renamed or suffixed).

### 2. `src/fgo_translate` — Atlas-derived join

- New `fgo_translate/atlas.py`: `build_atlas_translations(data_dir) -> dict[str, Translation]`:
  - Reads `servant_data.json` + `servant_data.{cn,tw,kr,na}.json`, same for craft essences and mystic codes (missing files → skip that region with a log).
  - Alignment: servants & CEs by `collection_no`, mystic codes by `id`; skills/append passives/CE skills by `id` with `(num, order)` fallback; NPs by `num`; ScriptFunction payloads by skill id + function index.
  - Extracts every text field the parser emits: `Servant.name`; `NoblePhantasm.name`; `Skill.name/detail`; `AppendPassiveSkill.name/original_name/detail`; CE `name/original_name` + CE skill `name/original_name/detail`; MC `name` + MC skill `name/detail`; choice2/3 `detail/optionA/B/C`; np2/np3 `detail` + options.
  - Key = existing `_normalize_text` (PUA table); **middle-dot alias**: entries containing `･`/`・` are additionally registered under the other form (fill-only) so Chaldea keys and Atlas keys unify without breaking consumers.
- `pipeline.py`: `build_translations(chaldea_dir, atlas_dir=None)` merges per policy (Atlas wins over Chaldea tables, then patch wins last); log per-region coverage counts.
- `cli.py`: new `--atlas-data DIR` (default cwd); missing parsed outputs → Chaldea-only run (backwards compatible).

### 3. Tests (pytest, synthetic fixtures in tmp_path, no network)

- `fgo_translate`: cross-region alignment (incl. id-missing fallback, absent entity/region), choice/np2/np3 payload alignment, mutated JP keys preserved, PUA + dot aliases, placeholder retention, merge precedence incl. patch-wins-last.
- `fga_data_parser`: region-suffixed output naming; `build_servants(region="NA")` skips JP name fixes; CLI loop writes per-region files from pre-cached raw fixtures (monkeypatch `download_data`).

### 4. Docs

- `docs/fgo_translate.md`: Atlas-derived source, merge policy, coverage report, dot-alias note.
- `docs/fga_data_parser.md`: multi-region defaults, output naming, region-gated name fixes.

### 5. CI

- `release.yml` needs **no changes**: the default parser run now fetches all five regions before `fgo-translate`, and the four published artifacts keep their names (`fgo_translate.pb` just becomes complete). Note the heavier parse step (~300 MB of downloads).

## Verification

- `uv run pytest`, `uv run ruff check`, `uv run ruff format --check .`
- Run `uv run fga-data-parser` then `uv run fgo-translate` locally; spot-check: `アルトリア・ペンドラゴン` resolves with an NA value; a `[{0}]`-placeholder skill detail key resolves for CN/TW/KR/NA; mystic code 1 name; coverage counts per region vs the Chaldea-only baseline.

---

# Follow-up: prune keys unused by the parser outputs

The merged table still carries Chaldea rows the parser data never shows:
buff names/details, noble Phantasm details, enemy/NPC names, rows for skills
the parser dropped, and so on. Those keys only bloat `fgo_translate.json`/`.pb`
— the sidecar exists to translate the three data files. `fgo_translate` now
prunes the final table to the JP texts that actually appear in
`servant_data.json`, `mystic_code_data.json` and `craft_essence_data.json`.

## Design decisions

- **"Used" = any string value in the three JP outputs.** Table keys are JP
  game text; the remaining string leaves (icon URLs, `class_name`, `flag`,
  `card_type`, ...) never collide with table keys, so scanning every string
  value is a safe superset that needs no field list and stays correct when the
  parser grows new text fields. Values are PUA-normalized like the keys.
- **Prune after the middle-dot aliasing.** Aliases exist to unify the merge
  across the two dot spellings; they are glue, not output, so the non-parser
  spelling is pruned away and only the spelling the data files use survives.
- **Chaldea rows for used texts survive.** A JP-only servant is in
  `servant_data.json` but has no regional parsed data; its community
  translation from Chaldea is exactly what the table must keep.
- **No parsed outputs -> no pruning.** The Chaldea-only fallback keeps its
  full table (`atlas.collect_used_texts` returns `None` and
  `build_translations` skips the filter).
- **Consequence, accepted:** text the parser does not emit (buff texts, noble
  Phantasm details) leaves the sidecar unless a data file references it (e.g.
  a buff detail used as a choice-button fallback). Bringing those back means
  emitting them from the parser, not loosening the prune.

## Implementation

1. `fgo_translate/atlas.py`: `collect_used_texts(data_dir) -> set[str] | None`
   — recursive string scan of the three JP outputs (shared `_PARSED_STEMS`
   constant with `build_atlas_entries`), normalized; `None` when no parsed
   outputs exist.
2. `fgo_translate/pipeline.py`: `build_translations(..., used_texts=None)` —
   filters the merged map after alias registration, logs the dropped count
   before the coverage report.
3. `fgo_translate/cli.py`: pass `collect_used_texts(args.atlas_data)` through.
4. Tests: collection (used texts, `None` when missing), pruning keeps used
   Chaldea-only rows and drops unused ones plus alias spellings, CLI prunes
   end-to-end; unpruned behavior unchanged when `used_texts` is `None`.
5. Docs/README: the table covers exactly the texts in the parser's data
   files; buff/NP-detail note moves to future ideas.

## Verification (follow-up)

- `uv run pytest`, `uv run ruff check`, `uv run ruff format --check .`
- Re-run `uv run fgo-translate` against the existing parsed outputs: every
  remaining key must be present in the three data files, Chaldea-only rows for
  used texts (JP-only servants) must survive, buff/td-detail rows must be
  gone, and the pb must shrink accordingly.
