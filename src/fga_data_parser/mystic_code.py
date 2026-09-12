from dataclasses import dataclass, field

from .skill import Skill


@dataclass
class Assets:
    male: str
    female: str


@dataclass
class MysticCode:
    id: int
    name: str
    assets: Assets
    skills: list[Skill] = field(default_factory=list)
