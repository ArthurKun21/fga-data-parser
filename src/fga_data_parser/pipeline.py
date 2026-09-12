import logging
from typing import Any

from .craft_essence import CraftEssence, CraftEssenceAssets, CraftEssenceSkill
from .enums import CardType, CraftEssenceFlag, ServantFlag
from .mystic_code import Assets, MysticCode
from .servant import (
    AppendPassive,
    AppendPassiveSkill,
    NoblePhantasm,
    Servant,
    ServantAssetGroup,
    ServantAssets,
)
from .skill import Skill

logger = logging.getLogger(__name__)

# Only these servant types are playable in FGO.
PLAYABLE_TYPES = {"normal", "heroine"}


def build_servants(raw_servants: list[dict[str, Any]]) -> list[Servant]:
    """Convert raw Atlas servant data into Servant models, sorted by collection number."""
    playable = [raw for raw in raw_servants if raw.get("type") in PLAYABLE_TYPES]
    playable.sort(key=lambda raw: raw.get("collectionNo", 0))

    servant_list: list[Servant] = []

    # To prevent duplicate names
    name_cache: set[str] = set()

    for raw in playable:
        class_name = raw.get("className", "")
        name = _fix_name(
            raw.get("name", ""),
            gender=raw.get("gender", ""),
            class_name=class_name,
            rarity=raw.get("rarity", 0),
        )
        name = _dedupe_name(name, class_name=class_name, seen=name_cache)

        servant = Servant(
            id=raw.get("id", 0),
            collection_no=raw.get("collectionNo", 0),
            name=name,
            class_name=class_name,
            rarity=raw.get("rarity", 0),
            flag=ServantFlag(raw.get("flag", "")),
            assets=_build_servant_assets(
                raw.get("extraAssets", {}), collection_no=raw.get("collectionNo", 0)
            ),
            gender=raw.get("gender", ""),
            nps=_build_nps(raw.get("noblePhantasms", [])),
            skills=_parse_skills(raw.get("skills", [])),
            append_passives=_build_append_passives(raw.get("appendPassive", [])),
        )
        servant_list.append(servant)

    return servant_list


def build_mystic_codes(raw_mystic_codes: list[dict[str, Any]]) -> list[MysticCode]:
    """Convert raw Atlas mystic code data into MysticCode models, sorted by id."""
    mystic_code_list: list[MysticCode] = []

    for raw in raw_mystic_codes:
        item_assets = raw.get("extraAssets", {}).get("item", {})
        mystic_code = MysticCode(
            id=raw.get("id", 0),
            name=raw.get("name", ""),
            assets=Assets(
                male=item_assets.get("male", ""),
                female=item_assets.get("female", ""),
            ),
            skills=_parse_skills(raw.get("skills", []), num_from_index=True),
        )
        mystic_code_list.append(mystic_code)

    mystic_code_list.sort(key=lambda mystic_code: mystic_code.id)
    return mystic_code_list


def build_craft_essences(raw_equips: list[dict[str, Any]]) -> list[CraftEssence]:
    """Convert raw Atlas craft essence data into CraftEssence models.

    Sorted by collection number.
    """
    craft_essence_list: list[CraftEssence] = []

    for raw in raw_equips:
        craft_essence = CraftEssence(
            id=raw.get("id", 0),
            collection_no=raw.get("collectionNo", 0),
            name=raw.get("name", ""),
            original_name=raw.get("originalName", ""),
            type=raw.get("type", ""),
            flag=CraftEssenceFlag(raw.get("flag", "")),
            rarity=raw.get("rarity", 0),
            cost=raw.get("cost", 0),
            assets=_build_craft_essence_assets(raw.get("extraAssets", {})),
            atk_max=raw.get("atkMax", 0),
            hp_max=raw.get("hpMax", 0),
            skills=_build_craft_essence_skills(raw.get("skills", [])),
        )
        craft_essence_list.append(craft_essence)

    craft_essence_list.sort(key=lambda craft_essence: craft_essence.collection_no)
    return craft_essence_list


def _build_craft_essence_assets(extra_assets: dict[str, Any]) -> CraftEssenceAssets:
    def equip_images(group: str) -> dict[str, str]:
        return extra_assets.get(group, {}).get("equip", {})

    return CraftEssenceAssets(
        chara_graph=equip_images("charaGraph"),
        faces=equip_images("faces"),
        equip_face=equip_images("equipFace"),
    )


