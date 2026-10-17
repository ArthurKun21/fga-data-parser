# FGA Data Parser

Converts raw [Fate/Grand Order](https://www.fate-go.jp) data from the
Atlas Academy API into a format that can be used by
[FGA (Fate/Grand Automata) Preview](https://github.com/ArthurKun21/fga-preview-build).

[![GitHub downloads](https://img.shields.io/github/downloads/ArthurKun21/fga-data-parser/total?label=downloads&labelColor=27303D&color=0D1117&logo=github&logoColor=FFFFFF&style=flat)](https://github.com/ArthurKun21/fga-data-parser/releases)

## Usage

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run fga-data-parser
```

This downloads the raw servant, mystic code, and craft essence data for all
game regions (JP, CN, TW, KR, NA), caches it next to the generated files, and
writes (JSON for humans, protobuf for applications):

- `servant_data.json` / `servant_data.pb`
- `mystic_code_data.json` / `mystic_code_data.pb`
- `craft_essence_data.json` / `craft_essence_data.pb`

JP keeps the primary file names and the `.pb` outputs. The other regions write
suffixed JSON only (e.g. `servant_data.na.json`), which the translation step
cross-references for official per-region text.

The protobuf messages are defined in `protos/fga_data_parser/*.proto`; the
`.pb` files contain a `ServantList` / `MysticCodeList` / `CraftEssenceList`
message respectively.

## Translated text

`fgo-translate` builds a flat JP-text -> translated-text table (JP/CN/TW/NA/KR)
covering exactly the texts in the parser's data files. It cross-references the
parser's per-region outputs for the official game text of every region and
fills the gaps from the public name mappings of
[Chaldea](https://github.com/chaldea-center/chaldea). It needs a checkout of
[chaldea-data](https://github.com/chaldea-center/chaldea-data) and the parser's
outputs (both default to the current directory):

```bash
git clone --depth 1 https://github.com/chaldea-center/chaldea-data
uv run fga-data-parser
uv run fgo-translate
```

This writes `fgo_translate.json` / `fgo_translate.pb` (a `FgoTranslate`
message: JP text -> `TranslationProto`) next to the other outputs. A region is
absent when no translation exists for it; consumers fall back to the `jp`
text, like the Chaldea app does.

| Flag | Description |
| --- | --- |
| `--regions {JP,CN,TW,KR,NA} [...]` | Game servers to fetch data from (default: all regions). |
| `--force` | Re-download the raw data even if it is already cached. |
| `--output-dir DIR` | Directory for the cached raw data and generated files (default: current directory). |
| `--verbose` | Enable debug logging. |

## Docs

- [docs/fga_data_parser.md](./docs/fga_data_parser.md) — Atlas data-format knowledge, schema decisions, future ideas
- [docs/fgo_translate.md](./docs/fgo_translate.md) — how Chaldea's translation system works and how we reproduce it

## Development

See [CONTRIBUTING.md](./CONTRIBUTING.md) for setup, protobuf codegen, tests,
and linting.
