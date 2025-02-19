import time
from pathlib import Path

import httpx
import orjson

CWD = Path(__file__).parent


def download_data():
    file_path = CWD / "nice_mystic_code_lang_en.json"
    if file_path.exists() and file_path.stat().st_size > 10_000:
        return

    url = "https://api.atlasacademy.io/export/JP/nice_mystic_code_lang_en.json"

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


def read_data() -> list[dict]:
    try:
        with open(CWD / "nice_mystic_code_lang_en.json", "r", encoding="utf-8") as f:
            data = orjson.loads(f.read())
        return data
    except FileNotFoundError:
        print("File not found.")
        return []


def run():
    download_data()
    data = read_data()
    print(data)
