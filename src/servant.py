from dataclasses import dataclass
from typing import List

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
    name: str
    class_name: str
    rarity: int
    np: List[NoblePhantasm]
    skills: List[Skill]
