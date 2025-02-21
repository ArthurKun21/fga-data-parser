from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict

from .enums import SkillTarget


@dataclass
class Skill:
    id: int
    num: int
    name: str
    detail: str
    icon: str
    cooldown: Dict[int, int] = field(default_factory=dict)
    target: List[SkillTarget] = field(default_factory=list)
    ascension: int | None = None
    targetAscension: int | None = None

    @classmethod
    def create(
        cls,
        id: int,
        num: int,
        name: str,
        detail: str,
        icon: str,
        cooldown: Dict[int, int],
        target: List[SkillTarget],
        ascension: int | None,
        targetAscension: int | None,
    ) -> Skill:
        """
        Create a new Skill instance.

        Args:
            id (int):
                The unique identifier of the skill.
            num (int):
                The skill number.
            name (str):
                The name of the skill.
            detail (str):
                The description or details of the skill.
            icon (str):
                The icon path or identifier for the skill.
            cooldown (List[int]):
                List of cooldown values for skill level(1, 6, 10)
            target (List[SkillTarget]):
                List of skill targets.
            ascension (int | None):
                The ascension level required for the skill.
                This is required for [SkillTarget.Transform].
                None if not applicable.
            targetAscension (int | None):
                The target ascension level required.
                This is required for [SkillTarget.Transform].
                None if not applicable.

        Returns:
            Skill: A new instance of the Skill class.
        """

        return cls(
            id=id,
            num=num,
            name=name,
            detail=detail,
            icon=icon,
            cooldown=cooldown,
            target=target,
            ascension=ascension,
            targetAscension=targetAscension,
        )
