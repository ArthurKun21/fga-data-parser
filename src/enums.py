from enum import StrEnum


class CardType(StrEnum):
    BUSTER = "buster"
    ARTS = "arts"
    QUICK = "quick"


class SkillTarget(StrEnum):
    Unknown = "Unknown"
    TargetOne = "TargetOne"
    TargetAll = "TargetAll"
    CommandNPType2 = "CommandNPType2"
    CommandNPType3 = "CommandNPType3"
    Choice2 = "Choice2"
    Choice3 = "Choice3"
    Transform = "Transform"
    OrderChange = "OrderChange"
