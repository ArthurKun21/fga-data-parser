from typing import Any

from fga_data_parser.enums import SkillTarget
from fga_data_parser.skill import (
    Choice2Detail,
    Choice3Detail,
    NoblePhantasm2Update,
    NoblePhantasm3Update,
    ScriptFunction,
    Skill,
    TransformDetail,
)


def create_skill(
    *,
    cooldown: list[int] | None = None,
    scripts: dict[str, Any] | None = None,
    functions: list[dict[str, Any]] | None = None,
    limit_counts: list[int] | None = None,
) -> Skill:
    return Skill.create(
        id=1,
        num=1,
        name="Test Skill",
        detail="A test skill.",
        icon="icon.png",
        cooldown=[7, 6, 5, 4, 3, 2, 1] if cooldown is None else cooldown,
        scripts={} if scripts is None else scripts,
        functions=[] if functions is None else functions,
        limit_counts=[] if limit_counts is None else limit_counts,
    )


def command_np_functions(options: list[str]) -> list[dict[str, Any]]:
    functions = [
        {
            "funcType": "addStateShort",
            "funcTargetType": "commandTypeSelfTreasureDevice",
            "funcTargetTeam": "player",
            "funcPopupText": "NP type change",
        }
    ]
    functions.extend(
        {
            "funcType": "addStateShort",
            "funcTargetType": "commandTypeSelfTreasureDevice",
            "funcTargetTeam": "enemy",
            "funcPopupText": option,
        }
        for option in options
    )
    return functions


def select_add_info_scripts(button_names: list[str]) -> dict[str, Any]:
    return {
        "SelectAddInfo": [{"title": "Choose one", "btn": [{"name": name} for name in button_names]}]
    }


def test_defaults_to_target_all_and_max_cooldown() -> None:
    skill = create_skill()

    assert skill.functions == [ScriptFunction(target=SkillTarget.TARGET_ALL)]
    assert skill.cooldown == 7


def test_limit_counts_are_carried_through() -> None:
    skill = create_skill(limit_counts=[12, 13])

    assert skill.limit_counts == [12, 13]


def test_empty_cooldown_defaults_to_zero() -> None:
    skill = create_skill(cooldown=[])

    assert skill.cooldown == 0


def test_target_one() -> None:
    skill = create_skill(functions=[{"funcType": "addState", "funcTargetType": "ptOne"}])

    assert skill.functions == [ScriptFunction(target=SkillTarget.TARGET_ONE)]


def test_order_change() -> None:
    skill = create_skill(functions=[{"funcType": "addState", "funcTargetType": "ptselectOneSub"}])

    assert skill.functions == [ScriptFunction(target=SkillTarget.ORDER_CHANGE)]


def test_command_np_type_three() -> None:
    skill = create_skill(functions=command_np_functions(["Quick", "Arts", "Buster"]))

    assert skill.functions == [
        ScriptFunction(
            target=SkillTarget.COMMAND_NP_TYPE_3,
            np3=NoblePhantasm3Update(
                detail="NP type change", option_a="Quick", option_b="Arts", option_c="Buster"
            ),
        )
    ]


def test_command_np_type_two() -> None:
    skill = create_skill(functions=command_np_functions(["Quick", "Arts"]))

    assert skill.functions == [
        ScriptFunction(
            target=SkillTarget.COMMAND_NP_TYPE_2,
            np2=NoblePhantasm2Update(detail="NP type change", option_a="Quick", option_b="Arts"),
        )
    ]


def test_single_command_np_type_is_ignored() -> None:
    skill = create_skill(functions=command_np_functions(["Quick"]))

    assert skill.functions == [ScriptFunction(target=SkillTarget.TARGET_ALL)]


def test_command_np_options_without_popup_text_are_skipped() -> None:
    functions = [
        {
            "funcType": "addStateShort",
            "funcTargetType": "commandTypeSelfTreasureDevice",
            "funcTargetTeam": "enemy",
            "funcPopupText": "",
        },
        {
            "funcType": "addStateShort",
            "funcTargetType": "commandTypeSelfTreasureDevice",
            "funcTargetTeam": "enemy",
            "funcPopupText": "Arts",
        },
        {
            "funcType": "addStateShort",
            "funcTargetType": "commandTypeSelfTreasureDevice",
            "funcTargetTeam": "enemy",
            "funcPopupText": "Buster",
        },
    ]

    skill = create_skill(functions=functions)

    assert skill.functions == [
        ScriptFunction(
            target=SkillTarget.COMMAND_NP_TYPE_2,
            np2=NoblePhantasm2Update(detail="", option_a="Arts", option_b="Buster"),
        )
    ]


