"""Tests for the release tag generator script."""

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_SCRIPT = Path(__file__).parents[1] / "scripts" / "release_tag.py"
_spec = importlib.util.spec_from_file_location("release_tag", _SCRIPT)
release_tag = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release_tag)

JST = ZoneInfo("Asia/Tokyo")


def test_first_release_of_a_day_starts_at_version_zero() -> None:
    now = datetime(2026, 9, 13, 18, 0, tzinfo=UTC)

    assert release_tag.next_tag([], now) == "20260913.0"


def test_version_increments_for_same_day_releases() -> None:
    now = datetime(2026, 9, 13, 20, 30, tzinfo=UTC)
    tags = ["20260911.3", "20260913.0", "20260913.1"]

    assert release_tag.next_tag(tags, now) == "20260913.2"


def test_non_numeric_suffixes_are_ignored() -> None:
    now = datetime(2026, 9, 13, 18, 0, tzinfo=UTC)

    assert release_tag.next_tag(["20260913.beta"], now) == "20260913.0"


def test_date_uses_utc_even_for_other_timezones() -> None:
    # 2026-09-14 02:00 JST is 2026-09-13 17:00 UTC.
    now = datetime(2026, 9, 14, 2, 0, tzinfo=JST)

    assert release_tag.next_tag([], now) == "20260913.0"
