"""Photo comparability checks used before estimating change over time."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter, ImageStat

MODEL_VERSION = "photo-comparability-1.0"


@dataclass(frozen=True)
class PhotoComparisonOutcome:
    comparable: bool
    reasons: tuple[str, ...]
    metrics: dict[str, float]
    model_version: str = MODEL_VERSION


def _difference_hash(image: Image.Image) -> tuple[bool, ...]:
    grayscale = image.convert("L").resize((9, 8))
    pixels = list(grayscale.getdata())
    return tuple(
        pixels[row * 9 + column] > pixels[row * 9 + column + 1]
        for row in range(8)
        for column in range(8)
    )


def _hash_similarity(first: Image.Image, second: Image.Image) -> float:
    first_hash = _difference_hash(first)
    second_hash = _difference_hash(second)
    distance = sum(left != right for left, right in zip(first_hash, second_hash))
    return 1.0 - distance / len(first_hash)


def _color_histogram(image: Image.Image) -> list[float]:
    hsv = image.convert("HSV").resize((128, 128))
    pixels = list(hsv.getdata())
    hue = [0.0] * 16
    saturation = [0.0] * 4
    for hue_value, saturation_value, _ in pixels:
        hue[min(15, hue_value // 16)] += 1
        saturation[min(3, saturation_value // 64)] += 1
    total = len(pixels)
    return [value / total / 2 for value in (*hue, *saturation)]


def _histogram_similarity(first: Image.Image, second: Image.Image) -> float:
    left = _color_histogram(first)
    right = _color_histogram(second)
    return sum(min(a, b) for a, b in zip(left, right))


def _brightness(image: Image.Image) -> float:
    return float(ImageStat.Stat(image.convert("L")).mean[0])


def _sharpness(image: Image.Image) -> float:
    edges = image.convert("L").filter(ImageFilter.FIND_EDGES)
    return float(ImageStat.Stat(edges).mean[0])


class PhotoComparatorBaseline:
    def compare_paths(self, first_path: Path, second_path: Path) -> PhotoComparisonOutcome:
        with Image.open(first_path) as source:
            first = source.convert("RGB")
        with Image.open(second_path) as source:
            second = source.convert("RGB")

        first_ratio = first.width / first.height
        second_ratio = second.width / second.height
        aspect_difference = abs(first_ratio - second_ratio) / max(first_ratio, second_ratio)
        brightness_difference = abs(_brightness(first) - _brightness(second))
        structure_similarity = _hash_similarity(first, second)
        color_similarity = _histogram_similarity(first, second)
        first_sharpness = _sharpness(first)
        second_sharpness = _sharpness(second)
        sharpness_ratio = min(first_sharpness, second_sharpness) / max(
            first_sharpness, second_sharpness, 1.0
        )

        reasons = []
        if min(first.size) < 64 or min(second.size) < 64:
            reasons.append("image_too_small")
        if aspect_difference > 0.18:
            reasons.append("aspect_ratio_mismatch")
        if brightness_difference > 65:
            reasons.append("lighting_mismatch")
        if structure_similarity < 0.60 or color_similarity < 0.65:
            reasons.append("framing_mismatch")
        if max(first_sharpness, second_sharpness) > 8 and sharpness_ratio < 0.35:
            reasons.append("blur_mismatch")

        metrics = {
            "aspect_difference": round(aspect_difference, 4),
            "brightness_difference": round(brightness_difference, 4),
            "structure_similarity": round(structure_similarity, 4),
            "color_similarity": round(color_similarity, 4),
            "sharpness_ratio": round(sharpness_ratio, 4),
        }
        return PhotoComparisonOutcome(
            comparable=not reasons,
            reasons=tuple(reasons),
            metrics=metrics,
        )

    def compare(self, first: Any, second: Any) -> PhotoComparisonOutcome:
        return self.compare_paths(Path(first.uri), Path(second.uri))
