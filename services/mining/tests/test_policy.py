import pytest
from plantguard_mining import (
    AssessmentSignals,
    Evidence,
    IdentificationCandidate,
    RiskLevel,
    evaluate,
)


def test_low_identification_confidence_requires_confirmation():
    assessment = evaluate(
        AssessmentSignals(
            identification=[
                IdentificationCandidate("ficus-benjamina", "Фикус Бенджамина", 0.62)
            ],
            visual_findings=[],
            text_findings=[],
        )
    )

    assert assessment.requires_species_confirmation is True
    assert assessment.risk is RiskLevel.UNDETERMINED


def test_extreme_humidity_and_multiple_findings_produce_high_risk():
    assessment = evaluate(
        AssessmentSignals(
            identification=[
                IdentificationCandidate("ficus-benjamina", "Фикус Бенджамина", 0.91)
            ],
            visual_findings=[Evidence("leaf-yellowing", 0.82, "image")],
            text_findings=[Evidence("recent-leaf-drop", 0.76, "text")],
            humidity_pct=91,
        )
    )

    assert assessment.risk is RiskLevel.HIGH
    assert assessment.requires_species_confirmation is False
    assert "Проверить влажность субстрата" in assessment.recommended_actions[-1]


def test_incomparable_photos_request_another_photo():
    assessment = evaluate(
        AssessmentSignals(
            identification=[],
            visual_findings=[],
            text_findings=[],
            photos_comparable=False,
        )
    )

    assert assessment.requires_more_data is True
    assert any("Повторить фотографию" in action for action in assessment.recommended_actions)


def test_invalid_confidence_is_rejected():
    with pytest.raises(ValueError, match="confidence"):
        evaluate(
            AssessmentSignals(
                identification=[IdentificationCandidate("unknown", "Неизвестно", 1.1)],
                visual_findings=[],
                text_findings=[],
            )
        )
