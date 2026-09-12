from pathlib import Path
from typing import Any

import httpx
import pytest

from fga_data_parser.utils import download_data, read_data, write_data


class FakeResponse:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    def raise_for_status(self) -> None:
        pass

    def iter_bytes(self) -> Any:
        return iter(self._chunks)

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> bool:
        return False


def test_write_and_read_roundtrip(tmp_path: Path) -> None:
    file_path = tmp_path / "out.json"
    data = {"name": "Artoria", "nps": [{"card_type": "buster"}]}

    write_data(file_path, data)

    assert read_data(file_path) == data


def test_write_data_is_indented(tmp_path: Path) -> None:
    file_path = tmp_path / "out.json"

    write_data(file_path, {"a": 1})

    assert b"\n" in file_path.read_bytes()


def test_read_data_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_data(tmp_path / "missing.json")


def test_write_data_errors_propagate(tmp_path: Path) -> None:
    # tmp_path itself is a directory, so writing to it fails
    with pytest.raises(OSError):
        write_data(tmp_path, {"a": 1})


def test_download_uses_cached_file(tmp_path: Path) -> None:
    file_path = tmp_path / "raw.json"
    file_path.write_bytes(b"cached")

    assert download_data(file_path, "https://example.invalid/raw.json") == file_path
    assert file_path.read_bytes() == b"cached"


def test_download_writes_response_to_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_stream(method: str, url: str, timeout: object = None) -> FakeResponse:
        assert (method, url) == ("GET", "https://example.invalid/raw.json")
        return FakeResponse([b"hello ", b"world"])

    monkeypatch.setattr(httpx, "stream", fake_stream)

    file_path = tmp_path / "raw.json"
    assert download_data(file_path, "https://example.invalid/raw.json", force=True) == file_path
    assert file_path.read_bytes() == b"hello world"
    assert not file_path.with_name("raw.json.tmp").exists()


def test_download_retries_then_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts: list[str] = []

    def fake_stream(method: str, url: str, timeout: object = None) -> FakeResponse:
        attempts.append(url)
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx, "stream", fake_stream)
    monkeypatch.setattr("fga_data_parser.utils.time.sleep", lambda _seconds: None)

    file_path = tmp_path / "raw.json"
    with pytest.raises(RuntimeError, match="Failed to download"):
        download_data(file_path, "https://example.invalid/raw.json", force=True)

    assert len(attempts) == 3
    assert not file_path.exists()
    assert not file_path.with_name("raw.json.tmp").exists()
