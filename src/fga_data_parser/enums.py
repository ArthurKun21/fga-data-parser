from enum import StrEnum
from typing import Self


class CardType(StrEnum):
    BUSTER = "buster"
    ARTS = "arts"
    QUICK = "quick"

    @classmethod
    def from_atlas(cls, value: str) -> Self:
        """Map an Atlas noble Phantasm card value to a CardType.

        Atlas now encodes the card as the game's internal ID
        ("1" arts, "2" buster, "3" quick); older exports used the card names.
        """
        match value:
            case "2" | "buster":
                return cls.BUSTER
            case "1" | "arts":
                return cls.ARTS
            case "3" | "quick":
                return cls.QUICK
            case _:
                msg = f"Unknown noble Phantasm card type: {value!r}"
                raise ValueError(msg)


class NoblePhantasmTarget(StrEnum):
    """Targeting behavior of a noble Phantasm; unlike SkillTarget it is not UI-facing."""

    NOBLE_PHANTASM_TARGET_TRANSFORM = "Transform"


class SkillTarget(StrEnum):
    TARGET_ONE = "TargetOne"
    TARGET_ALL = "TargetAll"
    COMMAND_NP_TYPE_2 = "CommandNPType2"
    COMMAND_NP_TYPE_3 = "CommandNPType3"
    CHOICE_2 = "Choice2"
    CHOICE_3 = "Choice3"
    TRANSFORM = "Transform"
    ORDER_CHANGE = "OrderChange"


class ServantFlag(StrEnum):
    """Availability/combination flags for servants (Atlas "flag" field)."""

    NORMAL = "normal"
    IGNORE_COMBINE_LIMIT_SPECIAL = "ignoreCombineLimitSpecial"
    GOETIA = "goetia"


class CraftEssenceFlag(StrEnum):
    """Acquisition/source flags for craft essences (Atlas "flag" field)."""

    NORMAL = "normal"
    SVT_EQUIP_CAMPAIGN = "svtEquipCampaign"
    SVT_EQUIP_CHOCOLATE = "svtEquipChocolate"
    SVT_EQUIP_EVENT = "svtEquipEvent"
    SVT_EQUIP_EVENT_REWARD = "svtEquipEventReward"
    SVT_EQUIP_EXP = "svtEquipExp"
    SVT_EQUIP_FRIEND_SHIP = "svtEquipFriendShip"
    SVT_EQUIP_MANA_EXCHANGE = "svtEquipManaExchange"
    UNKNOWN = "unknown"
