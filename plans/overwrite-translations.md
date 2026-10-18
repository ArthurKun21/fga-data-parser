# Overwrite translations: manual gap-filler for the sidecar

## Problem

The sidecar table is rebuilt from scratch every run (Atlas cross-reference +
Chaldea mappings + patch), so keys with missing regions stay missing until an
upstream source covers them — and there is no way to supply a translation by
hand. `overwrite_translations.json` is a committed work-queue file in the same
shape as `fgo_translate.json` (`{"translations": {jp: {region: text}}}`, no
`.pb`): every key missing at least one region is recorded in it for manual /
machine translation, and values added there fill the gaps in the main table on
the next run.

## Design decisions

- **Fill-only.** An overwrite value is applied only to a region that is `None`
  in the built table; existing values always win. Corrections to translations
  Chaldea/Atlas already provide are out of scope.
- **Record the work queue, not the diffs.** After filling, a key stays in the
  overwrite file when it still misses a region (entry holds its post-fill known
  values, jp + present regions, giving the translator context) or when a fill
  was applied even if the key is now complete — the table is rebuilt from
  Chaldea every run, so dropping applied values would lose them on the next run.
- **Prune the clutter.** A key leaves the overwrite file when the table entry
  is fully translated without any fill (the overwrite value is redundant), and
  also when the key no longer exists in the table at all (e.g. pruned as unused
  by `collect_used_texts`): such an entry can never fill anything, matching the
  table's "covers exactly the parser's data files" philosophy.
- **Missing file → empty table; malformed → ValueError.** The file is
  hand-edited, so structural mistakes (unknown region key, non-string or empty
  value, missing `translations` wrapper) fail the run loudly with the offending
  key named, like the strict enums do.
- **Output is stable.** Top-level keys are sorted like the main table, inner
  region order comes from `Translation.to_json()` (jp, cn, tw, na, kr), so an
  unchanged run produces no diff and the release workflow's commit step no-ops.
- **The file lives at the repo root** (`--overwrite-translations`, default
  `./overwrite_translations.json`): it is a source-controlled input, not a
  build artifact, so it follows cwd like `--chaldea-data` rather than
  `--output-dir`. `.gitignore` gets a `!overwrite_translations.json` negation
  because `/*.json` would otherwise hide it.
- **Known limitation, accepted:** middle-dot alias keys are separate rows, so
  both spellings of an incomplete entry are recorded and filled independently.
- **No `.pb` for the overwrite file**; the fills flow into the regular
  `fgo_translate.json`/`.pb` consumers already read.

## Implementation

1. `plans/overwrite-translations.md` — this document.
2. `src/fgo_translate/pipeline.py`:
   - `load_overwrite_translations(path) -> dict[str, dict[str, str]]` — `{}`
     when the file is missing; otherwise read via `read_data` and validate
     (see above), raising `ValueError` with the path and offending key.
   - `apply_overwrite_translations(translations, overwrite) -> dict[str,
     dict[str, str]]` — fills missing regions in place (so downstream
     JSON/pb include them), returns the overwrite table to persist per the
     record/prune rules, and logs applied-fill / pending-entry counts.
   - `overwrite_translations_to_json(overwrite) -> dict` — output shape with
     sorted keys.
3. `src/fgo_translate/cli.py`: `--overwrite-translations PATH` (default
   `Path.cwd() / "overwrite_translations.json"`); after `build_translations`,
   load → apply → `write_data` the updated table (always when the file exists
   so it can shrink, on first run only when non-empty), before the main
   outputs are written.
4. `tests/test_fgo_translate.py`: fill missing regions; existing values are
   never overwritten; new/partial entries recorded with post-fill values;
   natively-complete, unknown, and fill-completed-then-redundant keys dropped;
   fill-completed keys kept (persistence regression); loader (missing, valid,
   malformed variants); CLI end-to-end writes both files.
5. `.gitignore`: `!overwrite_translations.json` right after `/*.json`.
6. `.github/workflows/release.yml`: "Commit overwrite translations" step after
   "Translate names" — git config as `github-actions[bot]`, add the file,
   `git diff --cached --quiet` no-op guard, commit
   `chore: update overwrite translations`, push. The `release` job already has
   `contents: write` and persisted checkout credentials, so the push to the
   triggering branch (master for scheduled runs) needs no other change.
7. `docs/fgo_translate.md`: overwrite-table section (purpose, format,
   fill/record/prune rules, CLI flag, workflow commit).

## Verification

- `uv run pytest`, `uv run ruff check .`, `uv run ruff format .`.
- `uv run fgo-translate` against the existing parsed outputs +
  `chaldea-data/`: file created with recorded missing entries; second run
  idempotent (no diff); a hand-added value fills its gap in
  `fgo_translate.json`; `git status` shows the file as trackable.

---

# Follow-up: nulls-only overwrite entries

## Problem

The recorded entries duplicated the main table (jp + every already-present
region value). That bloats the file, and the duplication is never used: fills
only ever target missing regions. The file only needs to say *which* regions
are still missing — and hold the manually provided values once given.

## Design decisions

- **Entry = only the regions missing from the freshly built table**, as
  `null` while unfilled and as the applied value once the overwrite file
  provided one; regions the build already covers are left out entirely. The
  jp text stays the dict key, so the translator still has the source text:

  ```json
  {
      "translations": {
          "key": {
              "kr": null,
              "na": null
          }
      }
  }
  ```

- **"Missing" is judged against the build before fills, not after.** A key
  completed by a fill keeps its applied values instead of collapsing to an
  empty entry — the table is rebuilt from Chaldea every run, so the values
  must survive in the file or the next run loses them. Only keys the build
  itself fully translated (or no longer contains) are pruned.
- **Loading tolerates the previous format** (jp echo + known values) so the
  first run after this change rewrites the file in place with no manual
  migration; the jp echo is ignored because the key is the jp text. Unknown
  region keys, non-string values, and empty strings still fail loudly.
- Write path, CLI flag, and the release-workflow commit are unchanged.

## Implementation

1. `src/fgo_translate/pipeline.py`: `load_overwrite_translations` accepts
   `null` region values and ignores a legacy `jp` echo;
   `apply_overwrite_translations` tracks the natively-missing regions per key
   and persists them as value-or-null (no more post-fill `to_json()` of known
   values); `overwrite_translations_to_json` only gains the `str | None`
   value type.
2. `tests/test_fgo_translate.py`: updated to the nulls-only expectations plus
   a legacy-format loading test.
3. `docs/fgo_translate.md`: overwrite section reflects the nulls-only shape.

## Verification (follow-up)

- `uv run pytest`, `uv run ruff check .`, `uv run ruff format .`
- Local run against the existing outputs: the old-format file is rewritten to
  nulls-only entries with zero fills, the second run is byte-identical, and a
  hand-filled null lands in `fgo_translate.json` while persisting in the file.
