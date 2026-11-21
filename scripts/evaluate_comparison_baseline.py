#!/usr/bin/env python3
"""Evaluate photo comparability on 60 reproducible synthetic pairs."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance
from plantguard_mining.comparison import PhotoComparatorBaseline

REPORT_PATH = Path("datasets/plantguard-v1/comparison-baseline-report.json")


def leaf(path: Path, index: int, size: tuple[int, int] = (180, 140)) -> Path:
    image = Image.new("RGB", size, (220, 215, 195))
    draw = ImageDraw.Draw(image)
    green = (25 + index % 15, 125 + index % 25, 40 + index % 10)
    draw.ellipse((22, 12, size[0] - 22, size[1] - 12), fill=green)
    draw.line(
        (size[0] // 2, 20, size[0] // 2, size[1] - 20),
        fill=(170, 215, 135),
        width=4,
    )
    image.save(path)
    return path


def build_pairs(root: Path) -> list[tuple[Path, Path, bool, str]]:
    pairs = []
    for index in range(20):
        first = leaf(root / f"comparable-a-{index}.png", index)
        second = root / f"comparable-b-{index}.png"
        with Image.open(first) as image:
            ImageEnhance.Brightness(image).enhance(1.04 + index % 4 * 0.02).save(second)
        pairs.append((first, second, True, "small_lighting_change"))
    for index in range(15):
        first = leaf(root / f"framing-a-{index}.png", index)
        second = root / f"framing-b-{index}.png"
        image = Image.new("RGB", (180, 140), (220, 215, 195))
        draw = ImageDraw.Draw(image)
        draw.rectangle((10 + index % 5, 12, 48, 130), fill=(30, 140, 45))
        image.save(second)
        pairs.append((first, second, False, "framing_mismatch"))
    for index in range(15):
        first = leaf(root / f"aspect-a-{index}.png", index)
        second = leaf(root / f"aspect-b-{index}.png", index, size=(100, 200))
        pairs.append((first, second, False, "aspect_ratio_mismatch"))
    for index in range(10):
        first = leaf(root / f"lighting-a-{index}.png", index)
        second = root / f"lighting-b-{index}.png"
        with Image.open(first) as image:
            ImageEnhance.Brightness(image).enhance(2.4).save(second)
        pairs.append((first, second, False, "lighting_mismatch"))
    return pairs


def main() -> None:
    comparator = PhotoComparatorBaseline()
    true_positive = true_negative = false_positive = false_negative = 0
    failures = []
    reason_counts: dict[str, int] = {}
    with tempfile.TemporaryDirectory() as directory:
        pairs = build_pairs(Path(directory))
        for first, second, expected, category in pairs:
            result = comparator.compare_paths(first, second)
            true_positive += expected and result.comparable
            true_negative += not expected and not result.comparable
            false_positive += not expected and result.comparable
            false_negative += expected and not result.comparable
            for reason in result.reasons:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            if result.comparable != expected:
                failures.append(
                    {
                        "category": category,
                        "expected_comparable": expected,
                        "reasons": list(result.reasons),
                    }
                )
    incompatible_recall = true_negative / max(1, true_negative + false_positive)
    comparable_recall = true_positive / max(1, true_positive + false_negative)
    report = {
        "schema_version": 1,
        "model_version": "photo-comparability-1.0",
        "benchmark": "synthetic-regression-only",
        "pair_count": 60,
        "confusion": {
            "true_comparable": true_positive,
            "true_incompatible": true_negative,
            "false_accept": false_positive,
            "false_reject": false_negative,
        },
        "incompatible_recall": round(incompatible_recall, 4),
        "comparable_recall": round(comparable_recall, 4),
        "reason_counts": dict(sorted(reason_counts.items())),
        "failures": failures,
        "release_quality_measured": False,
        "limitations": [
            "Synthetic pairs test deterministic gates, not real repeat-photo quality.",
            "Release evaluation still requires at least 50 manually labeled incompatible pairs.",
        ],
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if incompatible_recall < 0.95 or comparable_recall < 0.95:
        raise SystemExit("photo-comparison regression detected")
    print(
        f"[ok] evaluated 60 pairs: incompatible recall={incompatible_recall:.2f}, "
        f"comparable recall={comparable_recall:.2f}"
    )


if __name__ == "__main__":
    main()