def test_target_one_with_command_np_types() -> None:
    functions = [
        {"funcType": "addState", "funcTargetType": "ptOne"},
        *command_np_functions(["Quick", "Arts"]),
    ]

    skill = create_skill(functions=functions)

    assert skill.functions == [
        ScriptFunction(target=SkillTarget.TARGET_ONE),
        ScriptFunction(
            target=SkillTarget.COMMAND_NP_TYPE_2,
            np2=NoblePhantasm2Update(detail="NP type change", option_a="Quick", option_b="Arts"),
        ),
    ]


def test_transform() -> None:
    skill = create_skill(
        functions=[
            {
                "funcType": "transformServant",
                "funcTargetType": "self",
                "svals": [{"Value": 100100, "SetLimitCount": 3}],
            }
        ]
    )

    assert skill.functions == [
        ScriptFunction(
            target=SkillTarget.TRANSFORM,
            transform=TransformDetail(target=100100, ascension=3),
        )
    ]


def test_transform_without_svals_has_no_payload() -> None:
    skill = create_skill(
        functions=[{"funcType": "transformServant", "funcTargetType": "self", "svals": []}]
    )

    assert skill.functions == [ScriptFunction(target=SkillTarget.TRANSFORM)]


def test_transform_with_act_select_index() -> None:
    skill = create_skill(
        functions=[
            {
                "funcType": "transformServant",
                "funcTargetType": "self",
                "svals": [{"Value": 505700, "SetLimitCount": 0, "ActSelectIndex": 1}],
            }
        ]
    )

    assert skill.functions == [
        ScriptFunction(
            target=SkillTarget.TRANSFORM,
            act_select_index=1,
            transform=TransformDetail(target=505700, ascension=0),
        )
    ]


def test_target_one_with_act_select_index() -> None:
    skill = create_skill(
        functions=[
            {
                "funcType": "addState",
                "funcTargetType": "ptOne",
                "svals": [{"ActSelectIndex": 1}],
            }
        ]
    )

    assert skill.functions == [ScriptFunction(target=SkillTarget.TARGET_ONE, act_select_index=1)]


def test_same_target_with_different_act_select_index_stays_distinct() -> None:
    functions = [
        {"funcType": "addState", "funcTargetType": "ptOne"},
        {"funcType": "addState", "funcTargetType": "ptOne", "svals": [{"ActSelectIndex": 1}]},
    ]

    skill = create_skill(functions=functions)

    assert skill.functions == [
        ScriptFunction(target=SkillTarget.TARGET_ONE),
        ScriptFunction(target=SkillTarget.TARGET_ONE, act_select_index=1),
    ]


def test_same_target_and_act_select_index_are_removed() -> None:
    functions = [
        {"funcType": "addState", "funcTargetType": "ptOne", "svals": [{"ActSelectIndex": 1}]},
        {"funcType": "addState", "funcTargetType": "ptOne", "svals": [{"ActSelectIndex": 1}]},
    ]

    skill = create_skill(functions=functions)

    assert skill.functions == [ScriptFunction(target=SkillTarget.TARGET_ONE, act_select_index=1)]


def test_two_buttons_create_choice2() -> None:
    skill = create_skill(scripts=select_add_info_scripts(["Buster", "Arts"]))

    assert skill.functions == [
        ScriptFunction(
            target=SkillTarget.CHOICE_2,
            choice2=Choice2Detail(detail="Choose one", option_a="Buster", option_b="Arts"),
        )
    ]


def test_three_buttons_create_choice3() -> None:
    skill = create_skill(scripts=select_add_info_scripts(["Buster", "Arts", "Quick"]))

    assert skill.functions == [
        ScriptFunction(
            target=SkillTarget.CHOICE_3,
            choice3=Choice3Detail(
                detail="Choose one", option_a="Buster", option_b="Arts", option_c="Quick"
            ),
        )
    ]


def test_other_button_counts_are_ignored() -> None:
    skill = create_skill(scripts=select_add_info_scripts(["Buster"]))

    assert skill.functions == [ScriptFunction(target=SkillTarget.TARGET_ALL)]


def test_empty_button_names_are_skipped() -> None:
    scripts = {"SelectAddInfo": [{"title": "Choose", "btn": [{"name": ""}, {"name": "Arts"}]}]}

    skill = create_skill(scripts=scripts)

    assert skill.functions == [ScriptFunction(target=SkillTarget.TARGET_ALL)]


def test_duplicate_targets_are_removed() -> None:
    functions = [
        {"funcType": "addState", "funcTargetType": "ptOne"},
        {"funcType": "addState", "funcTargetType": "ptOne"},
    ]

    skill = create_skill(functions=functions)

    assert skill.functions == [ScriptFunction(target=SkillTarget.TARGET_ONE)]
