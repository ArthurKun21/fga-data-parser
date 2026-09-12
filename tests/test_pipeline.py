from typing import Any

import pytest

from fga_data_parser.craft_essence import CraftEssenceAssets, CraftEssenceSkill
from fga_data_parser.enums import CardType, CraftEssenceFlag, ServantFlag, SkillTarget
from fga_data_parser.mystic_code import Assets
from fga_data_parser.pipeline import build_craft_essences, build_mystic_codes, build_servants
from fga_data_parser.servant import (
    AppendPassive,
    AppendPassiveSkill,
    ServantAssetGroup,
    ServantAssets,
)
from fga_data_parser.skill import Skill


def make_servant(**overrides: Any) -> dict[str, Any]:
    servant = {
        "id": 100100,
        "collectionNo": 1,
        "type": "normal",
        "name": "Altria Pendragon",
        "className": "saber",
        "gender": "female",
        "rarity": 5,
        "flag": "normal",
        "extraAssets": {
            "charaGraph": {
                "ascension": {"1": "chara_graph_1.png"},
                "costume": {"100100": "chara_graph_costume.png"},
            },
            "faces": {"ascension": {"1": "face_1.png"}},
            "commands": {"ascension": {"1": "command_1.png"}},
            "status": {"ascension": {"1": "status_1.png"}},
        },
        "appendPassive": [
            {
                "num": 1,
                "skill": {
                    "id": 3001000,
                    "num": 0,
                    "name": "Append Skill",
                    "originalName": "Append Skill",
                    "detail": "Detail text.",
                    "icon": "append_icon.png",
                },
            }
        ],
        "noblePhantasms": [{"id": 100101, "num": 1, "name": "Excalibur", "card": "2"}],
        "skills": [],
    }
    servant.update(overrides)
    return servant


def make_mystic_code(**overrides: Any) -> dict[str, Any]:
    mystic_code = {
        "id": 200,
        "name": "Chaldea Uniform",
        "extraAssets": {"item": {"male": "male.png", "female": "female.png"}},
        "skills": [
            {
                "id": 9,
                "num": 0,
                "name": "Overload",
                "unmodifiedDetail": "Detail.",
                "icon": "icon.png",
                "coolDown": [8, 7, 6, 5, 4, 3, 2, 1],
                "priority": 0,
                "script": {},
                "functions": [],
            }
        ],
    }
    mystic_code.update(overrides)
    return mystic_code


def test_filters_out_non_playable_servants() -> None:
    servants = build_servants([make_servant(type="enemy"), make_servant(id=2)])

    assert [servant.id for servant in servants] == [2]


def test_sorts_by_collection_number() -> None:
    servants = build_servants(
        [
            make_servant(id=2, collectionNo=10),
            make_servant(id=1, collectionNo=2),
        ]
    )

    assert [servant.collection_no for servant in servants] == [2, 10]


def test_maps_numeric_card_values() -> None:
    (servant,) = build_servants([make_servant()])

    assert servant.nps[0].card_type is CardType.Buster
    assert servant.nps[0].card_type == "buster"


def test_builds_servant_assets_and_append_passives() -> None:
    (servant,) = build_servants([make_servant()])

    assert servant.flag is ServantFlag.Normal
    assert servant.gender == "female"
    assert servant.assets == ServantAssets(
        chara_graph=ServantAssetGroup(
            ascension={"1": "chara_graph_1.png"},
            costume={"100100": "chara_graph_costume.png"},
        ),
        faces=ServantAssetGroup(ascension={"1": "face_1.png"}, costume={}),
        commands=ServantAssetGroup(ascension={"1": "command_1.png"}, costume={}),
        status=ServantAssetGroup(ascension={"1": "status_1.png"}, costume={}),
    )
    assert servant.append_passives == [
        AppendPassive(
            num=1,
            skill=AppendPassiveSkill(
                id=3001000,
                num=0,
                name="Append Skill",
                original_name="Append Skill",
                detail="Detail text.",
                icon="append_icon.png",
            ),
        )
    ]