def _build_craft_essence_skills(raw_skills: list[dict[str, Any]]) -> list[CraftEssenceSkill]:
    skills: list[CraftEssenceSkill] = []
    for raw in raw_skills:
        skill = CraftEssenceSkill(
            id=raw.get("id", 0),
            name=raw.get("name", ""),
            original_name=raw.get("originalName", ""),
            detail=raw.get("detail", ""),
        )
        skills.append(skill)
    return skills


def _fix_name(name: str, *, gender: str, class_name: str, rarity: int) -> str:
    """Apply manual name fixes so names match what FGA expects."""
    # Atlas spells it "Altria"; use the official "Artoria" localization.
    if "Altria" in name:
        name = name.replace("Altria", "Artoria")

    # The summer version of BB shares the base name in the data.
    if name == "BB" and rarity == 5:
        name = "BB (Summer)"

    # The female Kishinami Hakuno (Caster) is better known as Hakunon.
    if name == "Kishinami Hakuno" and gender == "female":
        name = "Kishinami Hakunon"

    # Summer Ereshkigal ships under her beast class name.
    if name == "Ereshkigal" and class_name == "beastEresh":
        name = "Ereshkigal (Summer)"

    return name


def _dedupe_name(name: str, *, class_name: str, seen: set[str]) -> str:
    """Ensure a unique name by suffixing the servant's class until it is."""
    if name not in seen:
        seen.add(name)
        return name

    candidate = f"{name} ({class_name})"
    counter = 2
    while candidate in seen:
        candidate = f"{name} ({class_name}) {counter}"
        counter += 1
    seen.add(candidate)
    return candidate


def _build_servant_assets(extra_assets: dict[str, Any], *, collection_no: int) -> ServantAssets:
    def asset_group(group: str) -> ServantAssetGroup:
        group_assets = extra_assets.get(group, {})
        return ServantAssetGroup(
            ascension=group_assets.get("ascension", {}),
            costume=group_assets.get("costume", {}),
            transform_group=group_assets.get("transformGroup", {}),
        )

    chara_graph = asset_group("charaGraph")
    # Special case: servants without a collection number are not obtainable
    # yet (upcoming or NPC-only), so skip their card art.
    if collection_no == 0:
        chara_graph = ServantAssetGroup()

    return ServantAssets(
        chara_graph=chara_graph,
        faces=asset_group("faces"),
        commands=asset_group("commands"),
        status=asset_group("status"),
    )


def _build_append_passives(raw_append_passives: list[dict[str, Any]]) -> list[AppendPassive]:
    append_passives: list[AppendPassive] = []
    for raw in raw_append_passives:
        skill = raw.get("skill", {})
        append_passive = AppendPassive(
            num=raw.get("num", 0),
            skill=AppendPassiveSkill(
                id=skill.get("id", 0),
                num=skill.get("num", 0),
                name=skill.get("name", ""),
                original_name=skill.get("originalName", ""),
                detail=skill.get("detail", ""),
                icon=skill.get("icon", ""),
            ),
        )
        append_passives.append(append_passive)
    return append_passives


def _build_nps(raw_nps: list[dict[str, Any]]) -> list[NoblePhantasm]:
    nps: list[NoblePhantasm] = []
    for raw in raw_nps:
        np = NoblePhantasm(
            id=raw.get("id", 0),
            num=raw.get("num", 0),
            name=raw.get("name", ""),
            card_type=CardType.from_atlas(raw.get("card", "")),
        )
        nps.append(np)
    return nps


def _parse_skills(
    raw_skills: list[dict[str, Any]],
    *,
    num_from_index: bool = False,
) -> list[Skill]:
    """Convert raw Atlas skill dicts into Skill models.

    num_from_index: mystic code skills all report num 0 in the Atlas export
    (an Atlas bug), so their position is used as the skill number instead.
    """
    skill_list: list[Skill] = []
    for index, raw in enumerate(raw_skills):
        skill = Skill.create(
            id=raw.get("id", 0),
            num=index if num_from_index else raw.get("num", 0),
            name=raw.get("name", ""),
            detail=raw.get("unmodifiedDetail", ""),
            icon=raw.get("icon", ""),
            cooldown=raw.get("coolDown", []),
            ascension=raw.get("priority", 0),
            scripts=raw.get("script", {}),
            functions=raw.get("functions", []),
        )
        skill_list.append(skill)
    return skill_list
