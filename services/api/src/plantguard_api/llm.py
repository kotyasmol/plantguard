"""Optional compatible adapter for structured explanation planning."""

from __future__ import annotations

import json
from dataclasses import asdict
from urllib.request import Request, urlopen

from plantguard_mining.explanations import ExplanationContext, ExplanationPlan

SYSTEM_PROMPT = """You order already verified facts for a plant-care explanation.
Return JSON only with keys summary_code, evidence_codes, recommended_actions.
Copy values exclusively from the supplied allowed values. Never diagnose a disease,
invent a cause, add treatment, or change the calculated risk."""


class CompatibleExplanationPlanner:
    def __init__(self, *, base_url: str, api_key: str, model: str, timeout: float) -> None:
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def plan(self, context: ExplanationContext) -> ExplanationPlan:
        body = json.dumps(
            {
                "model": self._model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(asdict(context), ensure_ascii=False),
                    },
                ],
            }
        ).encode()
        request = Request(
            self._url,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=self._timeout) as response:  # noqa: S310
            payload = json.loads(response.read())
        content = payload["choices"][0]["message"]["content"]
        plan = json.loads(content)
        if set(plan) != {"summary_code", "evidence_codes", "recommended_actions"}:
            raise ValueError("unexpected explanation plan fields")
        return ExplanationPlan(
            summary_code=str(plan["summary_code"]),
            evidence_codes=tuple(str(item) for item in plan["evidence_codes"]),
            recommended_actions=tuple(str(item) for item in plan["recommended_actions"]),
        )