def test_servant_missing_asset_groups_default_to_empty() -> None:
    (servant,) = build_servants([make_servant(extraAssets={})])

    assert servant.assets == ServantAssets(
        chara_graph=ServantAssetGroup(ascension={}, costume={}),
        faces=ServantAssetGroup(ascension={}, costume={}),
        commands=ServantAssetGroup(ascension={}, costume={}),
        status=ServantAssetGroup(ascension={}, costume={}),
    )


def test_servant_transform_group_assets_are_captured() -> None:
    (servant,) = build_servants(
        [
            make_servant(
                extraAssets={
                    "faces": {
                        "ascension": {"1": "face_1.png"},
                        "transformGroup": {"505731": "face_transform.png"},
                    }
                }
            )
        ]
    )

    assert servant.assets.faces == ServantAssetGroup(
        ascension={"1": "face_1.png"},
        costume={},
        transform_group={"505731": "face_transform.png"},
    )


def test_servant_unknown_flag_raises() -> None:
    with pytest.raises(ValueError, match="is not a valid ServantFlag"):
        build_servants([make_servant(flag="svtSomethingNew")])


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"name": "Altria Pendragon (Lily)"}, "Artoria Pendragon (Lily)"),
        ({"name": "BB", "rarity": 5, "className": "mooncancer"}, "BB (Summer)"),
        ({"name": "BB", "rarity": 4, "className": "mooncancer"}, "BB"),
        (
            {"name": "Kishinami Hakuno", "gender": "female", "className": "caster"},
            "Kishinami Hakunon",
        ),
        (
            {"name": "Kishinami Hakuno", "gender": "male", "className": "mooncancer"},
            "Kishinami Hakuno",
        ),
        ({"name": "Ereshkigal", "className": "beastEresh"}, "Ereshkigal (Summer)"),
        ({"name": "Ereshkigal", "className": "lancer"}, "Ereshkigal"),
    ],
)
def test_name_fixes(overrides: dict[str, Any], expected: str) -> None:
    (servant,) = build_servants([make_servant(**overrides)])

    assert servant.name == expected


def test_duplicate_names_get_class_suffix() -> None:
    servants = build_servants(
        [
            make_servant(id=1, name="Same Name"),
            make_servant(id=2, name="Same Name"),
        ]
    )

    assert [servant.name for servant in servants] == ["Same Name", "Same Name (saber)"]


def test_repeated_duplicates_stay_unique() -> None:
    servants = build_servants(
        [
            make_servant(id=1, name="Same Name"),
            make_servant(id=2, name="Same Name"),
            make_servant(id=3, name="Same Name"),
        ]
    )

    assert [servant.name for servant in servants] == [
        "Same Name",
        "Same Name (saber)",
        "Same Name (saber) 2",
    ]


def test_parses_servant_skills() -> None:
    raw_skill = {
        "id": 9,
        "num": 2,
        "name": "Charisma B",
        "unmodifiedDetail": "Increases allies' attack.",
        "icon": "icon.png",
        "coolDown": [7, 6, 5, 4, 3, 2, 1],
        "priority": 0,
        "script": {},
        "functions": [{"funcType": "addState", "funcTargetType": "ptAll"}],
    }

    (servant,) = build_servants([make_servant(skills=[raw_skill])])

    skill = servant.skills[0]
    assert isinstance(skill, Skill)
    assert skill.id == 9
    assert skill.num == 2
    assert skill.name == "Charisma B"
    assert skill.detail == "Increases allies' attack."
    assert skill.cooldown == 7
    assert skill.target == [SkillTarget.TargetAll]


def test_builds_mystic_codes() -> None:
    (mystic_code,) = build_mystic_codes([make_mystic_code()])

    assert mystic_code.id == 200
    assert mystic_code.name == "Chaldea Uniform"
    assert mystic_code.assets == Assets(male="male.png", female="female.png")


