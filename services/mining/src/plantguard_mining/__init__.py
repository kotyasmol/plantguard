"""Decision-support primitives used by PlantGuard services."""

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
from .visual import VisualAnalysisOutcome, VisualConditionBaseline

__all__ = [
    "Assessment",
    "AssessmentSignals",
    "Evidence",
    "IdentificationOutcome",
    "IdentificationCandidate",
    "KnnPlantIdentifier",
    "RiskLevel",
    "SPECIES_CATALOG",
    "VisualAnalysisOutcome",
    "VisualConditionBaseline",
    "evaluate",
    "extract_features",
    "fit_artifact",
]
