# AGENTS.md

Guidance for coding agents working in this repository.

## Project overview

Two CLIs in one uv-managed Python package (src layout, Python >= 3.12):

- `fga-data-parser` (`src/fga_data_parser`): downloads Fate/Grand Order data
  from the Atlas Academy API and converts it to dataclass models written as
  JSON + protobuf (`servant_data`, `mystic_code_data`, `craft_essence_data`).
- `fgo-translate` (`src/fgo_translate`): builds a flat JP-text -> translated-
  text table (JP/CN/TW/NA/KR) from the Chaldea app's public mappings, written
  as JSON + protobuf (`fgo_translate`).

See `docs/fga_data_parser.md` and `docs/fgo_translate.md` for data-format
knowledge, design decisions, and future ideas before changing behavior.

## Critical rules

- **Never commit.** The user reviews and commits themselves. Do not stage
  (`git add`) or run `git commit` unless explicitly asked.
- **Never commit `chaldea-data/`** — it is a gitignored runtime checkout of
  chaldea-center/chaldea-data, not part of this project. Do not lint or reformat
  files inside it.
- **Generated protobuf bindings are not committed** (`*_pb2.py`, `*_pb2.pyi`
  are gitignored). Run `uv run python scripts/generate_proto.py` after cloning
  and after ANY `.proto` change — tests import the generated modules and fail
  with ImportError otherwise.
- **Changing a `.proto` means three edits**: the `.proto` file, the converter
  in the package's `pb.py`, and tests. Regenerate bindings before running.
- **Enums are strict on purpose.** When Atlas introduces an unknown value
  (`CardType`, `ServantFlag`, `CraftEssenceFlag`), the run fails loudly. Fix by
  adding the member + a test — never by loosening the parse.

## Commands

```bash
uv sync                              # install deps + the project itself (editable)
uv run python scripts/generate_proto.py   # regenerate protobuf bindings (required after clone / .proto edits)
uv run pytest                        # run tests
uv run ruff check .                  # lint
uv run ruff format --check .         # format check
uv run fga-data-parser               # run the parser (needs network unless cached)
uv run fgo-translate                 # build translations (needs chaldea-data/ checkout)
uv build --wheel                     # packaging check when build config changed
```

Both CLIs write outputs to `--output-dir` (default cwd); `*.json` and `*.pb`
outputs are gitignored.

## Repo layout

- `src/fga_data_parser/` — models (`servant.py`, `mystic_code.py`,
  `craft_essence.py`, `skill.py`, `enums.py`), pure transforms (`pipeline.py`),
  proto conversion (`pb.py`), CLI (`cli.py`, `__main__.py`), I/O (`utils.py`),
  generated bindings (`*_pb2.py`).
- `src/fgo_translate/` — same structure, smaller: `pipeline.py` (Chaldea
  table merge), `pb.py`, `cli.py`, `fgo_translate_pb2.py`.
- `protos/fga_data_parser/*.proto`, `protos/translations/fgo_translate.proto`
  — schema sources of truth. The translations proto gets its own include root
  in `scripts/generate_proto.py` so its bindings land inside the
  `fgo_translate` package.
- `tests/` — pytest; use synthetic fixtures in `tmp_path`, no network.
- `scripts/` — CI helpers (`generate_proto.py`, `release_tag.py`).
- `docs/` — domain knowledge and future-work notes; update when adding
  data-format knowledge.

## Conventions

- Builtin generics only (`list[int]`, `X | None`); no `typing.List`/`Optional`.
- Enums are `StrEnum` whose member names mirror their values (see
  `SkillTarget`); region/language codes follow Chaldea's (JP/CN/TW/NA/KR —
  the English game region is `NA`, there is no `en`).
- Dataclasses for models; orjson for all JSON I/O; protobuf serialization uses
  `SerializeToString(deterministic=True)`.
- CLI output goes through `logging` with a rich handler — never `print`.
- Comments explain constraints and why, not what. Help strings and user-facing
  text stay concise.
- ruff is the linter/formatter (config in `pyproject.toml`; generated
  `*_pb2.py`/`*_pb2.pyi` and `chaldea-data` are excluded). Run
  `uv run ruff format .` before finishing.

## CI and releases

- `.github/workflows/test.yml` — push/PR: `uv sync --locked`, generate proto
  code, `ruff check`, `ruff format --check`, `pytest`.
- `.github/workflows/release.yml` — daily at 18:00 JST (`0 9 * * *` UTC) and
  `workflow_dispatch`: checks out chaldea-data, parses, translates, and
  publishes the four `.pb` files to a GitHub release tagged
  `YYYYMMDD.<version>` (UTC date, version increments per day via
  `scripts/release_tag.py`, which needs `GITHUB_TOKEN` in its step env for
  `gh`). Action SHAs are pinned deliberately — keep them pinned.

## Gotchas

- protoc requires file arguments to be exact prefixes of an `-I` root — pass
  paths relative to the repo root (see `scripts/generate_proto.py`).
- Hatchling respects `.gitignore` when building wheels; `ignore-vcs = true` in
  `[tool.hatch.build.targets.wheel]` is what keeps the gitignored bindings in
  the package — do not remove it.
- Adding a dependency: use `uv add` / `uv add --dev` so the lockfile stays in
  sync; dependabot updates the uv group weekly.
