from pathlib import Path
from utils import download_data, read_data

CWD = Path(__file__).parent


def servant_data():
    url = "https://api.atlasacademy.io/export/JP/nice_servant_lang_en.json"
    file_path = CWD / "nice_servant_lang_en.json"
    download_data(file_path, url)
    return read_data(file_path)


def mystic_code_data():
    url = "https://api.atlasacademy.io/export/JP/nice_mystic_code_lang_en.json"
    file_path = CWD / "nice_mystic_code_lang_en.json"
    download_data(file_path, url)
    return read_data(file_path)


def main():
    servants = servant_data()
    mystic_codes = mystic_code_data()
    print(servants)
    print(mystic_codes)


if __name__ == "__main__":
    main()
