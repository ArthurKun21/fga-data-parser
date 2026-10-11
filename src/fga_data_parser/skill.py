import logging
from dataclasses import dataclass, field
from typing import Any, Self

from .enums import SkillTarget

logger = logging.getLogger(__name__)


@dataclass
class Choice2Detail:
    detail: str
    option_a: str
    option_b: str


@dataclass
class Choice3Detail:
    detail: str
    option_a: str
    option_b: str
    option_c: str


@dataclass
class NoblePhantasm2Update:
    detail: str
    option_a: str
    option_b: str


@dataclass
class NoblePhantasm3Update:
    detail: str
    option_a: str
    option_b: str
    option_c: str


@dataclass
class TransformDetail:
    # target: id of the servant being transformed into (raw svals "Value").
    # ascension: ascension of the transform target (raw svals "SetLimitCount");
    # only meaningful when target is the servant's own id.
    target: int
    ascension: int


@dataclass
class ScriptFunction:
    target: SkillTarget
    choice2: Choice2Detail | None = None
    choice3: Choice3Detail | None = None
    np2: NoblePhantasm2Update | None = None
    np3: NoblePhantasm3Update | None = None
    transform: TransformDetail | None = None


@dataclass
class Skill:
    id: int
    num: int
    name: str
    detail: str
    icon: str
    cooldown: int
    functions: list[ScriptFunction] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        id: int,
        num: int,
        name: str,
        detail: str,
        icon: str,
        cooldown: list[int],
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
            scripts (dict[str, Any]):
                The skill's raw "script" dictionary.
            functions (list[dict[str, Any]]):
                The skill's raw "functions" list.

        Returns:
            Skill: A new instance of the Skill class.
        """
        script_functions: list[ScriptFunction] = []

        # Choices come from the script, every other target from the functions.
        choice = cls._check_for_choice_from_scripts(scripts)
        if choice is not None:
            script_functions.append(choice)
        script_functions.extend(cls._check_functions(functions))

        # If no target is found, default to [SkillTarget.TARGET_ALL]
        if len(script_functions) == 0:
            script_functions.append(ScriptFunction(target=SkillTarget.TARGET_ALL))

        script_functions = cls._dedupe_functions(script_functions)

        # Only take the highest cooldown value
        return cls(
            id=id,
            num=num,
            name=name,
            detail=detail,
            icon=icon,
            cooldown=max(cooldown, default=0),
            functions=script_functions,
        )

    @staticmethod
    def _check_for_choice_from_scripts(scripts: dict[str, Any]) -> ScriptFunction | None:
        """
        Build the choice ScriptFunction from a skill's "script" dictionary.

        Looks for 'SelectAddInfo' and maps its title and button names onto a
        Choice2/Choice3 entry. The title becomes the payload detail because the
        raw button entries carry no description text. Button counts other than
        2 or 3 are ignored.

        Args:
            scripts (dict[str, Any]): A dictionary containing script information
                with 'SelectAddInfo' data.

        Returns:
            ScriptFunction | None: The choice entry, or None when the script
                has no usable selection.
        """
        select_add_info: list[dict[str, Any]] = scripts.get("SelectAddInfo", [])
        if len(select_add_info) == 0:
            return None

        first_select_add_info = select_add_info[0]
        title = first_select_add_info.get("title", "")

        button_info: list[dict[str, Any]] = first_select_add_info.get("btn", [])
        options: list[str] = []
        for button in button_info:
            name = button.get("name", "")
            if name:
                options.append(name)

        match len(options):
            case 2:
                return ScriptFunction(
                    target=SkillTarget.CHOICE_2,
                    choice2=Choice2Detail(detail=title, option_a=options[0], option_b=options[1]),
                )
            case 3:
                return ScriptFunction(
                    target=SkillTarget.CHOICE_3,
                    choice3=Choice3Detail(
                        detail=title,
                        option_a=options[0],
                        option_b=options[1],
                        option_c=options[2],
                    ),
                )
            case _:
                if options:
                    logger.debug(
                        "Ignoring %d command buttons from scripts: %s",
                        len(options),
                        options,
                    )
                return None

    @staticmethod
    def _check_functions(functions: list[dict[str, Any]]) -> list[ScriptFunction]:
        """
        Derive the function-driven ScriptFunction entries from raw Atlas functions.

        Each relevant function contributes at most one entry. The command NP type
        change is appended last because it spans several functions: the
        player-team function's funcPopupText describes the effect (the payload
        detail) and each enemy-team function's funcPopupText is one option.

        Args:
            functions (list[dict[str, Any]]): The skill's raw "functions" list.

        Returns:
            list[ScriptFunction]: The derived entries, possibly empty.
        """
        script_functions: list[ScriptFunction] = []

        np_detail: str | None = None
        np_options: list[str] = []

        for function in functions:
            target_type = function.get("funcTargetType", "")
            if len(target_type) == 0:
                continue

            match target_type:
                case "ptOne":
                    script_functions.append(ScriptFunction(target=SkillTarget.TARGET_ONE))
                case "ptselectOneSub":
                    script_functions.append(ScriptFunction(target=SkillTarget.ORDER_CHANGE))
                case "commandTypeSelfTreasureDevice":
                    popup_text = function.get("funcPopupText", "")
                    if function.get("funcTargetTeam", "") == "enemy":
                        if popup_text:
                            np_options.append(popup_text)
                    elif np_detail is None:
                        np_detail = popup_text
                case _:
                    pass

            match function.get("funcType", ""):
                case "transformServant":
                    script_functions.append(Skill._transform_function(function))
                case _:
                    pass

        match len(np_options):
            case 2:
                script_functions.append(
                    ScriptFunction(
                        target=SkillTarget.COMMAND_NP_TYPE_2,
                        np2=NoblePhantasm2Update(
                            detail=np_detail or "",
                            option_a=np_options[0],
                            option_b=np_options[1],
                        ),
                    )
                )
            case 3:
                script_functions.append(
                    ScriptFunction(
                        target=SkillTarget.COMMAND_NP_TYPE_3,
                        np3=NoblePhantasm3Update(
                            detail=np_detail or "",
                            option_a=np_options[0],
                            option_b=np_options[1],
                            option_c=np_options[2],
                        ),
                    )
                )
            case _:
                # Command NP options are only meaningful alongside a
                # CommandNPType2/3 target, so drop orphans.
                if np_options:
                    logger.debug("Ignoring %d command NP types: %s", len(np_options), np_options)

        return script_functions

    @staticmethod
    def _transform_function(function: dict[str, Any]) -> ScriptFunction:
        """
        Build the Transform entry from a transformServant function.

        The payload needs the transform target's servant id (svals "Value") and
        its ascension (svals "SetLimitCount"); without svals there is nothing
        to record, so only the target survives.

        Args:
            function (dict[str, Any]): The raw transformServant function.

        Returns:
            ScriptFunction: The transform entry.
        """
        svals: list[dict[str, Any]] = function.get("svals", [])
        if not svals:
            return ScriptFunction(target=SkillTarget.TRANSFORM)

        transform_info = svals[0]
        return ScriptFunction(
            target=SkillTarget.TRANSFORM,
            transform=TransformDetail(
                target=transform_info.get("Value", 0),
                ascension=transform_info.get("SetLimitCount", 0),
            ),
        )

    @staticmethod
    def _dedupe_functions(functions: list[ScriptFunction]) -> list[ScriptFunction]:
        """Collapse consecutive same-target entries into the first, keeping any payload."""
        deduped: list[ScriptFunction] = []
        for function in functions:
            if deduped and deduped[-1].target == function.target:
                previous = deduped[-1]
                previous.choice2 = previous.choice2 or function.choice2
                previous.choice3 = previous.choice3 or function.choice3
                previous.np2 = previous.np2 or function.np2
                previous.np3 = previous.np3 or function.np3
                previous.transform = previous.transform or function.transform
                continue
            deduped.append(function)
        return deduped
