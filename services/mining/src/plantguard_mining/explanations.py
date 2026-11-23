"""Grounded explanations for decision-support results."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

SUMMARY_BY_RISK = {
    "unknown": "insufficient_data",
    "low": "stable",
    "medium": "attention",
    "high": "urgent_attention",
}

SUMMARY_TEXT = {
    "insufficient_data": "Пока недостаточно данных для уверенной оценки состояния.",
    "stable": "По доступным данным выраженные признаки ухудшения не обнаружены.",
    "attention": "Есть признаки, которым стоит уделить внимание.",
    "urgent_attention": "Обнаружено сочетание признаков, требующее скорой проверки условий.",
}

EVIDENCE_TEXT = {
    "leaf-yellowing": "заметно пожелтение листа",
    "leaf-dark-spots": "заметны тёмные участки или пятна",
    "leaf-tissue-damage": "заметно повреждение ткани листа",
    "leaf-drop": "в описании указано опадение листьев",
    "leaf-wilting": "в описании указано увядание",
}

MISSING_TEXT = {
    "confirmed_species": "вид растения не подтверждён",
    "analyzable_photo": "не хватает подходящей фотографии",
    "symptom_description": "не хватает описания изменений",
}


@dataclass(frozen=True)
class ExplanationContext:
    risk_level: str
    evidence_codes: tuple[str, ...]
    recommended_actions: tuple[str, ...]
    missing_inputs: tuple[str, ...] = ()
    conflicting_evidence: bool = False


@dataclass(frozen=True)
class ExplanationPlan:
    summary_code: str
    evidence_codes: tuple[str, ...]
    recommended_actions: tuple[str, ...]


@dataclass(frozen=True)
class GroundedExplanation:
    text: str
    source: str


class ExplanationPlanner(Protocol):
    def plan(self, context: ExplanationContext) -> ExplanationPlan: ...


def _unique_known(items: Sequence[str], catalog: dict[str, str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item for item in items if item in catalog))


def default_plan(context: ExplanationContext) -> ExplanationPlan:
    return ExplanationPlan(
        summary_code=SUMMARY_BY_RISK.get(context.risk_level, "insufficient_data"),
        evidence_codes=_unique_known(context.evidence_codes, EVIDENCE_TEXT),
        recommended_actions=tuple(dict.fromkeys(context.recommended_actions)),
    )


def render_explanation(context: ExplanationContext, plan: ExplanationPlan) -> str:
    sentences = [SUMMARY_TEXT[plan.summary_code]]
    facts = [EVIDENCE_TEXT[code] for code in plan.evidence_codes]
    if facts:
        sentences.append("Основание: " + "; ".join(facts) + ".")
    missing = [MISSING_TEXT[code] for code in context.missing_inputs if code in MISSING_TEXT]
    if context.conflicting_evidence:
        missing.append("фото и описание дают разные сигналы")
    if missing:
        sentences.append("Ограничения: " + "; ".join(dict.fromkeys(missing)) + ".")
    if plan.recommended_actions:
        sentences.append("Следующий шаг: " + plan.recommended_actions[0].rstrip(".") + ".")
    sentences.append(
        "Это предварительная оценка по наблюдаемым признакам, а не диагноз специалиста."
    )
    return " ".join(sentences)


class GroundedExplanationGenerator:
    """Validate a model-produced plan and fall back to a safe local plan."""

    def __init__(self, planner: ExplanationPlanner | None = None) -> None:
        self._planner = planner

    def explain(self, context: ExplanationContext) -> GroundedExplanation:
        fallback = default_plan(context)
        if self._planner is None:
            return GroundedExplanation(
                text=render_explanation(context, fallback),
                source="deterministic",
            )
        try:
            plan = self._planner.plan(context)
            self._validate(context, plan)
        except (OSError, TimeoutError, ValueError, TypeError, KeyError):
            return GroundedExplanation(
                text=render_explanation(context, fallback),
                source="deterministic-fallback",
            )
        return GroundedExplanation(
            text=render_explanation(context, plan),
            source="llm-structured",
        )

    @staticmethod
    def _validate(context: ExplanationContext, plan: ExplanationPlan) -> None:
        expected_summary = SUMMARY_BY_RISK.get(context.risk_level, "insufficient_data")
        if plan.summary_code != expected_summary:
            raise ValueError("summary code contradicts the calculated risk")
        if not set(plan.evidence_codes).issubset(context.evidence_codes):
            raise ValueError("explanation contains unsupported evidence")
        if not set(plan.recommended_actions).issubset(context.recommended_actions):
            raise ValueError("explanation contains an unsupported action")
        if len(plan.evidence_codes) != len(set(plan.evidence_codes)):
            raise ValueError("explanation contains duplicate evidence")
        if len(plan.recommended_actions) != len(set(plan.recommended_actions)):
            raise ValueError("explanation contains duplicate actions")
