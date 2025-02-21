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
        scripts: Dict,
        functions: Dict,
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
        targets = []
        command_buttons = cls._check_for_buttons_from_scripts(scripts=scripts)
        match len(command_buttons):
            case 2:
                targets.append(SkillTarget.Choice2)
            case 3:
                targets.append(SkillTarget.Choice3)
            case _:
                pass

        return cls(
            id=id,
            num=num,
            name=name,
            detail=detail,
            icon=icon,
            cooldown=cooldown,
        )

    @staticmethod
    def _check_for_buttons_from_scripts(
        scripts: Dict,
    ) -> List[str]:
        """
        Extract button names from script data.
        Given a dictionary containing script data, this method extracts button names from the
        SelectAddInfo field's button information.
        Args:
            scripts (Dict): A dictionary containing script data with potential SelectAddInfo field
        Returns:
            List[str]: A list of button names found in the scripts. Returns empty list if no valid
                      buttons are found.
        Example structure of scripts dict:
            {
                "SelectAddInfo": [
                    {
                        "btn": [
                            {"name": "button1"},
                            {"name": "button2"}
                        ]
                    }
                ]
            }
        """
        targets = []
        select_add_info: list[dict] = scripts.get("SelectAddInfo", [])
        if len(select_add_info) == 0:
            return targets

        first_select_add_info = select_add_info[0]
        button_info: list[dict] = first_select_add_info.get("btn", [])
        if len(button_info) == 0:
            return targets

        for button in button_info:
            button_name = button.get("name", "")
            if len(button_name) == 0:
                continue
            targets.append(button_name)

        return targets
