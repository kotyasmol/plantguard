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
    species_confirmed: bool = False
    image_analyzable: bool = False
    text_analyzable: bool = False
    humidity_pct: float | None = None
    temperature_c: float | None = None
    photos_comparable: bool | None = None
    dynamics_trend: str | None = None
    environment_alerts: Sequence[str] = ()


@dataclass(frozen=True)
class Assessment:
    risk: RiskLevel
    requires_species_confirmation: bool
    requires_more_data: bool
    evidence: tuple[Evidence, ...]
    recommended_actions: tuple[str, ...]
    conflicting_evidence: bool = False
    missing_inputs: tuple[str, ...] = ()
    policy_version: str = "2.0"


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
    requires_species_confirmation = not signals.species_confirmed and (
        top_candidate is None or top_candidate.confidence < IDENTIFICATION_THRESHOLD
    )

    accepted_findings = tuple(
        item
        for item in (*signals.visual_findings, *signals.text_findings)
        if item.confidence >= FINDING_THRESHOLD
    )

    extreme_environment = bool(signals.environment_alerts) or (
        signals.humidity_pct is not None
        and (signals.humidity_pct < 20 or signals.humidity_pct > 85)
    ) or (
        signals.temperature_c is not None
        and (signals.temperature_c < 10 or signals.temperature_c > 35)
    )

    visual_codes = {
        item.code
        for item in signals.visual_findings
        if item.confidence >= FINDING_THRESHOLD
    }
    text_codes = {
        item.code for item in signals.text_findings if item.confidence >= FINDING_THRESHOLD
    }
    conflicting_evidence = bool(
        signals.image_analyzable
        and signals.text_analyzable
        and visual_codes
        and text_codes
        and visual_codes.isdisjoint(text_codes)
    )
    worsening = signals.dynamics_trend == "worsening"

    if extreme_environment and len(accepted_findings) >= 2:
        risk = RiskLevel.HIGH
    elif worsening and accepted_findings:
        risk = RiskLevel.HIGH if len(accepted_findings) >= 2 else RiskLevel.MODERATE
    elif extreme_environment or accepted_findings:
        risk = RiskLevel.MODERATE
    elif (
        signals.species_confirmed
        and signals.image_analyzable
        and signals.text_analyzable
    ):
        risk = RiskLevel.LOW
    else:
        risk = RiskLevel.UNDETERMINED

    actions = []
    missing_inputs = []
    if requires_species_confirmation:
        actions.append("Подтвердить вид растения перед видоспецифичной рекомендацией")
        missing_inputs.append("confirmed_species")
    if not signals.image_analyzable:
        actions.append("Добавить чёткую фотографию выбранного листа при рассеянном свете")
        missing_inputs.append("analyzable_photo")
    if not signals.text_analyzable:
        actions.append("Описать замеченные изменения своими словами")
        missing_inputs.append("symptom_description")
    if signals.photos_comparable is False:
        actions.append("Повторить фотографию при сопоставимом ракурсе и освещении")
    if signals.humidity_pct is not None and signals.humidity_pct > 85:
        actions.append("Проверить влажность субстрата и состояние дренажа")
    if signals.humidity_pct is not None and signals.humidity_pct < 20:
        actions.append("Проверить, требуется ли растению полив")
    if "leaf-yellowing" in visual_codes | text_codes:
        actions.append("Проверить влажность субстрата, дренаж и нижнюю сторону листа")
    if "leaf-dark-spots" in visual_codes | text_codes:
        actions.append("Осмотреть обе стороны листа и отметить изменение пятен")
    if "leaf-tissue-damage" in visual_codes | text_codes:
        actions.append("Осмотреть повреждённый участок и нижнюю сторону листа")
    if "leaf-drop" in text_codes or "leaf-wilting" in text_codes:
        actions.append("Проверить фактический полив и недавние изменения условий")
    if conflicting_evidence:
        actions.append("Уточнить описание и повторить снимок того же листа")
    if not actions and risk is RiskLevel.UNDETERMINED:
        actions.append("Добавить описание симптомов или дополнительную фотографию")
    if not actions and risk is RiskLevel.LOW:
        actions.append("Продолжить наблюдение и повторить снимок при изменениях")

    unique_actions = tuple(dict.fromkeys(actions))

    return Assessment(
        risk=risk,
        requires_species_confirmation=requires_species_confirmation,
        requires_more_data=(
            risk is RiskLevel.UNDETERMINED
            or signals.photos_comparable is False
            or conflicting_evidence
        ),
        evidence=accepted_findings,
        recommended_actions=unique_actions,
        conflicting_evidence=conflicting_evidence,
        missing_inputs=tuple(missing_inputs),
    )
