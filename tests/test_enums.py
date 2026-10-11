import pytest

from fga_data_parser.enums import CardType


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", CardType.ARTS),
        ("2", CardType.BUSTER),
        ("3", CardType.QUICK),
        ("arts", CardType.ARTS),
        ("buster", CardType.BUSTER),
        ("quick", CardType.QUICK),
    ],
)
def test_from_atlas(value: str, expected: CardType) -> None:
    assert CardType.from_atlas(value) is expected


def test_from_atlas_unknown_value_raises() -> None:
    with pytest.raises(ValueError, match="Unknown noble Phantasm card type"):
        CardType.from_atlas("4")
