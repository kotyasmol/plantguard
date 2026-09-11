"""Deterministic policy that combines model signals into a safe assessment."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum


class RiskLevel(str, Enum):
    UNDETERMINED = "undetermined"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


@dataclass(frozen=True)
class IdentificationCandidate:
    species_code: str
    display_name: str
    confidence: float


@dataclass(frozen=True)
class Evidence:
    code: str
    confidence: float
    source: str


@dataclass(frozen=True)
class AssessmentSignals:
    identification: Sequence[IdentificationCandidate]
    visual_findings: Sequence[Evidence]
    text_findings: Sequence[Evidence]
    humidity_pct: float | None = None
    temperature_c: float | None = None
    photos_comparable: bool | None = None


@dataclass(frozen=True)
class Assessment:
    risk: RiskLevel
    requires_species_confirmation: bool
    requires_more_data: bool
    evidence: tuple[Evidence, ...]
    recommended_actions: tuple[str, ...]
    policy_version: str = "1.0"


IDENTIFICATION_THRESHOLD = 0.80
FINDING_THRESHOLD = 0.65


def _validated_confidence(value: float) -> float:
    if not 0.0 <= value <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    return value


def evaluate(signals: AssessmentSignals) -> Assessment:
    """Combine structured signals without allowing a language model to set risk."""

    for candidate in signals.identification:
        _validated_confidence(candidate.confidence)
    for item in (*signals.visual_findings, *signals.text_findings):
        _validated_confidence(item.confidence)

    top_candidate = max(signals.identification, key=lambda item: item.confidence, default=None)
    requires_species_confirmation = (
        top_candidate is None or top_candidate.confidence < IDENTIFICATION_THRESHOLD
    )

    accepted_findings = tuple(
        item
        for item in (*signals.visual_findings, *signals.text_findings)
        if item.confidence >= FINDING_THRESHOLD
    )

    extreme_environment = (
        signals.humidity_pct is not None
        and (signals.humidity_pct < 20 or signals.humidity_pct > 85)
    ) or (
        signals.temperature_c is not None
        and (signals.temperature_c < 10 or signals.temperature_c > 35)
    )

    if not accepted_findings and not extreme_environment:
        risk = RiskLevel.UNDETERMINED
    elif extreme_environment and len(accepted_findings) >= 2:
        risk = RiskLevel.HIGH
    elif extreme_environment or accepted_findings:
        risk = RiskLevel.MODERATE
    else:
        risk = RiskLevel.LOW

    actions = []
    if requires_species_confirmation:
        actions.append("Подтвердить вид растения перед видоспецифичной рекомендацией")
    if signals.photos_comparable is False:
        actions.append("Повторить фотографию при сопоставимом ракурсе и освещении")
    if signals.humidity_pct is not None and signals.humidity_pct > 85:
        actions.append("Проверить влажность субстрата и состояние дренажа")
    if signals.humidity_pct is not None and signals.humidity_pct < 20:
        actions.append("Проверить, требуется ли растению полив")
    if not actions and risk is RiskLevel.UNDETERMINED:
        actions.append("Добавить описание симптомов или дополнительную фотографию")

    return Assessment(
        risk=risk,
        requires_species_confirmation=requires_species_confirmation,
        requires_more_data=risk is RiskLevel.UNDETERMINED or signals.photos_comparable is False,
        evidence=accepted_findings,
        recommended_actions=tuple(actions),
    )
