from fga_data_parser import common_pb2, craft_essence_pb2, mystic_code_pb2, servant_pb2
from fga_data_parser.craft_essence import CraftEssence, CraftEssenceAssets, CraftEssenceSkill
from fga_data_parser.enums import (
    CardType,
    CraftEssenceFlag,
    NoblePhantasmTarget,
    ServantFlag,
    SkillTarget,
)
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
from fga_data_parser.skill import (
    Choice2Detail,
    NoblePhantasm3Update,
    ScriptFunction,
    Skill,
    SkillLocked,
    TransformDetail,
)


def make_skill() -> Skill:
    return Skill(
        id=1,
        num=1,
        name="Test Skill",
        detail="A test skill.",
        icon="icon.png",
        cooldown=7,
        functions=[
            ScriptFunction(
                target=SkillTarget.CHOICE_2,
                choice2=Choice2Detail(detail="Choose one", option_a="Buster", option_b="Arts"),
            ),
            ScriptFunction(target=SkillTarget.TARGET_ONE),
            ScriptFunction(
                target=SkillTarget.COMMAND_NP_TYPE_3,
                np3=NoblePhantasm3Update(
                    detail="NP type change", option_a="Quick", option_b="Arts", option_c="Buster"
                ),
            ),
            ScriptFunction(
                target=SkillTarget.TRANSFORM,
                act_select_index=1,
                transform=TransformDetail(target=100100, ascension=2),
            ),
        ],
        locked=[SkillLocked(costume=12), SkillLocked(costume=13)],
    )


