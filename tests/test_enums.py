import pytest

from fga_data_parser.enums import CardType


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", CardType.Arts),
        ("2", CardType.Buster),
        ("3", CardType.Quick),
        ("arts", CardType.Arts),
        ("buster", CardType.Buster),
        ("quick", CardType.Quick),
    ],
)
def test_from_atlas(value: str, expected: CardType) -> None:
    assert CardType.from_atlas(value) is expected


def test_from_atlas_unknown_value_raises() -> None:
    with pytest.raises(ValueError, match="Unknown noble Phantasm card type"):
        CardType.from_atlas("4")
