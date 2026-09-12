import logging
import time
from pathlib import Path
from typing import Any

import httpx
import orjson

logger = logging.getLogger(__name__)

RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 1
HTTP_TIMEOUT = httpx.Timeout(30.0)


def download_data(file_path: Path, url: str, *, force: bool = False) -> Path:
    """Download url to file_path unless a cached copy exists (or force is set).

    The response is streamed to a temp file and renamed into place, so an
    interrupted download never poisons the cache. Raises RuntimeError if all
    retry attempts fail.
    """
    if not force and file_path.exists():
        logger.debug("Using cached %s", file_path)
        return file_path

    tmp_path = file_path.with_name(f"{file_path.name}.tmp")
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            with httpx.stream("GET", url, timeout=HTTP_TIMEOUT) as response:
                response.raise_for_status()
                with tmp_path.open("wb") as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)
        except (httpx.HTTPError, OSError) as error:
            logger.warning(
                "Error downloading %s (attempt %d/%d): %s",
                url,
                attempt,
                RETRY_ATTEMPTS,
                error,
            )
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)
            continue
        tmp_path.replace(file_path)
        return file_path

    tmp_path.unlink(missing_ok=True)
    msg = f"Failed to download {url} after {RETRY_ATTEMPTS} attempts"
    raise RuntimeError(msg)


def read_data(file_path: Path) -> list[dict[str, Any]]:
    """Read an Atlas Academy JSON export from disk."""
    with file_path.open("rb") as f:
        data = orjson.loads(f.read())
    return data


def write_data(file_path: Path, data: Any) -> None:
    """Serialize data to JSON at file_path."""
    file_path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))
    logger.debug("Wrote %s", file_path)


def write_bytes(file_path: Path, data: bytes) -> None:
    """Write raw bytes to file_path."""
    file_path.write_bytes(data)
    logger.debug("Wrote %s", file_path)
