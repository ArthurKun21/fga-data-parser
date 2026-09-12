"""Convert parsed models into protobuf messages for the .pb outputs."""

from google.protobuf.message import Message

from . import craft_essence_pb2, mystic_code_pb2, servant_pb2
from .craft_essence import CraftEssence, CraftEssenceSkill
from .mystic_code import MysticCode
from .servant import (
    AppendPassive,
    AppendPassiveSkill,
    NoblePhantasm,
    Servant,
    ServantAssetGroup,
    ServantAssets,
)
from .skill import Skill


def servants_to_bytes(servants: list[Servant]) -> bytes:
    """Serialize servants into servant_data.pb bytes."""
    return _serialize(
        servant_pb2.ServantList(servants=[_servant_message(servant) for servant in servants])
    )


def craft_essences_to_bytes(craft_essences: list[CraftEssence]) -> bytes:
    """Serialize craft essences into craft_essence_data.pb bytes."""
    return _serialize(
        craft_essence_pb2.CraftEssenceList(
            craft_essences=[_craft_essence_message(ce) for ce in craft_essences]
        )
    )


def mystic_codes_to_bytes(mystic_codes: list[MysticCode]) -> bytes:
    """Serialize mystic codes into mystic_code_data.pb bytes."""
    return _serialize(
        mystic_code_pb2.MysticCodeList(
            mystic_codes=[_mystic_code_message(mystic_code) for mystic_code in mystic_codes]
        )
    )


def _serialize(message: Message) -> bytes:
    return message.SerializeToString(deterministic=True)


def _servant_message(servant: Servant) -> servant_pb2.Servant:
    return servant_pb2.Servant(
        id=servant.id,
        collection_no=servant.collection_no,
        name=servant.name,
        class_name=servant.class_name,
        rarity=servant.rarity,
        flag=servant_pb2.Servant.ServantFlag.Value(servant.flag.name),
        assets=_servant_assets_message(servant.assets),
        gender=servant.gender,
        nps=[_noble_phantasm_message(np) for np in servant.nps],
        skills=[_skill_message(skill) for skill in servant.skills],
        append_passives=[
            _append_passive_message(append_passive) for append_passive in servant.append_passives
        ],
    )


def _noble_phantasm_message(noble_phantasm: NoblePhantasm) -> servant_pb2.NoblePhantasm:
    return servant_pb2.NoblePhantasm(
        id=noble_phantasm.id,
        num=noble_phantasm.num,
        name=noble_phantasm.name,
        card_type=servant_pb2.NoblePhantasm.CardType.Value(noble_phantasm.card_type.name),
    )


def _servant_assets_message(assets: ServantAssets) -> servant_pb2.ServantAssets:
    return servant_pb2.ServantAssets(
        chara_graph=_servant_asset_group_message(assets.chara_graph),
        faces=_servant_asset_group_message(assets.faces),
        commands=_servant_asset_group_message(assets.commands),
        status=_servant_asset_group_message(assets.status),
    )


def _servant_asset_group_message(group: ServantAssetGroup) -> servant_pb2.ServantAssetGroup:
    return servant_pb2.ServantAssetGroup(
        ascension=group.ascension,
        costume=group.costume,
        transform_group=group.transform_group,
    )


def _append_passive_message(append_passive: AppendPassive) -> servant_pb2.AppendPassive:
    return servant_pb2.AppendPassive(
        num=append_passive.num,
        skill=_append_passive_skill_message(append_passive.skill),
    )


def _append_passive_skill_message(
    skill: AppendPassiveSkill,
) -> servant_pb2.AppendPassiveSkill:
    return servant_pb2.AppendPassiveSkill(
        id=skill.id,
        num=skill.num,
        name=skill.name,
        original_name=skill.original_name,
        detail=skill.detail,
        icon=skill.icon,
    )


def _skill_message(skill: Skill) -> servant_pb2.Skill:
    message = servant_pb2.Skill(
        id=skill.id,
        num=skill.num,
        name=skill.name,
        detail=skill.detail,
        icon=skill.icon,
        cooldown=skill.cooldown,
        target=[servant_pb2.Skill.SkillTarget.Value(target.name) for target in skill.target],
    )
    if skill.script_buttons is not None:
        message.script_buttons.title = skill.script_buttons.title
        message.script_buttons.buttons.extend(skill.script_buttons.buttons)
    for button_row in skill.buttons:
        row = message.buttons.add()
        row.values.extend(button_row)
    if skill.transform is not None:
        message.transform.ascension = skill.transform.ascension
        if skill.transform.target_ascension is not None:
            message.transform.target_ascension = skill.transform.target_ascension
    return message


def _craft_essence_message(craft_essence: CraftEssence) -> craft_essence_pb2.CraftEssence:
    return craft_essence_pb2.CraftEssence(
        id=craft_essence.id,
        collection_no=craft_essence.collection_no,
        name=craft_essence.name,
        original_name=craft_essence.original_name,
        type=craft_essence.type,
        flag=craft_essence_pb2.CraftEssence.CraftEssenceFlag.Value(craft_essence.flag.name),
        rarity=craft_essence.rarity,
        cost=craft_essence.cost,
        assets=craft_essence_pb2.CraftEssenceAssets(
            chara_graph=craft_essence.assets.chara_graph,
            faces=craft_essence.assets.faces,
            equip_face=craft_essence.assets.equip_face,
        ),
        atk_max=craft_essence.atk_max,
        hp_max=craft_essence.hp_max,
        skills=[_craft_essence_skill_message(skill) for skill in craft_essence.skills],
    )


def _craft_essence_skill_message(
    skill: CraftEssenceSkill,
) -> craft_essence_pb2.CraftEssenceSkill:
    return craft_essence_pb2.CraftEssenceSkill(
        id=skill.id,
        name=skill.name,
        original_name=skill.original_name,
        detail=skill.detail,
    )


def _mystic_code_message(mystic_code: MysticCode) -> mystic_code_pb2.MysticCode:
    return mystic_code_pb2.MysticCode(
        id=mystic_code.id,
        name=mystic_code.name,
        assets=mystic_code_pb2.Assets(
            male=mystic_code.assets.male,
            female=mystic_code.assets.female,
        ),
        skills=[_skill_message(skill) for skill in mystic_code.skills],
    )
