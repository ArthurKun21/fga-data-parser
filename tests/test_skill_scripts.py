"""Tests for the machine-translations skill scripts.

The scripts live outside the packages, in
.agents/skills/machine-translations/scripts/, and are imported here by path.
apply.py/inventory.py must gate the queue exactly like the repo loader, and
apply.py's writes must round-trip byte-identically through the repo's own
writer; validate.py (which runs the real loader) is checked through its CLI.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

from fga_data_parser.utils import write_data
from fgo_translate.pipeline import (
    load_overwrite_translations,
    overwrite_translations_to_json,
)

SCRIPTS_DIR = (
    Path(__file__).resolve().parents[1] / ".agents" / "skills" / "machine-translations" / "scripts"
)


def _load_script(name: str) -> Any:
    """Import a skill script as a module by path; they live outside the packages."""
    spec = importlib.util.spec_from_file_location(f"skill_{name}", SCRIPTS_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def inventory_mod() -> Any:
    return _load_script("inventory")


@pytest.fixture
def apply_mod() -> Any:
    return _load_script("apply")


def _run_script(script: str, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / script), *args],
        capture_output=True,
        check=False,
    )


def _writer_bytes(data: Any) -> bytes:
    """Bytes exactly as the repo's own writer produces them."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "writer.json"
        write_data(path, data)
        return path.read_bytes()


def write_queue(path: Path, table: dict[str, dict[str, str | None]]) -> None:
    """Serialize exactly like the pipeline writer (sorted keys, writer options)."""
    path.write_bytes(_writer_bytes(overwrite_translations_to_json(table)))


QUEUE: dict[str, dict[str, str | None]] = {
    "ブレイキング": {"cn": "突破", "kr": None},
    "クリティカル威力アップ": {"cn": None, "tw": None, "na": None, "kr": None},
    "スター獲得": {"cn": None, "kr": None},
}


def test_inventory_summary_counts(inventory_mod: Any, tmp_path: Path) -> None:
    path = tmp_path / "overwrite_translations.json"
    write_queue(path, QUEUE)

    summary = inventory_mod.summarize(inventory_mod.load_table(path))

    assert summary["total_entries"] == 3
    assert summary["pending_entries"] == 3
    assert summary["entries_all_null"] == 1
    assert summary["nulls"] == {"cn": 2, "tw": 1, "na": 1, "kr": 3}
    assert summary["total_nulls"] == 7


def test_inventory_slices_partition_pending_work(inventory_mod: Any, tmp_path: Path) -> None:
    path = tmp_path / "overwrite_translations.json"
    write_queue(path, QUEUE)

    work = inventory_mod.pending_work(inventory_mod.load_table(path))
    slices = inventory_mod.write_slices(work, 2, tmp_path / "slices")

    assert work["ブレイキング"] == {"kr": None}
    assert [slice_info["keys"] for slice_info in slices] == [2, 1]
    seen: list[str] = []
    for slice_info in slices:
        slice_data = json.loads(Path(str(slice_info["path"])).read_bytes())
        assert all(value is None for entry in slice_data.values() for value in entry.values())
        seen.extend(slice_data)
    assert sorted(seen) == sorted(work)
    assert len(seen) == len(set(seen))


@pytest.mark.parametrize(
    "document",
    [
        {"translations": []},
        {"translations": {"テスト": "x"}},
        {"translations": {"テスト": {"en": "x"}}},
        {"translations": {"テスト": {"cn": ""}}},
        {"translations": {"テスト": {"jp": ""}}},
    ],
)
def test_helper_loader_rejects_like_the_repo_loader(
    inventory_mod: Any, tmp_path: Path, document: Any
) -> None:
    path = tmp_path / "queue.json"
    path.write_bytes(json.dumps(document, ensure_ascii=False).encode("utf-8"))

    with pytest.raises(ValueError):
        inventory_mod.load_table(path)
    with pytest.raises(ValueError):
        load_overwrite_translations(path)


