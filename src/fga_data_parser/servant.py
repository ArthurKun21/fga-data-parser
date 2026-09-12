from dataclasses import dataclass

from .enums import CardType
from .skill import Skill


@dataclass
class NoblePhantasm:
    id: int
    num: int
    name: str
    card_type: CardType


@dataclass
class Servant:
    id: int
    collection_no: int
    name: str
    class_name: str
    rarity: int
    nps: list[NoblePhantasm]
    skills: list[Skill]
