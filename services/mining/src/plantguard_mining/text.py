"""Russian symptom extraction with explicit regular expressions and negation handling."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .policy import Evidence

MODEL_VERSION = "ru-symptom-regex-1.0"
NEGATION = re.compile(r"(?:\bне\b|\bнет\b|\bбез\b|\bникак(?:их|ого|ой)?\b)", re.IGNORECASE)
POST_NEGATION = re.compile(
    r"(?:\bнет\b|\bне\s+(?:видн\w*|обнаруж\w*|наблюда\w*))", re.IGNORECASE
)
PATTERNS = {
    "leaf-yellowing": re.compile(
        r"\b(?:желт\w*|пожелт\w*|желте\w*|обесцвеч\w*)\b", re.IGNORECASE
    ),
    "leaf-dark-spots": re.compile(
        r"\b(?:пятн\w*|крапин\w*|точк\w*|почерн\w*|черне\w*|темне\w*)\b",
        re.IGNORECASE,
    ),
    "leaf-tissue-damage": re.compile(
        r"\b(?:дыр\w*|отверсти\w*|разрыв\w*|порван\w*|надорван\w*|"
        r"сух\w*\s+кра\w*|кра\w*\s+сух\w*|объеден\w*)\b",
        re.IGNORECASE,
    ),
    "leaf-drop": re.compile(
        r"\b(?:опада\w*|осыпа\w*|сбрасыва\w*\s+листь\w*)\b", re.IGNORECASE
    ),
    "leaf-wilting": re.compile(
        r"\b(?:вял\w*|поник\w*|увяда\w*|сморщ\w*)\b", re.IGNORECASE
    ),
}


@dataclass(frozen=True)
class TextAnalysisOutcome:
    findings: tuple[Evidence, ...]
    analyzable: bool
    model_version: str = MODEL_VERSION


def _negated(text: str, start: int, end: int) -> bool:
    prefix = text[max(0, start - 32) : start]
    boundary = max(prefix.rfind("."), prefix.rfind("!"), prefix.rfind("?"))
    suffix = text[end : end + 24]
    boundary_positions = (
        suffix.find("."),
        suffix.find("!"),
        suffix.find("?"),
        suffix.find(","),
    )
    suffix_boundary = min(
        (position for position in boundary_positions if position >= 0),
        default=len(suffix),
    )
    return (
        NEGATION.search(prefix[boundary + 1 :]) is not None
        or POST_NEGATION.search(suffix[:suffix_boundary]) is not None
    )


class RussianSymptomExtractor:
    def extract(self, description: str) -> TextAnalysisOutcome:
        text = " ".join(description.strip().split())
        if not text:
            return TextAnalysisOutcome(findings=(), analyzable=False)
        findings = []
        for code, pattern in PATTERNS.items():
            matches = list(pattern.finditer(text))
            if any(not _negated(text, match.start(), match.end()) for match in matches):
                findings.append(
                    Evidence(
                        code=code,
                        confidence=0.92,
                        source="text:ru-symptom-regex-1.0",
                    )
                )
        return TextAnalysisOutcome(
            findings=tuple(findings),
            analyzable=True,
        )
