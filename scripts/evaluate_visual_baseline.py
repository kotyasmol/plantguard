#!/usr/bin/env python3
"""Run a reproducible synthetic regression benchmark for the visual baseline."""

from __future__ import annotations

import json
import tempfile
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw
from plantguard_mining.visual import VisualConditionBaseline

REPORT_PATH = Path("datasets/plantguard-v1/visual-baseline-report.json")
CODES = ("leaf-yellowing", "leaf-dark-spots", "leaf-tissue-damage")


def create_cases(root: Path) -> list[tuple[Path, set[str]]]:
    cases: list[tuple[Path, set[str]]] = []
    for index, color in enumerate(((35, 135, 40), (45, 165, 55), (30, 115, 45))):
        path = root / f"healthy-{index}.png"
        Image.new("RGB", (160, 160), color).save(path)
        cases.append((path, set()))
    for index, color in enumerate(((180, 180, 25), (150, 165, 30), (195, 175, 35))):
        path = root / f"yellow-{index}.png"
        Image.new("RGB", (160, 160), color).save(path)
        cases.append((path, {"leaf-yellowing"}))
    for index in range(3):
        path = root / f"spots-{index}.png"
        image = Image.new("RGB", (160, 160), (35, 145, 45))
        draw = ImageDraw.Draw(image)
        for x, y in ((35, 35), (80, 55), (55, 110), (120, 100)):
            radius = 10 + index
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(8, 45, 8))
        image.save(path)
        cases.append((path, {"leaf-dark-spots"}))
    for index in range(3):
        path = root / f"damage-{index}.png"
        image = Image.new("RGB", (160, 160), (35, 145, 45))
        draw = ImageDraw.Draw(image)
        for x, y in ((40, 40), (75, 70), (115, 100), (55, 125)):
            radius = 8 + index
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="white")
        image.save(path)
        cases.append((path, {"leaf-tissue-damage"}))
    return cases


def main() -> None:
    analyzer = VisualConditionBaseline()
    totals = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    false_positives: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory() as directory:
        for path, expected in create_cases(Path(directory)):
            result = analyzer.analyze_path(path)
            predicted = {finding.code for finding in result.findings}
            unexpected = predicted - expected
            if unexpected:
                false_positives.append(
                    {"case": path.name, "unexpected_findings": sorted(unexpected)}
                )
            for code in CODES:
                totals[code]["tp"] += code in expected and code in predicted
                totals[code]["fp"] += code not in expected and code in predicted
                totals[code]["fn"] += code in expected and code not in predicted

    metrics = {}
    for code in CODES:
        values = totals[code]
        precision = values["tp"] / max(1, values["tp"] + values["fp"])
        recall = values["tp"] / max(1, values["tp"] + values["fn"])
        metrics[code] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            **values,
        }
    report = {
        "schema_version": 1,
        "model_version": "visual-rules-1.0",
        "benchmark": "synthetic-regression-only",
        "case_count": 12,
        "metrics": metrics,
        "false_positives": false_positives,
        "release_quality_measured": False,
        "limitations": [
            "Synthetic cases verify deterministic behavior but do not measure field quality.",
            "A manually labeled real-photo condition dataset is still required.",
        ],
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if false_positives or any(
        item["precision"] < 1.0 or item["recall"] < 1.0 for item in metrics.values()
    ):
        raise SystemExit("visual baseline regression detected")
    print(f"[ok] evaluated {report['case_count']} synthetic visual cases")


if __name__ == "__main__":
    main()
