import time
from pathlib import Path

import httpx
import orjson


def download_data(file_path: Path, url: str):
    if file_path.exists() and file_path.stat().st_size > 10_000:
        return

    retry = 3

    for i in range(retry):
        try:
            with httpx.stream("GET", url) as response:
                with open(file_path, "wb") as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)
            return file_path
        except Exception as e:
            print(f"Error downloading from Atlas {retry - i} retries left.\t{e}.")
            time.sleep(1)
            continue


def read_data(
    file_path: Path,
) -> list[dict]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = orjson.loads(f.read())
        return data
    except FileNotFoundError:
        print("File not found.")
        return []


def write_data(file_path: Path, data):
    with open(file_path, "wb") as f:
        f.write(orjson.dumps(data, option=orjson.OPT_INDENT_2))
