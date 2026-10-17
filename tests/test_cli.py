import json
from pathlib import Path
from typing import Any

import orjson
from test_pipeline import make_equip, make_mystic_code, make_servant

from fga_data_parser import cli


def _raw_data() -> dict[str, list[dict[str, Any]]]:
    return {
        "nice_servant": [make_servant()],
        "nice_mystic_code": [make_mystic_code()],
        "nice_equip": [make_equip()],
    }


def _stub_download(monkeypatch, raw_by_region: dict[str, dict[str, list[dict[str, Any]]]]) -> None:
    """Serve per-region fixture payloads instead of downloading the exports."""

    def download(file_path: Path, url: str, *, force: bool = False) -> None:
        region = url.split("/")[-2].lower()
        stem = file_path.name.removesuffix(".json")
        if stem.endswith(f".{region}"):
            stem = stem.removesuffix(f".{region}")
        file_path.write_bytes(orjson.dumps(raw_by_region[region][stem]))

    monkeypatch.setattr(cli, "download_data", download)


def test_cli_writes_jp_proto_and_region_suffixed_json(tmp_path, monkeypatch) -> None:
    _stub_download(monkeypatch, {"jp": _raw_data(), "na": _raw_data()})

    exit_code = cli.main(["--output-dir", str(tmp_path), "--regions", "JP", "NA"])

    assert exit_code == 0
    # JP keeps the primary names and gets protobuf outputs; other regions
    # feed the translation join and only need JSON.
    assert (tmp_path / "servant_data.json").exists()
    assert (tmp_path / "servant_data.pb").exists()
    assert (tmp_path / "craft_essence_data.na.json").exists()
    assert not (tmp_path / "craft_essence_data.na.pb").exists()
    assert (tmp_path / "nice_servant.na.json").exists()
    # The FGA-facing name fixes only apply to the JP output.
    jp = json.loads((tmp_path / "servant_data.json").read_text())
    na = json.loads((tmp_path / "servant_data.na.json").read_text())
    assert jp[0]["name"] == "Artoria Pendragon"
    assert na[0]["name"] == "Altria Pendragon"
