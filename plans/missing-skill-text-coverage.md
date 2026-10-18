# Missing skill-text coverage: popup texts and sourceless keys

## Problem

Consumer reports: skill names, skill details, and the choice2/choice3/np2/np3
popup texts (`skill.py` payload `detail`/`option_a/b/c`) are missing from
`fgo_translate.json`, so the parser data cannot be translated for them.
Verified against the built table (three distinct holes):

1. **Popup texts of region-unaligned skills.** The Atlas cross-reference only
   pairs skills two regions share; for JP-only content (e.g. Francesca
   Prelati) every payload text is unpaired. Their upstream sources are
   consumed by nobody:
   - `chaldea-data/mappings/func_popuptext.json` (flat JP→regions, 415 rows)
     holds the `funcPopupText` strings the parser copies into np2/np3
     payloads (`宝具タイプチェンジ：Arts`, ...).
   - `mappings/misc.json` section `SelectAddInfo` holds the choice2/choice3
     titles and button names (`霊基を入れ替えるか選択してください`,
     `入れ替えない`, ... — present with CN text, absent from the built table).
   Neither file is in `TABLE_NAMES`, and `misc.json` is sectioned, so it
   cannot simply be appended.
2. **Skill details of JP-only skills.** The parser emits Atlas' resolved
   `detail` (`…ダウン(3ターン)`) while Chaldea `skill_detail` keys are the
   templated texts (`…ダウン[{0}](3ターン)`); the two coincide only without
   placeholders (see docs "Our design decisions"), so no Chaldea row matches.
   Example: Prelati's detail is in `skill_detail.json` (templated) and in
   `servant_data.json` (resolved) but in neither source of the built table.
3. **Sourceless texts never reach the work queue.** `apply_overwrite_translations`
   records only keys already in the table; a used-but-sourceless text is
   absent from both `fgo_translate.json` and `overwrite_translations.json`,
   so it can never be translated later.

## Design decisions

- **Consume `func_popuptext` as a regular table.** Same flat schema as the
  other mappings; append to `TABLE_NAMES`. The mapping patch already carries a
  `func_popuptext` section, which the existing patch-win loop picks up
  automatically once the name is a known table.
- **Flatten only the JP-text-keyed `misc.json` sections.** `SelectAddInfo` and
  `selectTreasureDeviceInfo` are keyed by skill popup JP text and merge
  fill-only like any table. The remaining sections are identifier-keyed
  (`$default`, `Function`, `SkillScript`, `condBranchSkillInfo`) or unrelated
  to parser outputs (`TowerName`, `master_name`, `RecipeName`,
  `TradeGoodsName`, `BattlePointName`) and stay out — flattening them would
  seed the table with keys like `"Branch"` or `"ifPrevFuncSucceed"` that are
  not game text. `dist/mappingPatch.json` carries the same `misc` payload, so
  the patch merge flattens it with the same section list and wins last.
- **Every translatable parser text becomes a table key, even without a
  source.** `collect_translatable_texts` walks exactly the fields the
  cross-reference records (names, details, payload texts — never icon URLs,
  enums or ids) in the JP outputs; `build_translations` adds the ones no
  source covered as translation-less entries (`{"jp": ...}` in JSON, unset
  regions in pb). Consumers already fall back to jp, and the keys make the
  table "cover exactly the parser's data files" again — pruning removes
  unused keys, this adds back the used ones no source reached.
- **Sourceless keys flow into the overwrite queue unchanged.** A translation-
  less entry misses all four regions, so the existing record/fill/prune rules
  queue it as `{cn: null, tw: null, na: null, kr: null}` and apply values the
  file already holds. No special casing in the overwrite code.
- **Pruning stays keyed on `collect_used_texts`** (every string leaf): if the
  parser grows a text field the walker does not know yet, its Chaldea rows
  still survive pruning — the walker only gates the additions, so a missed
  field degrades to today's behavior instead of dropping translations.
- **Rejected: resolving Chaldea's templated detail keys via svals.** That
  re-implements Atlas' `[{0}]` substitution for every skill rank — fragile and
  a parser concern, not a translation-merge concern. The overwrite queue is
  the designed path for content no source covers.
- **Rejected: filtering `used_texts` by heuristics** (drop URLs/ASCII) to find
  missing keys — imprecise in both directions; a structured walker is exact.

## Implementation

1. `plans/missing-skill-text-coverage.md` — this document.
2. `src/fgo_translate/pipeline.py`:
   - `TABLE_NAMES` += `"func_popuptext"` (last).
   - `MISC_SECTIONS = ("SelectAddInfo", "selectTreasureDeviceInfo")` + helper
     flattening a misc payload (`mappings/misc.json`, and the patch's `misc`
     section) into `{jp: regions}`; merged fill-only after the tables, the
     patch copy wins last.
   - `build_translations(..., required_texts: set[str] | None = None)`:
     after pruning, add missing required texts as empty entries and log the
     count.
3. `src/fgo_translate/atlas.py`: `collect_translatable_texts(data_dir) ->
   set[str] | None` — walks the JP outputs' translatable fields (reusing
   `_PAYLOAD_FIELDS`; comment ties the field list to the recorders), returns
   `None` when no JP outputs exist (Chaldea-only build, like
   `collect_used_texts`).
4. `src/fgo_translate/cli.py`: pass
   `required_texts=collect_translatable_texts(args.atlas_data)`.
5. `tests/test_fgo_translate.py`: fixture writes `func_popuptext.json` and a
   sectioned `misc.json`; new tests for fill-only merge, unused-section
   exclusion, patch `misc`/`func_popuptext` precedence, jp-only required keys
   queued as all-null entries and filled from the overwrite file, and
   `required_texts=None` adding nothing.
6. `docs/fgo_translate.md`: covered-tables list, misc flattening, key
   inclusion, queue interplay; drop `func_popuptext` from "Future ideas".

## Verification

- `uv run pytest`, `uv run ruff check .`, `uv run ruff format .`.
- `uv run fgo-translate` against the existing parsed outputs +
  `chaldea-data/`: Prelati's choice2 texts present with CN from `misc.json`
  (NA/KR null → queued); the log reports the sourceless keys added;
  `overwrite_translations.json` gains the new null work-queue entries.
