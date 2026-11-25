import json

import pytest
from plantguard_api.llm import CompatibleExplanationPlanner
from plantguard_mining.explanations import ExplanationContext


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def context() -> ExplanationContext:
    return ExplanationContext(
        risk_level="medium",
        evidence_codes=("leaf-yellowing",),
        recommended_actions=("Проверить влажность грунта",),
    )


def test_compatible_planner_sends_grounded_context_and_parses_plan(monkeypatch):
    captured: dict[str, object] = {}
    content = json.dumps({
        "summary_code": "attention",
        "evidence_codes": ["leaf-yellowing"],
        "recommended_actions": ["Проверить влажность грунта"],
    })

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        return FakeResponse({"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr("plantguard_api.llm.urlopen", fake_urlopen)
    planner = CompatibleExplanationPlanner(
        base_url="https://llm.example/v1/",
        api_key="secret",
        model="test-model",
        timeout=3.5,
    )

    plan = planner.plan(context())

    assert captured["url"] == "https://llm.example/v1/chat/completions"
    assert captured["authorization"] == "Bearer secret"
    assert captured["timeout"] == 3.5
    assert captured["body"]["model"] == "test-model"
    assert plan.evidence_codes == ("leaf-yellowing",)
    assert plan.recommended_actions == ("Проверить влажность грунта",)


def test_compatible_planner_rejects_unexpected_fields(monkeypatch):
    content = json.dumps({
        "summary_code": "attention",
        "evidence_codes": [],
        "recommended_actions": [],
        "diagnosis": "invented",
    })
    monkeypatch.setattr(
        "plantguard_api.llm.urlopen",
        lambda *_args, **_kwargs: FakeResponse(
            {"choices": [{"message": {"content": content}}]}
        ),
    )
    planner = CompatibleExplanationPlanner(
        base_url="https://llm.example/v1",
        api_key="secret",
        model="test-model",
        timeout=3,
    )

    with pytest.raises(ValueError, match="unexpected explanation plan fields"):
        planner.plan(context())
