"""Decision-support primitives used by PlantGuard services."""

from .comparison import PhotoComparatorBaseline, PhotoComparisonOutcome
from .dynamics import (
    ChangeDirection,
    DynamicsResult,
    FindingChange,
    OverallTrend,
    calculate_dynamics,
)
from .explanations import (
    ExplanationContext,
    ExplanationPlan,
    GroundedExplanation,
    GroundedExplanationGenerator,
)
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
    "ChangeDirection",
    "DynamicsResult",
    "Evidence",
    "ExplanationContext",
    "ExplanationPlan",
    "FindingChange",
    "GroundedExplanation",
    "GroundedExplanationGenerator",
    "IdentificationOutcome",
    "IdentificationCandidate",
    "KnnPlantIdentifier",
    "PhotoComparatorBaseline",
    "PhotoComparisonOutcome",
    "RiskLevel",
    "RussianSymptomExtractor",
    "SPECIES_CATALOG",
    "TextAnalysisOutcome",
    "OverallTrend",
    "VisualAnalysisOutcome",
    "VisualConditionBaseline",
    "evaluate",
    "calculate_dynamics",
    "extract_features",
    "fit_artifact",
]
