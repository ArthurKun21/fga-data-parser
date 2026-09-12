from fga_data_parser import craft_essence_pb2, mystic_code_pb2, servant_pb2
from fga_data_parser.craft_essence import CraftEssence, CraftEssenceAssets, CraftEssenceSkill
from fga_data_parser.enums import CardType, CraftEssenceFlag, ServantFlag, SkillTarget
from fga_data_parser.mystic_code import Assets, MysticCode
from fga_data_parser.pb import (
    craft_essences_to_bytes,
    mystic_codes_to_bytes,
    servants_to_bytes,
)
from fga_data_parser.servant import (
    AppendPassive,
    AppendPassiveSkill,
    NoblePhantasm,
    Servant,
    ServantAssetGroup,
    ServantAssets,
)
from fga_data_parser.skill import ScriptButton, Skill, TransformDetail


def make_skill() -> Skill:
    return Skill(
        id=1,
        num=1,
        name="Test Skill",
        detail="A test skill.",
        icon="icon.png",
        cooldown=7,
        target=[SkillTarget.TargetOne, SkillTarget.Transform],
        script_buttons=ScriptButton(title="Choose one", buttons=["Buster", "Arts"]),
        buttons=[["Quick", "Arts", "Buster"]],
        transform=TransformDetail(ascension=2, target_ascension=3),
    )


def make_servant() -> Servant:
    return Servant(
        id=100100,
        collection_no=2,
        name="Artoria Pendragon",
        class_name="saber",
        rarity=5,
        flag=ServantFlag.Normal,
        assets=ServantAssets(
            chara_graph=ServantAssetGroup(
                ascension={"1": "chara_graph_1.png"},
                costume={"100100": "chara_graph_costume.png"},
            ),
            faces=ServantAssetGroup(ascension={"1": "face_1.png"}),
            commands=ServantAssetGroup(),
            status=ServantAssetGroup(
                ascension={"1": "status_1.png"},
                transform_group={"1": "status_transform.png"},
            ),
        ),
        gender="female",
        nps=[NoblePhantasm(id=100101, num=1, name="Excalibur", card_type=CardType.Buster)],
        skills=[make_skill()],
        append_passives=[
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
        ],
    )


def test_servant_round_trip() -> None:
    parsed = servant_pb2.ServantList.FromString(servants_to_bytes([make_servant()]))

    assert len(parsed.servants) == 1
    servant = parsed.servants[0]
    assert servant.id == 100100
    assert servant.collection_no == 2
    assert servant.name == "Artoria Pendragon"
    assert servant.class_name == "saber"
    assert servant.rarity == 5
    assert servant.flag == servant_pb2.Servant.Normal
    assert servant.gender == "female"
    assert servant.assets.chara_graph.ascension == {"1": "chara_graph_1.png"}
    assert servant.assets.chara_graph.costume == {"100100": "chara_graph_costume.png"}
    assert servant.assets.faces.ascension == {"1": "face_1.png"}
    assert servant.assets.commands.ascension == {}
    assert servant.assets.status.transform_group == {"1": "status_transform.png"}

    np = servant.nps[0]
    assert (np.id, np.num, np.name) == (100101, 1, "Excalibur")
    assert np.card_type == servant_pb2.NoblePhantasm.Buster

    skill = servant.skills[0]
    assert skill.id == 1
    assert skill.cooldown == 7
    assert list(skill.target) == [
        servant_pb2.Skill.TargetOne,
        servant_pb2.Skill.Transform,
    ]
    assert skill.script_buttons.title == "Choose one"
    assert list(skill.script_buttons.buttons) == ["Buster", "Arts"]
    assert [list(row.values) for row in skill.buttons] == [["Quick", "Arts", "Buster"]]
    assert skill.transform.ascension == 2
    assert skill.transform.HasField("target_ascension")
    assert skill.transform.target_ascension == 3

    append_passive = servant.append_passives[0]
    assert append_passive.num == 1
    assert append_passive.skill.id == 3001000
    assert append_passive.skill.original_name == "Append Skill"


