#!/usr/bin/env python3
"""Evaluate the Russian regex extractor on a deterministic 100-phrase fixture."""

from __future__ import annotations

import json
from pathlib import Path

from plantguard_mining.text import PATTERNS, RussianSymptomExtractor

REPORT_PATH = Path("datasets/plantguard-v1/text-baseline-report.json")
SUBJECTS = ("Нижний лист", "Новый лист", "Растение", "Два листа", "Лист у окна")
EXPRESSIONS = {
    "leaf-yellowing": ("желтеет", "пожелтел", "заметно обесцвечивается"),
    "leaf-dark-spots": ("покрылся пятнами", "имеет тёмные крапины", "начал чернеть"),
    "leaf-tissue-damage": ("имеет дырки", "порван", "имеет сухие края"),
    "leaf-drop": ("опадает", "начал осыпаться", "сбрасывает листья"),
    "leaf-wilting": ("выглядит вялым", "поник", "постепенно увядает"),
}
NEGATIVE_EXPRESSIONS = (
    "не желтеет",
    "без пятен",
    "не имеет дырок",
    "не опадает",
    "не выглядит вялым",
)


def build_cases() -> list[tuple[str, set[str]]]:
    cases = []
    for code, expressions in EXPRESSIONS.items():
        for subject in SUBJECTS:
            for expression in expressions:
                cases.append((f"{subject} {expression}.", {code}))
    for subject in SUBJECTS:
        for expression in NEGATIVE_EXPRESSIONS:
            cases.append((f"{subject} {expression}.", set()))
    return cases


def main() -> None:
    extractor = RussianSymptomExtractor()
    cases = build_cases()
    predictions = [
        (
            description,
            expected,
            {finding.code for finding in extractor.extract(description).findings},
        )
        for description, expected in cases
    ]
    metrics = {}
    mismatches = [
        {
            "description": description,
            "expected": sorted(expected),
            "actual": sorted(actual),
        }
        for description, expected, actual in predictions
        if actual != expected
    ]
    for code in PATTERNS:
        true_positive = false_positive = false_negative = 0
        for _description, expected, actual in predictions:
            true_positive += code in expected and code in actual
            false_positive += code not in expected and code in actual
            false_negative += code in expected and code not in actual
        precision = true_positive / max(1, true_positive + false_positive)
        recall = true_positive / max(1, true_positive + false_negative)
        f1 = 2 * precision * recall / max(1e-12, precision + recall)
        metrics[code] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    report = {
        "schema_version": 1,
        "model_version": "ru-symptom-regex-1.0",
        "benchmark": "templated-regression-only",
        "case_count": len(cases),
        "macro_f1": round(sum(item["f1"] for item in metrics.values()) / len(metrics), 4),
        "metrics": metrics,
        "mismatches": mismatches,
        "release_quality_measured": False,
        "limitations": [
            "The fixture is templated and is not an independent user-language sample.",
            "Release evaluation still requires 100 manually labeled descriptions.",
        ],
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if mismatches:
        raise SystemExit(f"text baseline produced {len(mismatches)} mismatches")
    print(f"[ok] evaluated {len(cases)} Russian text cases")


if __name__ == "__main__":
    main()
