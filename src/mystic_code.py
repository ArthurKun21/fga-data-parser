from dataclasses import dataclass, field
from typing import Dict

from .skill import Skill


@dataclass
class MysticCode:
    id: int
    name: str
    assets: Dict[str, str]
    skills: list[Skill] = field(default_factory=list)
