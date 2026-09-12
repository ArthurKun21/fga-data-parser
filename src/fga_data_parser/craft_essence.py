from dataclasses import dataclass, field

from .enums import CraftEssenceFlag


@dataclass
class CraftEssenceSkill:
    id: int
    name: str
    original_name: str
    detail: str


@dataclass
class CraftEssenceAssets:
    chara_graph: dict[str, str]
    faces: dict[str, str]
    equip_face: dict[str, str]


@dataclass
class CraftEssence:
    id: int
    collection_no: int
    name: str
    original_name: str
    type: str
    flag: CraftEssenceFlag
    rarity: int
    cost: int
    assets: CraftEssenceAssets
    atk_max: int
    hp_max: int
    skills: list[CraftEssenceSkill] = field(default_factory=list)
