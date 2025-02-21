from enum import StrEnum


class CardType(StrEnum):
    BUSTER = "buster"
    ARTS = "arts"
    QUICK = "quick"


class SkillTarget(StrEnum):
    Unknown = "unknown"
    TargetOne = "target_one"
    TargetAll = "target_all"
    CommandNPType2 = "command_np_type_2"
    CommandNPType3 = "command_np_type_3"
    Choice2 = "choice_2"
    Choice3 = "choice_3"
    Transform = "transform"
    OrderChange = "order_change"