def test_helper_loader_agrees_with_repo_loader(inventory_mod: Any, tmp_path: Path) -> None:
    path = tmp_path / "overwrite_translations.json"
    write_queue(path, QUEUE)

    assert inventory_mod.load_table(path) == load_overwrite_translations(path)


def test_apply_fills_nulls_and_round_trips_byte_identically(apply_mod: Any, tmp_path: Path) -> None:
    path = tmp_path / "overwrite_translations.json"
    write_queue(path, QUEUE)
    raw = json.loads(path.read_bytes())

    result = apply_mod.apply_fills(
        raw["translations"],
        {
            "クリティカル威力アップ": {"na": "Increase critical attack effectiveness by 10%"},
            "スター獲得": {"kr": "스타 획득"},
        },
    )
    path.write_bytes(_writer_bytes(raw))

    assert result["applied"] == 2
    assert result["per_region"] == {"cn": 0, "tw": 0, "na": 1, "kr": 1}
    assert result["rejected"] == []
    assert result["conflicts"] == []
    table = load_overwrite_translations(path)
    # The written bytes are exactly what the pipeline's writer produces.
    assert path.read_bytes() == _writer_bytes(overwrite_translations_to_json(table))
    assert table["クリティカル威力アップ"]["na"] == "Increase critical attack effectiveness by 10%"
    assert table["ブレイキング"]["cn"] == "突破"  # existing value untouched


def test_apply_never_overwrites_and_rejects_bad_fills(apply_mod: Any, tmp_path: Path) -> None:
    path = tmp_path / "overwrite_translations.json"
    write_queue(path, QUEUE)
    original = path.read_bytes()
    translations = json.loads(original)["translations"]

    idempotent = apply_mod.apply_fills(translations, {"ブレイキング": {"cn": "突破"}})
    conflict = apply_mod.apply_fills(translations, {"ブレイキング": {"cn": "突破改"}})
    unknown_key = apply_mod.apply_fills(translations, {"存在しないキー": {"na": "x"}})
    not_pending = apply_mod.apply_fills(translations, {"ブレイキング": {"tw": "Blocking"}})
    empty = apply_mod.apply_fills(translations, {"スター獲得": {"cn": ""}})

    assert idempotent["already_filled"] == 1
    assert idempotent["applied"] == 0
    assert len(conflict["conflicts"]) == 1
    assert conflict["applied"] == 0
    assert len(unknown_key["rejected"]) == 1
    assert len(not_pending["rejected"]) == 1
    assert "not pending" in not_pending["rejected"][0]["reason"]
    assert len(empty["rejected"]) == 1
    # Nothing was applied, so the on-disk representation is untouched.
    assert _writer_bytes(json.loads(original)) == original


def test_apply_rebuilds_canonical_region_order(apply_mod: Any, tmp_path: Path) -> None:
    path = tmp_path / "hand_edited.json"
    # Hand-edited style: regions out of the canonical cn/tw/na/kr order.
    path.write_bytes(json.dumps({"translations": {"テスト": {"kr": None, "cn": None}}}).encode())
    raw = json.loads(path.read_bytes())

    result = apply_mod.apply_fills(raw["translations"], {"テスト": {"cn": "测试"}})

    assert result["applied"] == 1
    assert list(raw["translations"]["テスト"]) == ["cn", "kr"]


def test_apply_tolerates_legacy_jp_echo(apply_mod: Any, tmp_path: Path) -> None:
    path = tmp_path / "legacy.json"
    path.write_bytes(
        json.dumps({"translations": {"テスト": {"jp": "テスト", "cn": None}}}).encode()
    )
    raw = json.loads(path.read_bytes())

    result = apply_mod.apply_fills(raw["translations"], {"テスト": {"cn": "测试"}})

    assert result["applied"] == 1
    entry = raw["translations"]["テスト"]
    assert entry["cn"] == "测试"
    assert list(entry) == ["cn", "jp"]  # canonical regions first, legacy jp at the tail


