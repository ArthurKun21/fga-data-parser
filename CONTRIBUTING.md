# Contributing to FGA Data Parser

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Protobuf bindings

The generated protobuf bindings (`src/fga_data_parser/*_pb2.py` and
`src/fgo_translate/fgo_translate_pb2.py`) are not committed, so generate them
after cloning or whenever a `.proto` file changes (the runtime only needs
`protobuf`; codegen needs the dev group):

```bash
uv run python scripts/generate_proto.py
```

## Tests

```bash
uv run pytest
```

## Lint and format

```bash
uv run ruff check .
uv run ruff format --check .
```

CI runs the checks above on every push and pull request.

## Pre-commit hooks

Install the [pre-commit](https://pre-commit.com) hooks with:

```bash
uv run pre-commit install
```
