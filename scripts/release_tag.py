"""Generate the release tag name: YYYYMMDD.<version>, with the date in UTC.

The version starts at 0 for the first release of a day and increments when a
release for the same day already exists.
"""

import os
import subprocess
from collections.abc import Iterable
from datetime import UTC, datetime


def next_tag(tags: Iterable[str], now: datetime) -> str:
    """Return the next release tag for the UTC calendar day of now."""
    date = now.astimezone(UTC).strftime("%Y%m%d")
    prefix = f"{date}."
    version = 0
    for tag in tags:
        if not tag.startswith(prefix):
            continue
        suffix = tag[len(prefix) :]
        if suffix.isdigit():
            version = max(version, int(suffix) + 1)
    return f"{prefix}{version}"


def fetch_release_tags(repo: str) -> list[str]:
    """Fetch the most recent release tag names via the GitHub CLI."""
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/releases?per_page=100", "--jq", ".[].tag_name"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.split()


def main() -> int:
    tags = fetch_release_tags(os.environ["GITHUB_REPOSITORY"])
    print(next_tag(tags, datetime.now(UTC)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
