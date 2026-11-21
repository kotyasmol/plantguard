"""Interfaces implemented by concrete image and text model adapters."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from .identification import IdentificationOutcome
from .policy import Evidence
from .visual import VisualAnalysisOutcome


@dataclass(frozen=True)
class ImageReference:
    uri: str
    media_type: str


class PlantIdentifier(Protocol):
    def identify(self, image: ImageReference) -> IdentificationOutcome:
        """Return ordered candidates and an explicit recognition decision."""


class VisualConditionAnalyzer(Protocol):
    def analyze(self, image: ImageReference) -> VisualAnalysisOutcome:
        """Return visible findings without producing a final diagnosis."""


class SymptomExtractor(Protocol):
    def extract(self, description: str) -> Sequence[Evidence]:
        """Convert free-form text into structured findings."""


class ExplanationGenerator(Protocol):
    def explain(self, facts: Sequence[Evidence], actions: Sequence[str]) -> str:
        """Explain only the supplied facts and selected actions."""
