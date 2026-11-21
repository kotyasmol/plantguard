import pytest
from plantguard_mining.text import RussianSymptomExtractor


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("Нижний лист постепенно желтеет", {"leaf-yellowing"}),
        ("Появились тёмные пятна и мелкие дырки", {"leaf-dark-spots", "leaf-tissue-damage"}),
        ("Края сухие, листья поникли", {"leaf-tissue-damage", "leaf-wilting"}),
        ("После перестановки начали опадать листья", {"leaf-drop"}),
        ("Лист пожелтел, но пятен нет", {"leaf-yellowing"}),
    ],
)
def test_extracts_supported_russian_symptoms(description, expected):
    result = RussianSymptomExtractor().extract(description)

    assert result.analyzable is True
    assert {finding.code for finding in result.findings} == expected


@pytest.mark.parametrize(
    "description",
    [
        "Листья не желтеют",
        "Нет пятен, разрывов и сухих краёв",
        "Растение без дырок на листьях",
        "Никаких признаков увядания",
    ],
)
def test_negated_symptoms_are_not_reported(description):
    result = RussianSymptomExtractor().extract(description)

    assert result.findings == ()


def test_empty_description_is_not_analyzable():
    result = RussianSymptomExtractor().extract("  ")

    assert result.analyzable is False
