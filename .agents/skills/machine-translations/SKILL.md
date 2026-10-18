---
name: machine-translations
description: Machine-translate the null regions in fgo-translate's overwrite_translations.json work queue (Fate/Grand Order game text) into cn/tw/na/kr. Use whenever the user says "perform machine translation", asks to fill pending or missing FGO translations, translate the overwrite table, or replace nulls in overwrite_translations.json with translations.
---

# Machine-translate the fgo-translate overwrite work queue

`overwrite_translations.json` is the
committed work queue of the `fgo_translate` build (`src/fgo_translate/`). Every
entry is keyed by the exact JP game text and holds only the regions the
automated build (Atlas cross-referencing + Chaldea mappings) could not
translate, as `null`. Filling a null makes the next `fgo-translate` run apply
it to the real table (`fgo_translate.json` / `.pb`) and prune the entry.

If there is no `overwrite_translations.json` in the current repo root, this
skill does not apply — say so and stop.

```json
{
    "translations": {
        "<JP game text>": {"cn": null, "tw": null, "kr": null, "na": null}
    }
}
```

Your job: replace every `null` region value with a translation of the entry's
key — the key itself is the source text — then write the file back
byte-compatible. Everything else about the file must not change.

## Hard rules

The loader (`fgo_translate.pipeline.load_overwrite_translations`) fails the
whole `fgo-translate` run on structural mistakes, and that run gates the daily
release. So:

1. Only translate. Never modify existing non-null values, never add, remove,
   or rename entries or keys, never reorder the file.
2. Region keys are exactly `cn`, `tw`, `na`, `kr`. Never add a `jp` region —
   the dict key is the JP text.
3. Values must be non-empty strings. An empty string fails the loader; if an
   entry truly cannot be translated, leave that region `null`.
4. Preserve everything structural inside a translation:
   - `[servantName 1000100]`-style placeholders and `[{0}]`-style slots stay
     byte-identical and in place.
   - Newlines (keys may end in `\n`), `＆`, `＋`, `【】`, `（）`, `%`, and numbers.
5. Never commit or push — the user commits, and the release workflow also
   commits this file (see the repo's AGENTS.md).

## Translation conventions

This is Fate/Grand Order text: servant / craft-essence / mystic-code / skill /
noble-Phantasm / buff names and descriptions. Prefer the official server
localization where you know it; otherwise follow the style already present in
the built table (`fgo_translate.json`, also in the repo root — 10k+ reference
entries). Observed conventions, match them:

- **na** (English, official FGO NA phrasing): "Increase all allies' Buster
  Card effectiveness by 20% & decrease Debuff Resist by 20% [Demerit]" —
  `【デメリット】` becomes `[Demerit]`, effects use "Increase/Decrease ... by N%".
- **cn** (Simplified, Chaldea community style): card types are 力指令卡
  (Buster) / 迅指令卡 (Quick) / 技指令卡 (Arts); halfwidth commas; `＆` kept;
  性能提升 / 降低 for up / down.
- **tw** (Traditional, Chaldea community style): card types stay English —
  Buster指令卡 / Quick指令卡 / Arts指令卡; fullwidth punctuation; 提升 / 下降.
- **kr** (Korean, KR server style).
- If the key itself is already English (rare, e.g. "Breaching", "December
  23rd"), `na` is the key verbatim and cn/tw/kr translate it.
- Confident official names (servants, skills, events) beat literal
  translations in every region.

Consistency across the run matters more than any single entry: recurring
boilerplate (特攻, クリティカル威力, NP獲得量, ターゲット集中, スター獲得,
被ダメージ時, ...) must render identically everywhere. Build the glossary
first (step 2) and reuse it verbatim in every batch.

## Procedure

1. **Inventory.** Load the file with Python and report: total entries and
   nulls per region (cn / tw / na / kr). This sets the batch plan.
2. **Glossary.** Skim `fgo_translate.json` for entries sharing this run's
   boilerplate and record how each recurring term renders in cn/tw/na/kr
   (aim for 20–40 terms). Note the placeholder rule from the hard rules in it.
3. **Translate.**
   - Small run (≈40 nulls or fewer): translate inline, no subagents.
   - Larger run: fan out general-purpose subagents in parallel, 40–60 entries
     each. Give every agent: its slice as `key -> {region: null}` pairs, the
     glossary, the hard rules and conventions above, and require strict JSON
     back: `{"<key>": {"na": "...", ...}}` containing only filled regions.
     Nothing skipped silently — an untranslatable entry comes back with the
     region still `null` and is listed in the report.
4. **Apply.** Merge with Python so the byte format stays exactly the
   pipeline's own writer (orjson, 2-space indent, sorted keys as-is):

   ```python
   import json, orjson
   from pathlib import Path

   path = Path("overwrite_translations.json")
   raw = path.read_bytes()
   data = json.loads(raw)
   fills = {}  # {"<key>": {"na": "...", ...}} from the batches
   table = data["translations"]
   applied = 0
   for key, regions in fills.items():
       for region, value in regions.items():
           if value and table.get(key, {}).get(region) is None:
               table[key][region] = value
               applied += 1
   path.write_bytes(
       orjson.dumps(data, option=orjson.OPT_INDENT_2)
       + (b"\n" if raw.endswith(b"\n") else b"")
   )
   print("applied", applied)
   ```

5. **Validate.** The repo's own loader must accept the file:

   ```bash
   uv run python -c "from pathlib import Path; from fgo_translate.pipeline import load_overwrite_translations; t = load_overwrite_translations(Path('overwrite_translations.json')); print(len(t), 'entries ok')"
   ```

   Then check `git diff overwrite_translations.json`: only `null` -> string
   transitions may appear. Any other change (key, entry, value, ordering,
   formatting noise) must be fixed before reporting.

6. **Report.** Entries processed, regions filled per language, regions still
   `null` and why. Mention that `uv run fgo-translate` applies the fills and
   prunes completed entries on its next run (needs network + `chaldea-data/`);
   do not run it unless asked.
