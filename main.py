from pathlib import Path

from src.enums import CardType
from src.servant import NoblePhantasm, Servant
from src.mystic_code import MysticCode
from src.skill import Skill
from utils import download_data, read_data, write_data

CWD = Path(__file__).parent


def servant_data():
    url = "https://api.atlasacademy.io/export/JP/nice_servant_lang_en.json"
    file_path = CWD / "nice_servant_lang_en.json"
    download_data(file_path, url)
    servants = read_data(file_path)

    servant_list: list[Servant] = []

    playable_type = ["heroine", "normal"]

    for servant in servants:
        servant_type = servant.get("type", None)
        if servant_type not in playable_type:
            continue

        servant_id = servant.get("id", 0)
        servant_collection_no = servant.get("collectionNo", 0)
        servant_name = servant.get("name", "")
        servant_class = servant.get("className", "")
        servant_rarity = servant.get("rarity", 0)

        servant_nps: list[dict] = servant.get("noblePhantasms", [])

        np_list: list[NoblePhantasm] = []

        for np in servant_nps:
            np_id = np.get("id", 0)
            np_num = np.get("num", 0)
            np_name = np.get("name", "")
            np_card_type = np.get("card", "")

            np_card_type = CardType(np_card_type)

            noble_phantasm = NoblePhantasm(
                id=np_id,
                num=np_num,
                name=np_name,
                card_type=np_card_type,
            )

            np_list.append(noble_phantasm)

        skill_list: list[Skill] = []

        servant_skills: list[dict] = servant.get("skills", [])
        for skill in servant_skills:
            skill_id = skill.get("id", 0)
            skill_num = skill.get("num", 0)
            skill_name = skill.get("name", "")
            skill_detail = skill.get("detail", "")
            skill_icon = skill.get("icon", "")
            skill_cooldown = skill.get("coolDown", [])
            skill_target = skill.get("priority", 0)

            skill_scripts = skill.get("script", {})
            skill_functions = skill.get("functions", [])

            skill = Skill.create(
                id=skill_id,
                num=skill_num,
                name=skill_name,
                detail=skill_detail,
                icon=skill_icon,
                cooldown=skill_cooldown,
                priority=skill_target,
                scripts=skill_scripts,
                functions=skill_functions,
            )
            skill_list.append(skill)

        servant = Servant(
            id=servant_id,
            collection_no=servant_collection_no,
            name=servant_name,
            class_name=servant_class,
            rarity=servant_rarity,
            np=np_list,
            skills=skill_list,
        )
        servant_list.append(servant)

    write_file_path = CWD / "servant_data.json"
    write_data(write_file_path, servant_list)


def mystic_code_data():
    url = "https://api.atlasacademy.io/export/JP/nice_mystic_code_lang_en.json"
    file_path = CWD / "nice_mystic_code_lang_en.json"
    download_data(file_path, url)
    mystic_codes = read_data(file_path)

    mystic_code_list: list[MysticCode] = []

    for mystic_code in mystic_codes:
        id = mystic_code.get("id", 0)
        name = mystic_code.get("name", "")
        extraAssets = mystic_code.get("extraAssets", {})
        item = extraAssets.get("item", {})

        male_assets = item.get("male", "")
        female_assets = item.get("female", "")

        skill_list: list[Skill] = []

        mystic_code_skills: list[dict] = mystic_code.get("skills", [])
        for skill in mystic_code_skills:
            skill_id = skill.get("id", 0)
            skill_num = skill.get("num", 0)
            skill_name = skill.get("name", "")
            skill_detail = skill.get("detail", "")
            skill_icon = skill.get("icon", "")
            skill_cooldown = skill.get("coolDown", [])
            skill_target = skill.get("priority", 0)

            skill_scripts = skill.get("script", {})
            skill_functions = skill.get("functions", [])

            skill = Skill.create(
                id=skill_id,
                num=skill_num,
                name=skill_name,
                detail=skill_detail,
                icon=skill_icon,
                cooldown=skill_cooldown,
                priority=skill_target,
                scripts=skill_scripts,
                functions=skill_functions,
            )

            skill_list.append(skill)

        mystic_code = MysticCode(
            id=id,
            name=name,
            assets={
                "male": male_assets,
                "female": female_assets,
            },
            skills=skill_list,
        )
        mystic_code_list.append(mystic_code)

    write_file_path = CWD / "mystic_code_data.json"
    write_data(write_file_path, mystic_code_list)


def main():
    servant_data()
    mystic_code_data()


if __name__ == "__main__":
    main()
