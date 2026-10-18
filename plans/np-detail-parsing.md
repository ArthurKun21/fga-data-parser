# Servant NP detail parsing

## Problem

The parser's `NoblePhantasm` model carries only `id, num, name, card_type,
targets, locked` — the NP's description text is dropped. `servant.proto`
already declares `NoblePhantasm.detail = 7`, but neither the dataclass,
`_build_nps`, nor the pb converter populate it, so the field never appears in
`servant_data.json`/`servant_data.pb`.

Consequences on the translations side: `fgo_translate.atlas` aligns NPs
across regions but records only their `name`, and `collect_translatable_texts`
walks only `np["name"]` — NP details never reach `fgo_translate.json` even
though the `FgoTranslate` schema comment already advertises "noble Phantasm
names and descriptions". Chaldea's `td_detail` table cannot help on its own:
its keys are the templated `[{0}]` texts while the parser carries Atlas'
resolved `detail`, so no row matches (same situation as skill details, see
`docs/fgo_translate.md`).

## Design decisions

- **`detail` sits right after `name` in the dataclass**, mirroring `Skill` and
  `AppendPassiveSkill`; parsed with `raw.get("detail", "")` like
  `_parse_skills`. JSON output gains `detail` between `name` and `card_type`.
- **Proto keeps `detail = 7` appended** (wire-compatible with existing
  consumers, same reasoning as `Servant.alternate_forms_id = 100`); the field
  gets the same resolved-vs-templated comment as `common.Skill.detail`.
- **No `fgo_translate.proto` change**: the table is one flat
  `map<string, TranslationProto>` keyed by JP text; NP details are just more
  keys once the parser emits them.
- **Resolved `detail` only** — `unmodifiedDetail` (placeholders) is not
  emitted, mirroring skills.
- **Rejected: matching Chaldea's templated `td_detail` keys** via svals
  substitution — re-implements Atlas' `[{0}]` replacement; the overwrite queue
  is the designed path for texts no source covers (see
  `plans/missing-skill-text-coverage.md`).

## Implementation

1. `plans/np-detail-parsing.md` — this document.
2. `src/fga_data_parser/servant.py`: `NoblePhantasm.detail: str` after `name`.
3. `src/fga_data_parser/pipeline.py` `_build_nps`:
   `detail=raw.get("detail", "")`.
4. `src/fga_data_parser/pb.py` `_noble_phantasm_message`: `detail=...`.
5. `protos/fga_data_parser/servant.proto`: comment + column alignment;
   regenerate bindings (`scripts/generate_proto.py`).
6. `src/fgo_translate/atlas.py`:
   - `_collect_servants`: record `jp_np["detail"]` beside the NP `name`.
   - `collect_translatable_texts`: walk `np["detail"]` beside `np["name"]`
     (the field list stays in sync with the recorder, per its docstring).
7. Tests: `test_pipeline.py` (fixture `detail` + parse/default tests),
   `test_pb.py` (round-trip assert), `test_fgo_translate.py` (NP details in
   the atlas fixtures: JP id 11 / NA id 11 / TW id 888 pair through the
   existing alignment, a JP-only NP's detail lands in
   `collect_translatable_texts` only).
8. Docs: `docs/fga_data_parser.md` (NP `detail` raw-shape note),
   `docs/fgo_translate.md` (drop NP details from "Future ideas").

## Verification

- `uv run python scripts/generate_proto.py`, `uv run pytest`,
  `uv run ruff check .`, `uv run ruff format .`.
- No real CLI runs against the repo-root artifacts: a real `fgo-translate`
  run rewrites the committed `overwrite_translations.json` (new NP-detail
  keys enter the work queue); that belongs to the release workflow.
