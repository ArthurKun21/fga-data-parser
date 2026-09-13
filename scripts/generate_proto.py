"""Regenerate the protobuf bindings for all protos."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]

# The translations proto gets its own include root so the generated module
# lands inside the fgo_translate package instead of a top-level module.
COMMANDS = [
    [
        "-I",
        "protos",
        "--python_out=src",
        "--pyi_out=src",
        *sorted(
            str(path.relative_to(ROOT))
            for path in (ROOT / "protos" / "fga_data_parser").glob("*.proto")
        ),
    ],
    [
        "-I",
        "protos/translations",
        "--python_out=src/fgo_translate",
        "--pyi_out=src/fgo_translate",
        str((ROOT / "protos" / "translations" / "fgo_translate.proto").relative_to(ROOT)),
    ],
]


def main() -> int:
    for arguments in COMMANDS:
        subprocess.run(
            [sys.executable, "-m", "grpc_tools.protoc", *arguments],
            check=True,
            cwd=ROOT,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
