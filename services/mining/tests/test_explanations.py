from plantguard_mining.explanations import (
    ExplanationContext,
    ExplanationPlan,
    GroundedExplanationGenerator,
)


def context() -> ExplanationContext:
    return ExplanationContext(
        risk_level="medium",
        evidence_codes=("leaf-yellowing",),
        recommended_actions=("Проверить влажность субстрата",),
    )


def test_deterministic_explanation_only_uses_grounded_facts():
    result = GroundedExplanationGenerator().explain(context())

    assert result.source == "deterministic"
    assert "пожелтение" in result.text
    assert "не диагноз" in result.text


def test_valid_structured_plan_is_rendered_without_free_model_text():
    class Planner:
        def plan(self, _context):
            return ExplanationPlan(
                summary_code="attention",
                evidence_codes=("leaf-yellowing",),
                recommended_actions=("Проверить влажность субстрата",),
            )

    result = GroundedExplanationGenerator(Planner()).explain(context())

    assert result.source == "llm-structured"
    assert "пожелтение" in result.text


def test_unsupported_model_claim_uses_deterministic_fallback():
    class Planner:
        def plan(self, _context):
            return ExplanationPlan(
                summary_code="attention",
                evidence_codes=("fungal-disease",),
                recommended_actions=("Применить фунгицид",),
            )

    result = GroundedExplanationGenerator(Planner()).explain(context())

    assert result.source == "deterministic-fallback"
    assert "фунгицид" not in result.text


def test_unavailable_model_uses_deterministic_fallback():
    class Planner:
        def plan(self, _context):
            raise TimeoutError

    result = GroundedExplanationGenerator(Planner()).explain(context())

    assert result.source == "deterministic-fallback"
    assert "Проверить влажность субстрата" in result.text
