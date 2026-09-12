import logging
from dataclasses import dataclass, field
from itertools import groupby
from typing import Any, Self

from .enums import SkillTarget

logger = logging.getLogger(__name__)


@dataclass
class ScriptButton:
    title: str
    buttons: list[str]


@dataclass
class TransformDetail:
    ascension: int
    target_ascension: int | None = None


@dataclass
class Skill:
    id: int
    num: int
    name: str
    detail: str
    icon: str
    cooldown: int
    target: list[SkillTarget] = field(default_factory=list)
    script_buttons: ScriptButton | None = None
    buttons: list[list[str]] = field(default_factory=list)
    transform: TransformDetail | None = None

    @classmethod
    def create(
        cls,
        id: int,
        num: int,
        name: str,
        detail: str,
        icon: str,
        cooldown: list[int],
        ascension: int,
        scripts: dict[str, Any],
        functions: list[dict[str, Any]],
    ) -> Self:
        """
        Create a new Skill instance from raw Atlas data.

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
            cooldown (list[int]):
                The cooldown values per skill level; only the highest is kept.
            ascension (int):
                The ascension the skill belongs to, used as the source
                ascension for [SkillTarget.Transform] skills.
            scripts (dict[str, Any]):
                The skill's raw "script" dictionary.
            functions (list[dict[str, Any]]):
                The skill's raw "functions" list.

        Returns:
            Skill: A new instance of the Skill class.
        """
        targets: list[SkillTarget] = []
        buttons: list[list[str]] = []

        title, command_buttons = cls._check_for_buttons_from_scripts(scripts)
        match len(command_buttons):
            case 2:
                script_buttons = ScriptButton(title=title, buttons=command_buttons)
                targets.append(SkillTarget.Choice2)
            case 3:
                script_buttons = ScriptButton(title=title, buttons=command_buttons)
                targets.append(SkillTarget.Choice3)
            case _:
                if command_buttons:
                    logger.debug(
                        "Ignoring %d command buttons from scripts: %s",
                        len(command_buttons),
                        command_buttons,
                    )
                script_buttons = None

        function_targets, np_type_buttons, target_ascension = cls._check_functions(functions)
        targets.extend(function_targets)

        # Add the NP type buttons if they exist
        if np_type_buttons:
            buttons.append(np_type_buttons)

        # Set the ascension levels if there is a transform skill
        transform_detail = None
        if SkillTarget.Transform in targets:
            transform_detail = TransformDetail(
                ascension=ascension,
                target_ascension=target_ascension,
            )

        # If no target is found, default to [SkillTarget.TargetAll]
        if len(targets) == 0:
            targets.append(SkillTarget.TargetAll)

        # Remove duplicates from the target list
        targets = [k for k, _ in groupby(targets)]

        # Only take the highest cooldown value
        return cls(
            id=id,
            num=num,
            name=name,
            detail=detail,
            icon=icon,
            cooldown=max(cooldown, default=0),
            target=targets,
            script_buttons=script_buttons,
            buttons=buttons,
            transform=transform_detail,
        )

    @staticmethod
    def _check_for_buttons_from_scripts(
        scripts: dict[str, Any],
    ) -> tuple[str, list[str]]:
        """
        Extracts button information from a script dictionary.
        This static method processes script data to extract button names and their associated title.
        It specifically looks for 'SelectAddInfo' and its contained button information.
        Args:
            scripts (dict[str, Any]): A dictionary containing script information
                with 'SelectAddInfo' data.
        Returns:
            tuple[str, list[str]]: A tuple containing:
                - str: The title associated with the selection (empty string if not found)
                - list[str]: List of button names found in the scripts (empty list if none found)
        Example:
            title, buttons = _check_for_buttons_from_scripts(script_data)
        """

        targets = []
        select_add_info: list[dict[str, Any]] = scripts.get("SelectAddInfo", [])
        if len(select_add_info) == 0:
            return "", targets

        first_select_add_info = select_add_info[0]

        title = first_select_add_info.get("title", "")

        button_info: list[dict[str, Any]] = first_select_add_info.get("btn", [])
        if len(button_info) == 0:
            return "", targets

        for button in button_info:
            button_name = button.get("name", "")
            if len(button_name) == 0:
                continue
            targets.append(button_name)

        return title, targets

    @staticmethod
    def _check_functions(
        functions: list[dict[str, Any]],
    ) -> tuple[list[SkillTarget], list[str], int | None]:
        targets: list[SkillTarget] = []

        command_np_found: bool | None = None
        command_np_list: list[str] = []

        target_ascension: int | None = None

        for function in functions:
            func_type = function.get("funcType", "")
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
                            buffs: list[dict[str, Any]] = function.get("buffs", [])
                            if not buffs:
                                continue
                            command_type_buff = buffs[0]
                            command_name = command_type_buff.get("name", "")
                            if command_name:
                                command_np_list.append(command_name)
                        case False:
                            pass
                case "ptselectOneSub":
                    targets.append(SkillTarget.OrderChange)
                case _:
                    if command_np_found is not None:
                        command_np_found = False

            match func_type:
                case "transformServant":
                    targets.append(SkillTarget.Transform)
                    svals: list[dict[str, Any]] = function.get("svals", [])
                    if not svals:
                        continue
                    transform_info = svals[0]
                    target_ascension = transform_info.get("SetLimitCount")
                case _:
                    pass

        match len(command_np_list):
            case 2:
                targets.append(SkillTarget.CommandNPType2)
            case 3:
                targets.append(SkillTarget.CommandNPType3)
            case _:
                # Command NP buttons are only meaningful alongside a
                # CommandNPType2/3 target, so drop orphans.
                if command_np_list:
                    logger.debug(
                        "Ignoring %d command NP types: %s", len(command_np_list), command_np_list
                    )
                command_np_list = []

        return targets, command_np_list, target_ascension
