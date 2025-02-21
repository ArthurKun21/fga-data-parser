from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from itertools import groupby
from .enums import SkillTarget


@dataclass
class Skill:
    id: int
    num: int
    name: str
    detail: str
    icon: str
    cooldown: int | None = None
    target: List[SkillTarget] = field(default_factory=list)
    buttons: List[List[str]] = field(default_factory=list)
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
        priority: int,
        cooldown: List[int],
        scripts: Dict,
        functions: List[Dict],
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
        buttons = []

        targets = []
        command_buttons = cls._check_for_buttons_from_scripts(scripts=scripts)
        match len(command_buttons):
            case 2:
                buttons.append(command_buttons)
                targets.append(SkillTarget.Choice2)
            case 3:
                buttons.append(command_buttons)
                targets.append(SkillTarget.Choice3)
            case _:
                pass

        parse_targets, np_type_buttons, target_ascension = cls._check_functions(
            functions=functions
        )
        targets.extend(parse_targets)

        # Add the NP type buttons if they exist
        if len(np_type_buttons) > 0:
            buttons.append(np_type_buttons)

        # Set the ascension level if there is a transform skill
        if SkillTarget.Transform in targets:
            ascension = priority
        else:
            ascension = None

        # If no target is found, default to [SkillTarget.TargetAll]
        if len(targets) == 0:
            targets.append(SkillTarget.TargetAll)

        # Remove duplicates from the target list
        targets = [k for k, _ in groupby(targets)]

        # Only take the highest cooldown value
        parse_cooldown = max(cooldown)

        return cls(
            id=id,
            num=num,
            name=name,
            detail=detail,
            icon=icon,
            cooldown=parse_cooldown,
            target=targets,
            ascension=ascension,
            targetAscension=target_ascension,
            buttons=buttons,
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

    @staticmethod
    def _check_functions(
        functions: List[Dict],
    ) -> Tuple[List[SkillTarget], List[str], int | None]:
        targets: list[SkillTarget] = []

        command_np_found: bool | None = None
        command_np_list: List[str] = []

        target_ascension: int | None = None

        for function in functions:
            target_type = function.get("funcTargetType", "")
            if len(target_type) == 0:
                continue

            match target_type:
                case "ptOne":
                    if command_np_found is not None:
                        command_np_found = False
                    targets.append(SkillTarget.TargetOne)
                case "commandTypeSelfTreasureDevice":
                    match command_np_found:
                        case None:
                            command_np_found = True
                        case True:
                            buffs: list[dict] = function.get("buffs", [])
                            if not buffs:
                                continue
                            command_type_buff = buffs[0]
                            command_name = command_type_buff.get("name", "")
                            if command_name:
                                command_np_list.append(command_name)
                        case False:
                            pass
                case "transformServant":
                    targets.append(SkillTarget.Transform)
                    svals: list[dict] = function.get("svals", [])
                    if not svals:
                        continue
                    transform_info = svals[0]
                    target_ascension = transform_info.get("SetLimitCount", 0)
                case "ptselectOneSub":
                    targets.append(SkillTarget.OrderChange)
                case _:
                    if command_np_found is not None:
                        command_np_found = False

            if command_np_found is False:
                match len(command_np_list):
                    case 2:
                        targets.append(SkillTarget.CommandNPType2)
                    case 3:
                        targets.append(SkillTarget.CommandNPType3)
                    case _:
                        pass
                command_np_found = None

        return targets, command_np_list, target_ascension
