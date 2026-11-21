#!/usr/bin/env python3
"""Train and evaluate the lightweight species baseline on the locked registry."""

from __future__ import annotations

import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from dataset_registry import ALL_LABELS, load_manifest
from plantguard_mining.identification import KnnPlantIdentifier, fit_artifact, image_features

MANIFEST_PATH = Path("datasets/plantguard-v1/manifest.jsonl")
CACHE_PATH = Path(".data/dataset-images")
MODEL_PATH = Path("services/mining/src/plantguard_mining/models/species-knn-v1.json")
REPORT_PATH = Path("datasets/plantguard-v1/identification-report.json")
MODEL_VERSION = "species-knn-1.0"
USER_AGENT = "PlantGuard species baseline/1.0"


def download(record: dict[str, Any]) -> Path:
    destination = CACHE_PATH / f"{record['sample_id']}.image"
    if destination.is_file() and destination.stat().st_size > 0:
        return destination
    request = Request(str(record["image_url"]), headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        content = response.read(5 * 1024 * 1024)
    if not content:
        raise RuntimeError(f"empty image: {record['sample_id']}")
    destination.write_bytes(content)
    return destination


def prepare_images(records: list[dict[str, Any]]) -> dict[str, Path]:
    CACHE_PATH.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(download, record): record for record in records}
        for future in as_completed(futures):
            record = futures[future]
            paths[str(record["sample_id"])] = future.result()
    return paths


def macro_metrics(expected: list[str], predicted: list[str]) -> dict[str, Any]:
    per_class: dict[str, dict[str, float | int]] = {}
    f1_values = []
    for label in sorted(ALL_LABELS):
        true_positive = sum(e == label and p == label for e, p in zip(expected, predicted))
        false_positive = sum(e != label and p == label for e, p in zip(expected, predicted))
        false_negative = sum(e == label and p != label for e, p in zip(expected, predicted))
        support = sum(e == label for e in expected)
        precision = true_positive / max(1, true_positive + false_positive)
        recall = true_positive / max(1, true_positive + false_negative)
        f1 = 2 * precision * recall / max(1e-12, precision + recall)
        f1_values.append(f1)
        per_class[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support,
        }
    accuracy = sum(e == p for e, p in zip(expected, predicted)) / max(1, len(expected))
    return {
        "accuracy": round(accuracy, 4),
        "macro_f1": round(sum(f1_values) / len(f1_values), 4),
        "per_class": per_class,
    }


def predict(identifier: KnnPlantIdentifier, features: list[float], threshold: float) -> str:
    scores = identifier.scores_for_features(features)
    label, confidence = max(scores.items(), key=lambda item: item[1], default=("unknown", 0.0))
    if label == "unknown" or confidence < threshold:
        return "unknown"
    return label


def choose_threshold(
    identifier: KnnPlantIdentifier,
    validation: list[tuple[str, list[float]]],
) -> tuple[float, dict[str, Any]]:
    best_threshold = 0.0
    best_metrics: dict[str, Any] = {}
    for step in range(20, 81):
        threshold = step / 100
        expected = [label for label, _ in validation]
        predicted = [predict(identifier, vector, threshold) for _, vector in validation]
        metrics = macro_metrics(expected, predicted)
        if not best_metrics or metrics["macro_f1"] > best_metrics["macro_f1"]:
            best_threshold = threshold
            best_metrics = metrics
    return best_threshold, best_metrics


def calibration_error(
    identifier: KnnPlantIdentifier,
    samples: list[tuple[str, list[float]]],
) -> float:
    bins: list[list[tuple[float, bool]]] = [[] for _ in range(10)]
    for expected, vector in samples:
        scores = identifier.scores_for_features(vector)
        label, confidence = max(scores.items(), key=lambda item: item[1])
        bins[min(9, math.floor(confidence * 10))].append((confidence, label == expected))
    total = max(1, len(samples))
    error = 0.0
    for items in bins:
        if not items:
            continue
        mean_confidence = sum(item[0] for item in items) / len(items)
        accuracy = sum(item[1] for item in items) / len(items)
        error += len(items) / total * abs(mean_confidence - accuracy)
    return round(error, 4)


def main() -> None:
    records = load_manifest(MANIFEST_PATH)
    paths = prepare_images(records)
    featured = [
        (record, image_features(paths[str(record["sample_id"])])) for record in records
    ]
    training = [
        (str(record["label"]), vector)
        for record, vector in featured
        if record["split"] == "train"
    ]
    validation = [
        (str(record["label"]), vector)
        for record, vector in featured
        if record["split"] == "validation"
    ]
    test = [
        (str(record["label"]), vector)
        for record, vector in featured
        if record["split"] == "test"
    ]

    provisional = fit_artifact(
        training,
        model_version=MODEL_VERSION,
        recognition_threshold=0.0,
    )
    identifier = KnnPlantIdentifier(provisional)
    threshold, validation_metrics = choose_threshold(identifier, validation)
    artifact = fit_artifact(
        training,
        model_version=MODEL_VERSION,
        recognition_threshold=threshold,
    )
    identifier = KnnPlantIdentifier(artifact)
    expected = [label for label, _ in test]
    predicted = [predict(identifier, vector, threshold) for _, vector in test]
    test_metrics = macro_metrics(expected, predicted)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_PATH.write_text(
        json.dumps(artifact, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    report = {
        "schema_version": 1,
        "model_version": MODEL_VERSION,
        "algorithm": "standardized visual descriptors with distance-weighted k-NN",
        "neighbors": artifact["neighbors"],
        "recognition_threshold": threshold,
        "training_samples": len(training),
        "validation_samples": len(validation),
        "test_samples": len(test),
        "validation": validation_metrics,
        "test": test_metrics,
        "test_ece": calibration_error(identifier, test),
        "release_targets_met": {
            "macro_f1_at_least_0_85": test_metrics["macro_f1"] >= 0.85,
            "unknown_recall_at_least_0_90": (
                test_metrics["per_class"]["unknown"]["recall"] >= 0.90
            ),
        },
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"[ok] {MODEL_VERSION}: test macro-F1={test_metrics['macro_f1']}, "
        f"unknown recall={test_metrics['per_class']['unknown']['recall']}"
    )


if __name__ == "__main__":
    main()