def test_apply_cli_dry_run_then_apply_with_backup(tmp_path: Path) -> None:
    path = tmp_path / "overwrite_translations.json"
    write_queue(path, QUEUE)
    fills = tmp_path / "fills.json"
    fills.write_bytes(json.dumps({"スター獲得": {"kr": "스타 획득"}}, ensure_ascii=False).encode())
    backup = tmp_path / "before.json"
    original = path.read_bytes()

    dry = _run_script(
        "apply.py",
        "--fills",
        str(fills),
        "--file",
        str(path),
        "--dry-run",
        "--backup",
        str(backup),
    )
    assert dry.returncode == 0
    dry_summary = json.loads(dry.stdout)
    assert dry_summary["dry_run"] is True
    assert dry_summary["applied"] == 1
    assert path.read_bytes() == original
    assert not backup.exists()  # a dry run writes nothing

    real = _run_script(
        "apply.py", "--fills", str(fills), "--file", str(path), "--backup", str(backup)
    )
    assert real.returncode == 0
    summary = json.loads(real.stdout)
    assert summary["dry_run"] is False
    assert summary["applied"] == 1
    assert backup.exists()
    assert backup.read_bytes() == original
    table = load_overwrite_translations(path)
    assert table["スター獲得"]["kr"] == "스타 획득"


def test_apply_cli_exit_code_1_on_rejection(tmp_path: Path) -> None:
    path = tmp_path / "overwrite_translations.json"
    write_queue(path, QUEUE)
    fills = tmp_path / "fills.json"
    fills.write_bytes(json.dumps({"存在しないキー": {"na": "x"}}, ensure_ascii=False).encode())
    original = path.read_bytes()

    result = _run_script("apply.py", "--fills", str(fills), "--file", str(path))

    assert result.returncode == 1
    summary = json.loads(result.stdout)
    assert len(summary["rejected"]) == 1
    assert path.read_bytes() == original


def test_validate_passes_on_fills_only_diff(tmp_path: Path) -> None:
    path = tmp_path / "overwrite_translations.json"
    write_queue(path, QUEUE)
    baseline = tmp_path / "before.json"
    baseline.write_bytes(path.read_bytes())
    raw = json.loads(path.read_bytes())
    raw["translations"]["スター獲得"]["kr"] = "스타 획득"
    path.write_bytes(_writer_bytes(raw))

    result = _run_script("validate.py", "--file", str(path), "--baseline", str(baseline))

    assert result.returncode == 0
    verdict = json.loads(result.stdout)
    assert verdict["ok"] is True
    assert verdict["checks"] == {"loader": True, "byte_round_trip": True, "baseline": True}
    assert verdict["fills_total"] == 1
    assert verdict["fills_per_region"]["kr"] == 1
    assert verdict["total_nulls"] == 6


def test_validate_fails_when_existing_value_is_modified(tmp_path: Path) -> None:
    path = tmp_path / "overwrite_translations.json"
    write_queue(path, QUEUE)
    baseline = tmp_path / "before.json"
    baseline.write_bytes(path.read_bytes())

    tampered = dict(QUEUE)
    tampered["ブレイキング"] = {"cn": "突破改", "kr": None}
    write_queue(path, tampered)

    result = _run_script("validate.py", "--file", str(path), "--baseline", str(baseline))

    assert result.returncode == 1
    verdict = json.loads(result.stdout)
    assert verdict["checks"]["baseline"] is False
    assert verdict["checks"]["byte_round_trip"] is True  # writer-format, but the value is wrong
    assert any("was modified" in issue for issue in verdict["issues"])


def test_validate_fails_on_format_drift(tmp_path: Path) -> None:
    path = tmp_path / "overwrite_translations.json"
    write_queue(path, QUEUE)
    raw = json.loads(path.read_bytes())
    raw["translations"]["スター獲得"]["kr"] = "스타 획득"
    # Same content, compact formatting — the writer contract is 2-space indent
    # and a trailing newline.
    path.write_bytes(json.dumps(raw, ensure_ascii=False, separators=(",", ":")).encode())

    result = _run_script("validate.py", "--file", str(path))

    assert result.returncode == 1
    verdict = json.loads(result.stdout)
    assert verdict["checks"]["loader"] is True
    assert verdict["checks"]["byte_round_trip"] is False


