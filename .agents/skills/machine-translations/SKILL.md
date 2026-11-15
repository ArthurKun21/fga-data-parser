---
name: machine-translations
description: Machine-translate the null regions in fgo-translate's overwrite_translations.json work queue (Fate/Grand Order game text) into cn/tw/na/kr. Use whenever the user says "perform machine translation", asks to fill pending or missing FGO translations, translate the overwrite table, or replace nulls in overwrite_translations.json with translations.
---

# Machine-translate the fgo-translate overwrite work queue

`overwrite_translations.json` is the committed work queue of the
`fgo_translate` build (`src/fgo_translate/`). Every entry is keyed by the exact
JP game text and holds only the regions the automated build (Atlas
cross-referencing + Chaldea mappings) could not translate, as `null`. Filling a
null makes the next `fgo-translate` run apply it to the real table
(`fgo_translate.json` / `.pb`) and prune the entry.

If there is no `overwrite_translations.json` in the current repo root, this
skill does not apply — say so and stop.

```json
{
    "translations": {
        "<JP game text>": {"cn": null, "tw": null, "na": null, "kr": null}
    }
}
```

Your job: replace every `null` region value with a translation of the entry's
key — the key itself is the source text. Everything else about the file must
not change. The bundled scripts enforce the file's byte format (orjson 2-space
indent, newline-terminated, sorted top-level keys, `cn/tw/na/kr` region order
per entry) — never hand-edit the JSON; fill through `scripts/apply.py`.

## Available scripts

Bundled in this skill's `scripts/`; run all of them from the repo root with
`uv run`. Each prints its result as JSON on stdout; diagnostics go to stderr.
Shared exit codes: `0` success, `1` rejections or validation failures (listed
in the JSON), `2` usage errors, `3` structurally invalid work queue.
`inventory.py` and `apply.py` use only the standard library (byte parity with
the pipeline's writer is asserted by validate.py); `validate.py` imports the
repo's own pipeline code, so it needs the repo environment.

- **`scripts/inventory.py`** — read-only census: total entries, nulls per
  region, pending entries; `--slices N [--slices-dir DIR]` writes fan-out work
  units; `--snapshot PATH` copies the pre-state bytes.
- **`scripts/apply.py`** — merges a fills JSON into the queue
  (`--fills FILE|-`, `--dry-run`, `--backup PATH`). Fills only null regions;
  never touches existing values, never adds, removes, or reorders entries;
  writes byte-compatible with the pipeline's own writer.
- **`scripts/validate.py`** — the authoritative gate: the repo loader must
  accept the file, the bytes must equal what the pipeline writer produces, and
  with `--baseline PATH` only `null` → string transitions may differ from the
  pre-apply snapshot.

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

1. **Inventory.** Run the census script and read its JSON summary — total
   entries and nulls per region (cn / tw / na / kr) set the batch plan:

   ```bash
   uv run .agents/skills/machine-translations/scripts/inventory.py
   ```

   For a larger run, add `--slices <number of agents> --slices-dir <dir>`:
   each slice file holds one agent's `key -> {region: null}` work unit, already
   in the fills format of step 3.

2. **Glossary.** Skim `fgo_translate.json` for entries sharing this run's
   boilerplate and record how each recurring term renders in cn/tw/na/kr
   (aim for 20–40 terms). Note the placeholder rule from the hard rules in it.

3. **Translate.**
   - Small run (≈40 nulls or fewer): translate inline, no subagents, and write
     the fills JSON yourself.
   - Larger run: fan out general-purpose subagents in parallel, one slice file
     each (pass the slice's contents). Give every agent: the glossary, the
     hard rules and conventions above, and require strict JSON back:
     `{"<key>": {"na": "...", ...}}` containing only filled regions. Nothing
     skipped silently — an untranslatable entry comes back with the region
     still `null` and is listed in the report.
   Merge every batch into a single fills file before applying.

4. **Apply.** Preview first, then write — the real run also snapshots the
   pre-apply bytes for validation:

   ```bash
   uv run .agents/skills/machine-translations/scripts/apply.py --fills fills.json --dry-run
   backup="$(mktemp -d)/before.json"
   uv run .agents/skills/machine-translations/scripts/apply.py --fills fills.json --backup "$backup"
   ```

   A non-zero exit lists rejected fills (unknown key, region not pending for
   the key) or conflicts (fill differs from an existing value). Fix or drop
   them and re-run — the script never overwrites an existing value.

5. **Validate.** The repo's own loader must accept the file, the bytes must be
   exactly what the pipeline writer produces, and against the pre-apply
   snapshot only `null` → string transitions may appear:

   ```bash
   uv run .agents/skills/machine-translations/scripts/validate.py --baseline "$backup"
   ```

   As a last sanity check, `git diff overwrite_translations.json` should show
   only null → string lines; fix anything else before reporting.

6. **Report.** Entries processed, regions filled per language, regions still
   `null` and why — cite the scripts' JSON summaries. Mention that
   `uv run fgo-translate` applies the fills and prunes completed entries on its
   next run (needs network + `chaldea-data/`); do not run it unless asked.
