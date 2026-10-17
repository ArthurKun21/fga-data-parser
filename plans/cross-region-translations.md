# Cross-region translations from Atlas exports

## Problem

Every text field in `servant_data.json` / `craft_essence_data.json` / `mystic_code_data.json` is raw JP Atlas text copied verbatim. The `fgo_translate` sidecar is built **only** from Chaldea mappings, keyed by *pristine* JP text — so lookups fail for parser-mutated names (Altria→Artoria, "BB (Summer)", `(Saber)` dedupe suffixes) and Chaldea has coverage gaps (CN ~15.4k, NA ~14.1k of 16.1k entries). Result: consumers of `protos/fga_data_parser` + `protos/translations` get missing or wrong translations.

Fix: fetch the same three Atlas URL templates for all five regions (`export/{JP,CN,TW,KR,NA}/nice_*.json` — verified to exist with localized official text and cross-region-consistent `id`/`collectionNo`), and let `fgo_translate` join them into the sidecar.

## Design decisions

- **Sidecar schema unchanged** — `fgo_translate.proto` untouched; keys stay JP text, `cn/tw/na/kr` values get filled from official regional text.
- **Keys come from the parsed JP outputs** so they match exactly what consumers look up (mutated names included); region values are official regional text aligned per entity/field.
- **Merge policy: Atlas first** — official Atlas regional text wins where that region has the content; Chaldea tables fill gaps; `mappingPatch.json` still wins last (app behavior).
- Skill/CE-skill description values use templated `unmodifiedDetail` (keeps `[{0}]` placeholders, matching Chaldea `skill_detail` conventions).
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
