from dataclasses import dataclass, field

from .enums import CardType, NoblePhantasmTarget, ServantFlag
from .skill import Skill, SkillLocked


@dataclass
class NoblePhantasm:
    id: int
    num: int
    name: str
    detail: str
    card_type: CardType
    targets: list[NoblePhantasmTarget] = field(default_factory=list)
    # Stage gates (see SkillLocked); empty = available in every form.
    locked: list[SkillLocked] = field(default_factory=list)


@dataclass
class ServantAssetGroup:
    ascension: dict[str, str] = field(default_factory=dict)
    costume: dict[str, str] = field(default_factory=dict)
    transform_group: dict[str, str] = field(default_factory=dict)


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
    # Servant ids this form swaps with (via transform skills or NPs); always
    # references both ways even when the raw data only transforms one way.
    alternate_forms_id: list[int] = field(default_factory=list)
