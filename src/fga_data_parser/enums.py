from enum import StrEnum
from typing import Self


class CardType(StrEnum):
    Buster = "buster"
    Arts = "arts"
    Quick = "quick"

    @classmethod
    def from_atlas(cls, value: str) -> Self:
        """Map an Atlas noble Phantasm card value to a CardType.

        Atlas now encodes the card as the game's internal ID
        ("1" arts, "2" buster, "3" quick); older exports used the card names.
        """
        match value:
            case "2" | "buster":
                return cls.Buster
            case "1" | "arts":
                return cls.Arts
            case "3" | "quick":
                return cls.Quick
            case _:
                msg = f"Unknown noble Phantasm card type: {value!r}"
                raise ValueError(msg)


class SkillTarget(StrEnum):
    TargetOne = "TargetOne"
    TargetAll = "TargetAll"
    CommandNPType2 = "CommandNPType2"
    CommandNPType3 = "CommandNPType3"
    Choice2 = "Choice2"
    Choice3 = "Choice3"
    Transform = "Transform"
    OrderChange = "OrderChange"


class CraftEssenceFlag(StrEnum):
    """Acquisition/source flags for craft essences (Atlas "flag" field)."""

    Normal = "normal"
    SvtEquipCampaign = "svtEquipCampaign"
    SvtEquipChocolate = "svtEquipChocolate"
    SvtEquipEvent = "svtEquipEvent"
    SvtEquipEventReward = "svtEquipEventReward"
    SvtEquipExp = "svtEquipExp"
    SvtEquipFriendShip = "svtEquipFriendShip"
    SvtEquipManaExchange = "svtEquipManaExchange"
    Unknown = "unknown"
