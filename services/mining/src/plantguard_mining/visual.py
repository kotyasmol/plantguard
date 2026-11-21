"""Deterministic visual-condition baseline for observable leaf findings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter

from .policy import Evidence

MODEL_VERSION = "visual-rules-1.0"


@dataclass(frozen=True)
class VisualAnalysisOutcome:
    findings: tuple[Evidence, ...]
    analyzable: bool
    model_version: str = MODEL_VERSION


def _internal_gap_ratio(mask: list[bool], width: int, height: int) -> float:
    visited: set[int] = set()
    internal_gap_pixels = 0
    for start, is_plant in enumerate(mask):
        if is_plant or start in visited:
            continue
        stack = [start]
        visited.add(start)
        component_size = 0
        touches_border = False
        while stack:
            index = stack.pop()
            component_size += 1
            x = index % width
            y = index // width
            touches_border = touches_border or x in {0, width - 1} or y in {0, height - 1}
            for neighbor in (index - 1, index + 1, index - width, index + width):
                if neighbor < 0 or neighbor >= len(mask) or neighbor in visited:
                    continue
                neighbor_x = neighbor % width
                if abs(neighbor_x - x) > 1 or mask[neighbor]:
                    continue
                visited.add(neighbor)
                stack.append(neighbor)
        if not touches_border and component_size >= 9:
            internal_gap_pixels += component_size
    return internal_gap_pixels / max(1, sum(mask) + internal_gap_pixels)


class VisualConditionBaseline:
    """Estimate visible surface changes without inferring their cause."""

    def analyze_path(self, path: Path) -> VisualAnalysisOutcome:
        with Image.open(path) as source:
            image = source.convert("RGB")
        image.thumbnail((512, 512))
        hsv = image.convert("HSV")
        hsv_pixels = list(hsv.getdata())
        plant_mask = [
            18 <= hue <= 125 and saturation >= 35 and value >= 25
            for hue, saturation, value in hsv_pixels
        ]
        plant_pixels = sum(plant_mask)
        coverage = plant_pixels / max(1, len(plant_mask))
        if coverage < 0.08 or min(image.size) < 64:
            return VisualAnalysisOutcome(findings=(), analyzable=False)

        yellow_pixels = sum(
            is_plant and 24 <= hue <= 55 and saturation >= 55 and value >= 65
            for is_plant, (hue, saturation, value) in zip(plant_mask, hsv_pixels)
        )
        dark_pixels = sum(
            is_plant and value < 72
            for is_plant, (_, _, value) in zip(plant_mask, hsv_pixels)
        )
        yellow_ratio = yellow_pixels / plant_pixels
        dark_ratio = dark_pixels / plant_pixels

        edges = image.convert("L").filter(ImageFilter.FIND_EDGES)
        edge_values = list(edges.getdata())
        width, height = image.size
        internal_edges = 0
        internal_plant = 0
        for index, (edge, is_plant) in enumerate(zip(edge_values, plant_mask)):
            x = index % width
            y = index // width
            if 3 <= x < width - 3 and 3 <= y < height - 3 and is_plant:
                internal_plant += 1
                internal_edges += edge >= 75
        edge_ratio = internal_edges / max(1, internal_plant)
        gap_ratio = _internal_gap_ratio(plant_mask, width, height)

        findings = []
        if yellow_ratio >= 0.12:
            findings.append(
                Evidence(
                    code="leaf-yellowing",
                    confidence=min(0.99, 0.55 + yellow_ratio),
                    source="image:visual-rules-1.0",
                )
            )
        if dark_ratio >= 0.05:
            findings.append(
                Evidence(
                    code="leaf-dark-spots",
                    confidence=min(0.99, 0.55 + dark_ratio * 2),
                    source="image:visual-rules-1.0",
                )
            )
        if edge_ratio >= 0.08 or gap_ratio >= 0.005:
            findings.append(
                Evidence(
                    code="leaf-tissue-damage",
                    confidence=min(0.95, 0.55 + max(edge_ratio * 4, gap_ratio * 6)),
                    source="image:visual-rules-1.0",
                )
            )
        return VisualAnalysisOutcome(
            findings=tuple(sorted(findings, key=lambda item: item.confidence, reverse=True)),
            analyzable=True,
        )

    def analyze(self, image: Any) -> VisualAnalysisOutcome:
        return self.analyze_path(Path(image.uri))
