"""Decision-support primitives used by PlantGuard services."""

from .comparison import PhotoComparatorBaseline, PhotoComparisonOutcome
from .identification import (
    SPECIES_CATALOG,
    IdentificationOutcome,
    KnnPlantIdentifier,
    extract_features,
    fit_artifact,
)
from .policy import (
    Assessment,
    AssessmentSignals,
    Evidence,
    IdentificationCandidate,
    RiskLevel,
    evaluate,
)
from .text import RussianSymptomExtractor, TextAnalysisOutcome
from .visual import VisualAnalysisOutcome, VisualConditionBaseline

__all__ = [
    "Assessment",
    "AssessmentSignals",
    "Evidence",
    "IdentificationOutcome",
    "IdentificationCandidate",
    "KnnPlantIdentifier",
    "PhotoComparatorBaseline",
    "PhotoComparisonOutcome",
    "RiskLevel",
    "RussianSymptomExtractor",
    "SPECIES_CATALOG",
    "TextAnalysisOutcome",
    "VisualAnalysisOutcome",
    "VisualConditionBaseline",
    "evaluate",
    "extract_features",
    "fit_artifact",
]
