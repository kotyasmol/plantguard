"""Deterministic change calculation for two comparable observations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .policy import Evidence

FINDING_THRESHOLD = 0.65
CHANGE_THRESHOLD = 0.15


class ChangeDirection(str, Enum):
    APPEARED = "appeared"
    RESOLVED = "resolved"
    INCREASED = "increased"
    DECREASED = "decreased"
    STABLE = "stable"


class OverallTrend(str, Enum):
    IMPROVING = "improving"
    STABLE = "stable"
    WORSENING = "worsening"
    MIXED = "mixed"
    UNDETERMINED = "undetermined"


@dataclass(frozen=True)
class FindingChange:
    code: str
    previous_confidence: float
    current_confidence: float
    direction: ChangeDirection


@dataclass(frozen=True)
class DynamicsResult:
    trend: OverallTrend
    changes: tuple[FindingChange, ...]


def _strongest(findings: tuple[Evidence, ...]) -> dict[str, float]:
    result: dict[str, float] = {}
    for finding in findings:
        result[finding.code] = max(result.get(finding.code, 0.0), finding.confidence)
    return result


def calculate_dynamics(
    previous: tuple[Evidence, ...], current: tuple[Evidence, ...]
) -> DynamicsResult:
    previous_map = _strongest(previous)
    current_map = _strongest(current)
    changes = []
    for code in sorted(previous_map.keys() | current_map.keys()):
        before = previous_map.get(code, 0.0)
        after = current_map.get(code, 0.0)
        if max(before, after) < FINDING_THRESHOLD:
            continue
        if before < FINDING_THRESHOLD <= after:
            direction = ChangeDirection.APPEARED
        elif after < FINDING_THRESHOLD <= before:
            direction = ChangeDirection.RESOLVED
        elif after - before >= CHANGE_THRESHOLD:
            direction = ChangeDirection.INCREASED
        elif before - after >= CHANGE_THRESHOLD:
            direction = ChangeDirection.DECREASED
        else:
            direction = ChangeDirection.STABLE
        changes.append(
            FindingChange(
                code=code,
                previous_confidence=before,
                current_confidence=after,
                direction=direction,
            )
        )

    improving = any(
        change.direction in {ChangeDirection.RESOLVED, ChangeDirection.DECREASED}
        for change in changes
    )
    worsening = any(
        change.direction in {ChangeDirection.APPEARED, ChangeDirection.INCREASED}
        for change in changes
    )
    if improving and worsening:
        trend = OverallTrend.MIXED
    elif worsening:
        trend = OverallTrend.WORSENING
    elif improving:
        trend = OverallTrend.IMPROVING
    elif changes:
        trend = OverallTrend.STABLE
    else:
        trend = OverallTrend.UNDETERMINED
    return DynamicsResult(trend=trend, changes=tuple(changes))
