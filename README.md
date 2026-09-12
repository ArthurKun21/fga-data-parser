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
server, caches it next to the generated files, and writes:

- `servant_data.json`
- `mystic_code_data.json`
- `craft_essence_data.json`

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

Install the [pre-commit](https://pre-commit.com) hooks with:

```bash
uv run pre-commit install
```