def test_validate_fails_when_an_entry_is_added(tmp_path: Path) -> None:
    path = tmp_path / "overwrite_translations.json"
    write_queue(path, QUEUE)
    baseline = tmp_path / "before.json"
    baseline.write_bytes(path.read_bytes())

    grown = dict(QUEUE)
    grown["追加キー"] = {"cn": None}
    write_queue(path, grown)

    result = _run_script("validate.py", "--file", str(path), "--baseline", str(baseline))

    assert result.returncode == 1
    verdict = json.loads(result.stdout)
    assert verdict["checks"]["baseline"] is False
    assert any("entry added" in issue for issue in verdict["issues"])


def test_validate_reports_legacy_jp_entries_as_the_round_trip_cause(tmp_path: Path) -> None:
    path = tmp_path / "overwrite_translations.json"
    path.write_bytes(_writer_bytes({"translations": {"テスト": {"jp": "テスト", "cn": None}}}))

    result = _run_script("validate.py", "--file", str(path))

    assert result.returncode == 1
    verdict = json.loads(result.stdout)
    assert verdict["checks"]["loader"] is True  # the loader tolerates the legacy echo
    assert verdict["checks"]["byte_round_trip"] is False
    assert any("legacy jp-echo" in issue for issue in verdict["issues"])


def test_inventory_cli_summary_slices_and_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "overwrite_translations.json"
    write_queue(path, QUEUE)
    snapshot = tmp_path / "before.json"
    slices_dir = tmp_path / "slices"

    result = _run_script(
        "inventory.py",
        "--file",
        str(path),
        "--slices",
        "2",
        "--slices-dir",
        str(slices_dir),
        "--snapshot",
        str(snapshot),
    )

    assert result.returncode == 0
    summary = json.loads(result.stdout)
    assert summary["total_entries"] == 3
    assert summary["total_nulls"] == 7
    assert summary["snapshot"] == str(snapshot)
    assert snapshot.read_bytes() == path.read_bytes()
    assert [slice_info["keys"] for slice_info in summary["slices"]] == [2, 1]
    assert len(list(slices_dir.glob("slice-*.json"))) == 2


def test_end_to_end_inventory_apply_validate(tmp_path: Path) -> None:
    """The SKILL.md procedure wiring: census -> slices -> fills -> apply -> gate."""
    path = tmp_path / "overwrite_translations.json"
    write_queue(path, QUEUE)
    backup = tmp_path / "before.json"
    slices_dir = tmp_path / "slices"

    census = json.loads(
        _run_script(
            "inventory.py",
            "--file",
            str(path),
            "--slices",
            "1",
            "--slices-dir",
            str(slices_dir),
            "--snapshot",
            str(backup),
        ).stdout
    )
    work = json.loads(Path(census["slices"][0]["path"]).read_bytes())
    fills = tmp_path / "fills.json"
    fills.write_bytes(
        json.dumps(
            {key: {"kr": f"kr-{index}"} for index, key in enumerate(sorted(work))},
            ensure_ascii=False,
        ).encode()
    )

    applied = json.loads(
        _run_script(
            "apply.py", "--fills", str(fills), "--file", str(path), "--backup", str(backup)
        ).stdout
    )
    assert applied["applied"] == 3
    assert applied["rejected"] == []
    assert applied["conflicts"] == []
    assert applied["total_nulls"] == 4

    verdict = json.loads(
        _run_script("validate.py", "--file", str(path), "--baseline", str(backup)).stdout
    )
    assert verdict["ok"] is True
    assert verdict["fills_total"] == 3
    assert verdict["fills_per_region"]["kr"] == 3


@pytest.mark.parametrize("script", ["inventory.py", "apply.py", "validate.py"])
def test_script_help_is_available(script: str) -> None:
    result = _run_script(script, "--help")

    assert result.returncode == 0
    assert b"usage:" in result.stdout
