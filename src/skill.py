from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

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

        if len(np_type_buttons) > 0:
            buttons.append(np_type_buttons)

        # If no target is found, default to [SkillTarget.TargetAll]
        if len(targets) == 0:
            targets.append(SkillTarget.TargetAll)

        parse_cooldown = cls._create_cooldown_dict(cooldown=cooldown)

        return cls(
            id=id,
            num=num,
            name=name,
            detail=detail,
            icon=icon,
            cooldown=parse_cooldown,
            target=targets,
            targetAscension=target_ascension,
            buttons=buttons,
        )

    @staticmethod
    def _create_cooldown_dict(
        cooldown: List[int],
    ) -> Dict[int, int]:
        """
        Create a dictionary of cooldown values for skill levels.

        Args:
            cooldown (List[int]):
                List of cooldown values for skill level(1, 6, 10)

        Returns:
            Dict[int, int]: A dictionary containing cooldown values for skill levels.
        """
        cooldown_dict = {}
        if len(cooldown) == 10:
            cooldown_dict = {1: cooldown[0], 6: cooldown[5], 10: cooldown[9]}
        return cooldown_dict

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
