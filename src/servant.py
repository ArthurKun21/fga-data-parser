from dataclasses import dataclass
from typing import List

from .enums import CardType
from .skill import Skill


@dataclass
class NoblePhantasm:
    id: int
    name: str
    card_type: CardType


@dataclass
class Servant:
    id: int
    name: str
    class_name: str
    rarity: int
    np: NoblePhantasm
    skills: List[Skill]
