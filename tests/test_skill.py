from typing import Any

from fga_data_parser.enums import SkillTarget
from fga_data_parser.skill import ScriptButton, Skill, TransformDetail


def create_skill(
    *,
    cooldown: list[int] | None = None,
    ascension: int = 0,
    scripts: dict[str, Any] | None = None,
    functions: list[dict[str, Any]] | None = None,
) -> Skill:
    return Skill.create(
        id=1,
        num=1,
        name="Test Skill",
        detail="A test skill.",
        icon="icon.png",
        cooldown=[7, 6, 5, 4, 3, 2, 1] if cooldown is None else cooldown,
        ascension=ascension,
        scripts={} if scripts is None else scripts,
        functions=[] if functions is None else functions,
    )


def command_np_functions(names: list[str]) -> list[dict[str, Any]]:
    functions = [{"funcType": "addState", "funcTargetType": "commandTypeSelfTreasureDevice"}]
    functions.extend(
        {
            "funcType": "addState",
            "funcTargetType": "commandTypeSelfTreasureDevice",
            "buffs": [{"name": name}],
        }
        for name in names
    )
    return functions


def select_add_info_scripts(button_names: list[str]) -> dict[str, Any]:
    return {
        "SelectAddInfo": [{"title": "Choose one", "btn": [{"name": name} for name in button_names]}]
    }


def test_defaults_to_target_all_and_max_cooldown() -> None:
    skill = create_skill()

    assert skill.target == [SkillTarget.TargetAll]
    assert skill.cooldown == 7
    assert skill.script_buttons is None
    assert skill.buttons == []
    assert skill.transform is None


def test_empty_cooldown_defaults_to_zero() -> None:
    skill = create_skill(cooldown=[])

    assert skill.cooldown == 0


def test_target_one() -> None:
    skill = create_skill(functions=[{"funcType": "addState", "funcTargetType": "ptOne"}])

    assert skill.target == [SkillTarget.TargetOne]


def test_order_change() -> None:
    skill = create_skill(functions=[{"funcType": "addState", "funcTargetType": "ptselectOneSub"}])

    assert skill.target == [SkillTarget.OrderChange]


def test_command_np_type_three() -> None:
    skill = create_skill(functions=command_np_functions(["Quick", "Arts", "Buster"]))

    assert SkillTarget.CommandNPType3 in skill.target
    assert skill.buttons == [["Quick", "Arts", "Buster"]]


def test_command_np_type_two() -> None:
    skill = create_skill(functions=command_np_functions(["Quick", "Arts"]))

    assert SkillTarget.CommandNPType2 in skill.target
    assert skill.buttons == [["Quick", "Arts"]]


def test_single_command_np_type_is_ignored() -> None:
    skill = create_skill(functions=command_np_functions(["Quick"]))

    assert skill.target == [SkillTarget.TargetAll]
    assert skill.buttons == []


def test_target_one_with_command_np_types() -> None:
    functions = [
        {"funcType": "addState", "funcTargetType": "ptOne"},
        *command_np_functions(["Quick", "Arts"]),
    ]

    skill = create_skill(functions=functions)

    assert skill.target == [SkillTarget.TargetOne, SkillTarget.CommandNPType2]


def test_transform() -> None:
    skill = create_skill(
        ascension=2,
        functions=[
            {
                "funcType": "transformServant",
                "funcTargetType": "self",
                "svals": [{"SetLimitCount": 3}],
            }
        ],
    )

    assert SkillTarget.Transform in skill.target
    assert skill.transform == TransformDetail(ascension=2, target_ascension=3)


def test_transform_without_svals_has_no_target_ascension() -> None:
    skill = create_skill(
        ascension=1,
        functions=[{"funcType": "transformServant", "funcTargetType": "self", "svals": []}],
    )

    assert skill.transform == TransformDetail(ascension=1, target_ascension=None)


def test_two_buttons_create_choice2() -> None:
    skill = create_skill(scripts=select_add_info_scripts(["Buster", "Arts"]))

    assert skill.script_buttons == ScriptButton(title="Choose one", buttons=["Buster", "Arts"])
    assert skill.target == [SkillTarget.Choice2]


def test_three_buttons_create_choice3() -> None:
    skill = create_skill(scripts=select_add_info_scripts(["Buster", "Arts", "Quick"]))

    assert skill.script_buttons is not None
    assert skill.target == [SkillTarget.Choice3]


def test_other_button_counts_are_ignored() -> None:
    skill = create_skill(scripts=select_add_info_scripts(["Buster"]))

    assert skill.script_buttons is None
    assert skill.target == [SkillTarget.TargetAll]


def test_empty_button_names_are_skipped() -> None:
    scripts = {"SelectAddInfo": [{"title": "Choose", "btn": [{"name": ""}, {"name": "Arts"}]}]}

    skill = create_skill(scripts=scripts)

    assert skill.script_buttons is None
    assert skill.target == [SkillTarget.TargetAll]


def test_duplicate_targets_are_removed() -> None:
    functions = [
        {"funcType": "addState", "funcTargetType": "ptOne"},
        {"funcType": "addState", "funcTargetType": "ptOne"},
    ]

    skill = create_skill(functions=functions)

    assert skill.target == [SkillTarget.TargetOne]
