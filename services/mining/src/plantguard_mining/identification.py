"""Small local k-NN baseline for the three supported plant species."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter

from .policy import IdentificationCandidate


@dataclass(frozen=True)
class SpeciesDefinition:
    code: str
    scientific_name: str
    common_name: str


SPECIES_CATALOG = {
    "monstera_deliciosa": SpeciesDefinition(
        "monstera_deliciosa", "Monstera deliciosa", "Монстера деликатесная"
    ),
    "epipremnum_aureum": SpeciesDefinition(
        "epipremnum_aureum", "Epipremnum aureum", "Эпипремнум золотистый"
    ),
    "ficus_elastica": SpeciesDefinition(
        "ficus_elastica", "Ficus elastica", "Фикус каучуконосный"
    ),
}


@dataclass(frozen=True)
class IdentificationOutcome:
    candidates: tuple[IdentificationCandidate, ...]
    recognized: bool
    model_version: str


def _histogram(values: list[int], bins: int) -> list[float]:
    counts = [0] * bins
    for value in values:
        counts[min(bins - 1, value * bins // 256)] += 1
    total = max(1, len(values))
    return [count / total for count in counts]


def extract_features(image: Image.Image) -> list[float]:
    rgb = image.convert("RGB")
    rgb.thumbnail((96, 96))
    canvas = Image.new("RGB", (96, 96), (127, 127, 127))
    offset = ((96 - rgb.width) // 2, (96 - rgb.height) // 2)
    canvas.paste(rgb, offset)

    pixels = list(canvas.getdata())
    channels = [[pixel[channel] for pixel in pixels] for channel in range(3)]
    hsv_pixels = list(canvas.convert("HSV").getdata())
    hue = [pixel[0] for pixel in hsv_pixels]
    saturation = [pixel[1] for pixel in hsv_pixels]
    value = [pixel[2] for pixel in hsv_pixels]
    edges = list(canvas.convert("L").filter(ImageFilter.FIND_EDGES).getdata())

    features = []
    for channel in channels:
        features.extend(_histogram(channel, 8))
    features.extend(_histogram(hue, 12))
    features.extend(_histogram(saturation, 4))
    features.extend(_histogram(value, 4))
    features.extend(_histogram(edges, 8))

    for y in range(0, 96, 24):
        for x in range(0, 96, 24):
            block = [
                canvas.getpixel((column, row))
                for row in range(y, y + 24)
                for column in range(x, x + 24)
            ]
            excess_green = sum(
                max(0, 2 * green - red - blue) / 510 for red, green, blue in block
            ) / len(block)
            features.append(excess_green)
    return features


def image_features(path: Path) -> list[float]:
    with Image.open(path) as image:
        return extract_features(image)


def fit_artifact(
    samples: list[tuple[str, list[float]]],
    *,
    model_version: str,
    recognition_threshold: float,
    neighbors: int = 7,
) -> dict[str, Any]:
    if not samples:
        raise ValueError("at least one training sample is required")
    width = len(samples[0][1])
    if any(len(vector) != width for _, vector in samples):
        raise ValueError("feature vectors have inconsistent lengths")

    means = [sum(vector[index] for _, vector in samples) / len(samples) for index in range(width)]
    scales = []
    for index, mean in enumerate(means):
        variance = sum((vector[index] - mean) ** 2 for _, vector in samples) / len(samples)
        scales.append(max(math.sqrt(variance), 1e-6))

    normalized = [
        {
            "label": label,
            "vector": [round((value - means[i]) / scales[i], 6) for i, value in enumerate(vector)],
        }
        for label, vector in samples
    ]
    return {
        "schema_version": 1,
        "model_version": model_version,
        "neighbors": neighbors,
        "recognition_threshold": recognition_threshold,
        "feature_mean": [round(value, 8) for value in means],
        "feature_scale": [round(value, 8) for value in scales],
        "samples": normalized,
    }


class KnnPlantIdentifier:
    def __init__(self, artifact: dict[str, Any]) -> None:
        if artifact.get("schema_version") != 1:
            raise ValueError("unsupported identification model schema")
        self.model_version = str(artifact["model_version"])
        self.neighbors = int(artifact["neighbors"])
        self.recognition_threshold = float(artifact["recognition_threshold"])
        self.means = [float(value) for value in artifact["feature_mean"]]
        self.scales = [float(value) for value in artifact["feature_scale"]]
        self.samples = [
            (str(item["label"]), [float(value) for value in item["vector"]])
            for item in artifact["samples"]
        ]

    @classmethod
    def from_path(cls, path: Path) -> KnnPlantIdentifier:
        return cls(json.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def load_default(cls) -> KnnPlantIdentifier:
        resource = files("plantguard_mining").joinpath("models/species-knn-v1.json")
        return cls(json.loads(resource.read_text(encoding="utf-8")))

    def scores_for_features(self, features: list[float]) -> dict[str, float]:
        if len(features) != len(self.means):
            raise ValueError("feature vector does not match model")
        normalized = [
            (value - self.means[index]) / self.scales[index]
            for index, value in enumerate(features)
        ]
        distances = []
        for label, reference in self.samples:
            distance = math.sqrt(
                sum((value - reference[index]) ** 2 for index, value in enumerate(normalized))
                / len(normalized)
            )
            distances.append((distance, label))
        votes: dict[str, float] = {}
        for distance, label in sorted(distances)[: self.neighbors]:
            votes[label] = votes.get(label, 0.0) + 1.0 / (distance + 0.05)
        total = sum(votes.values()) or 1.0
        return {label: score / total for label, score in votes.items()}

    def identify_path(self, path: Path) -> IdentificationOutcome:
        scores = self.scores_for_features(image_features(path))
        supported = sorted(
            (
                IdentificationCandidate(
                    code,
                    SPECIES_CATALOG[code].common_name,
                    scores.get(code, 0.0),
                )
                for code in SPECIES_CATALOG
            ),
            key=lambda candidate: candidate.confidence,
            reverse=True,
        )
        top_label, top_score = max(
            scores.items(), key=lambda item: item[1], default=("unknown", 0.0)
        )
        recognized = top_label in SPECIES_CATALOG and top_score >= self.recognition_threshold
        return IdentificationOutcome(
            candidates=tuple(supported[:3]),
            recognized=recognized,
            model_version=self.model_version,
        )

    def identify(self, image: Any) -> IdentificationOutcome:
        return self.identify_path(Path(image.uri))
