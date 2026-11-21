"""Interfaces implemented by concrete image and text model adapters."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from .comparison import PhotoComparisonOutcome
from .identification import IdentificationOutcome
from .policy import Evidence
from .text import TextAnalysisOutcome
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
    def extract(self, description: str) -> TextAnalysisOutcome:
        """Convert free-form text into structured findings."""


class PhotoComparator(Protocol):
    def compare(
        self, first: ImageReference, second: ImageReference
    ) -> PhotoComparisonOutcome:
        """Reject pairs that cannot support a change estimate."""


class ExplanationGenerator(Protocol):
    def explain(self, facts: Sequence[Evidence], actions: Sequence[str]) -> str:
        """Explain only the supplied facts and selected actions."""