def test_mystic_code_skill_num_falls_back_to_index() -> None:
    raw_skills = [make_mystic_code()["skills"][0], make_mystic_code()["skills"][0]]
    raw_skills[1]["id"] = 10

    (mystic_code,) = build_mystic_codes([make_mystic_code(skills=raw_skills)])

    assert [skill.num for skill in mystic_code.skills] == [0, 1]


def test_missing_extra_assets_defaults_to_empty_strings() -> None:
    (mystic_code,) = build_mystic_codes([make_mystic_code(extraAssets={})])

    assert mystic_code.assets == Assets(male="", female="")


def test_mystic_codes_are_sorted_by_id() -> None:
    mystic_codes = build_mystic_codes(
        [make_mystic_code(id=30), make_mystic_code(id=10), make_mystic_code(id=20)]
    )

    assert [mystic_code.id for mystic_code in mystic_codes] == [10, 20, 30]


def make_equip(**overrides: Any) -> dict[str, Any]:
    equip = {
        "id": 9300010,
        "collectionNo": 191,
        "type": "servantEquip",
        "flag": "normal",
        "name": "星の王冠",
        "originalName": "星の王冠",
        "rarity": 5,
        "cost": 12,
        "atkMax": 2500,
        "hpMax": 400,
        "extraAssets": {
            "charaGraph": {"equip": {"9300010": "chara_graph.png"}},
            "faces": {"equip": {"9300010": "face.png"}},
            "equipFace": {"equip": {"9300010": "equip_face.png"}},
        },
        "skills": [
            {
                "id": 990338,
                "name": "星の王冠",
                "originalName": "星の王冠",
                "detail": "Detail text.",
            }
        ],
    }
    equip.update(overrides)
    return equip


def test_builds_craft_essences() -> None:
    (craft_essence,) = build_craft_essences([make_equip()])

    assert craft_essence.id == 9300010
    assert craft_essence.collection_no == 191
    assert craft_essence.name == "星の王冠"
    assert craft_essence.original_name == "星の王冠"
    assert craft_essence.type == "servantEquip"
    assert craft_essence.flag is CraftEssenceFlag.Normal
    assert craft_essence.rarity == 5
    assert craft_essence.cost == 12
    assert craft_essence.atk_max == 2500
    assert craft_essence.hp_max == 400
    assert craft_essence.assets == CraftEssenceAssets(
        chara_graph={"9300010": "chara_graph.png"},
        faces={"9300010": "face.png"},
        equip_face={"9300010": "equip_face.png"},
    )
    assert craft_essence.skills == [
        CraftEssenceSkill(
            id=990338,
            name="星の王冠",
            original_name="星の王冠",
            detail="Detail text.",
        )
    ]


def test_craft_essence_missing_asset_groups_default_to_empty() -> None:
    (craft_essence,) = build_craft_essences([make_equip(extraAssets={})])

    assert craft_essence.assets == CraftEssenceAssets(chara_graph={}, faces={}, equip_face={})


def test_craft_essence_skill_without_detail_defaults_to_empty() -> None:
    raw = make_equip()
    del raw["skills"][0]["detail"]

    (craft_essence,) = build_craft_essences([raw])

    assert craft_essence.skills[0].detail == ""


def test_craft_essences_are_sorted_by_collection_number() -> None:
    craft_essences = build_craft_essences(
        [make_equip(id=2, collectionNo=300), make_equip(id=1, collectionNo=100)]
    )

    assert [craft_essence.collection_no for craft_essence in craft_essences] == [100, 300]


def test_craft_essence_unknown_flag_raises() -> None:
    with pytest.raises(ValueError, match="is not a valid CraftEssenceFlag"):
        build_craft_essences([make_equip(flag="svtEquipSomethingNew")])
