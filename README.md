# FGA Data Parser

Converts raw [Fate/Grand Order](https://www.fate-go.jp) data from the
[Atlas Academy API](https://api.atlasacademy.io) into a format that can be used by
[FGA (Fate/Grand Automata)](https://github.com/Fate-Grand-Automata/FGA).

## Usage

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run fga-data-parser
```

This downloads the raw servant, mystic code, and craft essence data for the JP
server, caches it next to the generated files, and writes (JSON for humans,
protobuf for applications):

- `servant_data.json` / `servant_data.pb`
- `mystic_code_data.json` / `mystic_code_data.pb`
- `craft_essence_data.json` / `craft_essence_data.pb`

The protobuf messages are defined in `protos/fga_data_parser/*.proto`; the
`.pb` files contain a `ServantList` / `MysticCodeList` / `CraftEssenceList`
message respectively.

## Translated text

`fgo-translate` builds a flat JP-text -> translated-text table (JP/CN/TW/NA/KR)
from the public name mappings of
[Chaldea](https://github.com/chaldea-center/chaldea), covering servant/CE/
mystic-code names, skill names and descriptions, noble Phantasm names and
descriptions, and buff texts. It needs a checkout of
[chaldea-data](https://github.com/chaldea-center/chaldea-data):

```bash
git clone --depth 1 https://github.com/chaldea-center/chaldea-data
uv run fgo-translate
```

This writes `fgo_translate.json` / `fgo_translate.pb` (a `FgoTranslate`
message: JP text -> `TranslationProto`) next to the other outputs. A region is
absent when Chaldea has no translation for it; consumers fall back to the `jp`
text, like the Chaldea app does.

| Flag | Description |
| --- | --- |
| `--region {JP,NA}` | Game server to fetch data from (default: `JP`). |
| `--force` | Re-download the raw data even if it is already cached. |
| `--output-dir DIR` | Directory for the cached raw data and generated files (default: current directory). |
| `--verbose` | Enable debug logging. |

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

The generated protobuf bindings (`src/fga_data_parser/*_pb2.py`) are not
committed, so generate them after cloning or whenever a `.proto` file changes
(the runtime only needs `protobuf`; codegen needs the dev group):

```bash
uv run python -m grpc_tools.protoc -I protos --python_out=src --pyi_out=src protos/fga_data_parser/*.proto
```

Install the [pre-commit](https://pre-commit.com) hooks with:

```bash
uv run pre-commit install
```