def make_servant() -> Servant:
    return Servant(
        id=100100,
        collection_no=2,
        name="Artoria Pendragon",
        class_name="saber",
        rarity=5,
        flag=ServantFlag.NORMAL,
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
        nps=[
            NoblePhantasm(
                id=100101,
                num=1,
                name="Excalibur",
                card_type=CardType.BUSTER,
                locked=[SkillLocked(costume=17), SkillLocked(costume=19)],
            )
        ],
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
        alternate_forms_id=[600710],
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
    assert servant.flag == servant_pb2.Servant.NORMAL
    assert servant.gender == "female"
    assert servant.alternate_forms_id == [600710]
    assert servant.assets.chara_graph.ascension == {"1": "chara_graph_1.png"}
    assert servant.assets.chara_graph.costume == {"100100": "chara_graph_costume.png"}
    assert servant.assets.faces.ascension == {"1": "face_1.png"}
    assert servant.assets.commands.ascension == {}
    assert servant.assets.status.transform_group == {"1": "status_transform.png"}

    np = servant.nps[0]
    assert (np.id, np.num, np.name) == (100101, 1, "Excalibur")
    assert np.card_type == common_pb2.CardType.BUSTER
    # The unset side of a gate round-trips as the proto default 0.
    assert [(lock.costume, lock.ascension) for lock in np.locked] == [(17, 0), (19, 0)]

    skill = servant.skills[0]
    assert skill.id == 1
    assert skill.cooldown == 7
    assert [(lock.costume, lock.ascension) for lock in skill.locked] == [(12, 0), (13, 0)]
    assert [function.target for function in skill.functions] == [
        common_pb2.SkillTarget.CHOICE_2,
        common_pb2.SkillTarget.TARGET_ONE,
        common_pb2.SkillTarget.COMMAND_NP_TYPE_3,
        common_pb2.SkillTarget.TRANSFORM,
    ]
    choice2 = skill.functions[0].choice2
    assert choice2.detail == "Choose one"
    assert (choice2.optionA, choice2.optionB) == ("Buster", "Arts")
    # Bare entries carry no condition or payload messages.
    assert not skill.functions[1].HasField("act_select_index")
    assert not skill.functions[1].HasField("choice2")
    np3 = skill.functions[2].np3
    assert (np3.detail, np3.optionA, np3.optionB, np3.optionC) == (
        "NP type change",
        "Quick",
        "Arts",
        "Buster",
    )
    transform = skill.functions[3].transform
    assert (transform.target, transform.ascension) == (100100, 2)
    assert skill.functions[3].HasField("act_select_index")
    assert skill.functions[3].act_select_index == 1

    append_passive = servant.append_passives[0]
    assert append_passive.num == 1
    assert append_passive.skill.id == 3001000
    assert append_passive.skill.original_name == "Append Skill"


def test_transform_without_payload_is_unset() -> None:
    servant = make_servant()
    servant.skills = [
        Skill(
            id=1,
            num=1,
            name="Test Skill",
            detail="A test skill.",
            icon="icon.png",
            cooldown=7,
            functions=[ScriptFunction(target=SkillTarget.TRANSFORM)],
        )
    ]

    parsed = servant_pb2.ServantList.FromString(servants_to_bytes([servant]))

    function = parsed.servants[0].skills[0].functions[0]
    assert function.target == common_pb2.SkillTarget.TRANSFORM
    assert not function.HasField("transform")


def test_act_select_index_zero_round_trips() -> None:
    servant = make_servant()
    servant.skills = [
        Skill(
            id=1,
            num=1,
            name="Test Skill",
            detail="A test skill.",
            icon="icon.png",
            cooldown=7,
            functions=[ScriptFunction(target=SkillTarget.TRANSFORM, act_select_index=0)],
        )
    ]

    parsed = servant_pb2.ServantList.FromString(servants_to_bytes([servant]))

    function = parsed.servants[0].skills[0].functions[0]
    assert function.HasField("act_select_index")
    assert function.act_select_index == 0


def test_noble_phantasm_targets_round_trip() -> None:
    servant = make_servant()
    servant.nps = [
        NoblePhantasm(id=100101, num=1, name="Excalibur", card_type=CardType.BUSTER),
        NoblePhantasm(
            id=2501401,
            num=1,
            name="逆行銀河・赤方偏移",
            card_type=CardType.ARTS,
            targets=[NoblePhantasmTarget.NOBLE_PHANTASM_TARGET_TRANSFORM],
            locked=[SkillLocked(ascension=3), SkillLocked(costume=13)],
        ),
    ]

    parsed = servant_pb2.ServantList.FromString(servants_to_bytes([servant]))

    plain, transforming = parsed.servants[0].nps
    assert list(plain.targets) == []
    assert list(plain.locked) == []
    assert list(transforming.targets) == [
        servant_pb2.NoblePhantasmTarget.NOBLE_PHANTASM_TARGET_TRANSFORM
    ]
    assert [(lock.costume, lock.ascension) for lock in transforming.locked] == [
        (0, 3),
        (13, 0),
    ]


def test_craft_essence_round_trip() -> None:
    parsed = craft_essence_pb2.CraftEssenceList.FromString(
        craft_essences_to_bytes([make_craft_essence()])
    )

    assert len(parsed.craft_essences) == 1
    parsed_ce = parsed.craft_essences[0]
    assert parsed_ce.id == 9300010
    assert parsed_ce.flag == craft_essence_pb2.CraftEssence.SVT_EQUIP_CAMPAIGN
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
        flag=CraftEssenceFlag.UNKNOWN,
        rarity=3,
        cost=3,
        assets=CraftEssenceAssets(chara_graph={}, faces={}, equip_face={}),
        atk_max=0,
        hp_max=0,
    )

    parsed = craft_essence_pb2.CraftEssenceList.FromString(craft_essences_to_bytes([craft_essence]))

    assert parsed.craft_essences[0].flag == craft_essence_pb2.CraftEssence.UNKNOWN


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
    assert [function.target for function in parsed_mc.skills[0].functions] == [
        common_pb2.SkillTarget.CHOICE_2,
        common_pb2.SkillTarget.TARGET_ONE,
        common_pb2.SkillTarget.COMMAND_NP_TYPE_3,
        common_pb2.SkillTarget.TRANSFORM,
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
        flag=CraftEssenceFlag.SVT_EQUIP_CAMPAIGN,
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