def test_transform_without_target_ascension_is_unset() -> None:
    servant = make_servant()
    servant.skills = [
        Skill(
            id=1,
            num=1,
            name="Test Skill",
            detail="A test skill.",
            icon="icon.png",
            cooldown=7,
            target=[SkillTarget.Transform],
            transform=TransformDetail(ascension=2, target_ascension=None),
        )
    ]

    parsed = servant_pb2.ServantList.FromString(servants_to_bytes([servant]))

    transform = parsed.servants[0].skills[0].transform
    assert transform.ascension == 2
    assert not transform.HasField("target_ascension")


def test_craft_essence_round_trip() -> None:
    parsed = craft_essence_pb2.CraftEssenceList.FromString(
        craft_essences_to_bytes([make_craft_essence()])
    )

    assert len(parsed.craft_essences) == 1
    parsed_ce = parsed.craft_essences[0]
    assert parsed_ce.id == 9300010
    assert parsed_ce.flag == craft_essence_pb2.CraftEssence.SvtEquipCampaign
    assert parsed_ce.assets.chara_graph == {"9300010": "chara_graph.png"}
    assert parsed_ce.assets.equip_face == {"9300010": "equip_face.png"}
    assert parsed_ce.atk_max == 2500
    assert parsed_ce.skills[0].original_name == "星の王冠"


def test_craft_essence_unknown_flag_round_trips() -> None:
    craft_essence = CraftEssence(
        id=1,
        collection_no=1,
        name="name",
        original_name="name",
        type="servantEquip",
        flag=CraftEssenceFlag.Unknown,
        rarity=3,
        cost=3,
        assets=CraftEssenceAssets(chara_graph={}, faces={}, equip_face={}),
        atk_max=0,
        hp_max=0,
    )

    parsed = craft_essence_pb2.CraftEssenceList.FromString(craft_essences_to_bytes([craft_essence]))

    assert parsed.craft_essences[0].flag == craft_essence_pb2.CraftEssence.Unknown


def test_mystic_code_round_trip() -> None:
    mystic_code = MysticCode(
        id=200,
        name="Chaldea Uniform",
        assets=Assets(male="male.png", female="female.png"),
        skills=[make_skill()],
    )

    parsed = mystic_code_pb2.MysticCodeList.FromString(mystic_codes_to_bytes([mystic_code]))

    assert len(parsed.mystic_codes) == 1
    parsed_mc = parsed.mystic_codes[0]
    assert (parsed_mc.id, parsed_mc.name) == (200, "Chaldea Uniform")
    assert parsed_mc.assets.male == "male.png"
    assert parsed_mc.assets.female == "female.png"
    # Skills are shared with the servant proto.
    assert list(parsed_mc.skills[0].target) == [
        servant_pb2.Skill.TargetOne,
        servant_pb2.Skill.Transform,
    ]


def test_serialization_is_deterministic() -> None:
    assert servants_to_bytes([make_servant()]) == servants_to_bytes([make_servant()])
    assert craft_essences_to_bytes([make_craft_essence()]) == craft_essences_to_bytes(
        [make_craft_essence()]
    )


def make_craft_essence() -> CraftEssence:
    return CraftEssence(
        id=9300010,
        collection_no=191,
        name="星の王冠",
        original_name="星の王冠",
        type="servantEquip",
        flag=CraftEssenceFlag.SvtEquipCampaign,
        rarity=5,
        cost=12,
        assets=CraftEssenceAssets(
            chara_graph={"9300010": "chara_graph.png"},
            faces={"9300010": "face.png"},
            equip_face={"9300010": "equip_face.png"},
        ),
        atk_max=2500,
        hp_max=400,
        skills=[
            CraftEssenceSkill(
                id=990338,
                name="星の王冠",
                original_name="星の王冠",
                detail="Detail.",
            )
        ],
    )
