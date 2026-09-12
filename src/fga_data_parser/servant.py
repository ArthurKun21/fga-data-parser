from dataclasses import dataclass

from .enums import CardType, ServantFlag
from .skill import Skill


@dataclass
class NoblePhantasm:
    id: int
    num: int
    name: str
    card_type: CardType


@dataclass
class ServantAssetGroup:
    ascension: dict[str, str]
    costume: dict[str, str]


@dataclass
class ServantAssets:
    chara_graph: ServantAssetGroup
    faces: ServantAssetGroup
    commands: ServantAssetGroup
    status: ServantAssetGroup


@dataclass
class AppendPassiveSkill:
    id: int
    num: int
    name: str
    original_name: str
    detail: str
    icon: str


@dataclass
class AppendPassive:
    num: int
    skill: AppendPassiveSkill


@dataclass
class Servant:
    id: int
    collection_no: int
    name: str
    class_name: str
    rarity: int
    flag: ServantFlag
    assets: ServantAssets
    gender: str
    nps: list[NoblePhantasm]
    skills: list[Skill]
    append_passives: list[AppendPassive]
