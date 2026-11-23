#!/usr/bin/env python3
"""Validate the locked PlantGuard image manifest without downloading its media."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

SUPPORTED_LABELS = {
    "crassula_ovata",
    "dracaena_fragrans",
    "monstera_deliciosa",
    "epipremnum_aureum",
    "ficus_benjamina",
    "ficus_elastica",
    "goeppertia_zebrina",
    "oxalis_triangularis",
}
ALL_LABELS = SUPPORTED_LABELS | {"unknown"}
ALLOWED_LICENSES = {
    "cc0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "cc-by": "https://creativecommons.org/licenses/by/4.0/",
    "cc-by-sa": "https://creativecommons.org/licenses/by-sa/4.0/",
}
REQUIRED_SPLIT_COUNTS = {"train": 60, "validation": 14, "test": 50}
LOW_RESOURCE_SPLIT_COUNTS = {
    "goeppertia_zebrina": {"train": 24, "validation": 5, "test": 10},
}
REQUIRED_FIELDS = {
    "sample_id",
    "subject_id",
    "source_media_id",
    "label",
    "scientific_name",
    "split",
    "image_url",
    "observation_url",
    "license",
    "license_url",
    "attribution",
    "width",
    "height",
}


def load_manifest(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"line {line_number}: invalid JSON") from error
        if not isinstance(record, dict):
            raise ValueError(f"line {line_number}: expected an object")
        records.append(record)
    return records


def _https_url(value: object) -> bool:
    return isinstance(value, str) and urlparse(value).scheme == "https"


def audit_manifest(records: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    sample_ids: set[str] = set()
    media_ids: set[str] = set()
    subject_splits: dict[str, set[str]] = defaultdict(set)
    counts: Counter[tuple[str, str]] = Counter()
    licenses: Counter[str] = Counter()

    for index, record in enumerate(records, start=1):
        missing = sorted(REQUIRED_FIELDS - record.keys())
        if missing:
            errors.append(f"record {index}: missing fields {', '.join(missing)}")
            continue

        sample_id = str(record["sample_id"])
        media_id = str(record["source_media_id"])
        subject_id = str(record["subject_id"])
        label = str(record["label"])
        split = str(record["split"])
        license_code = str(record["license"]).lower()

        if sample_id in sample_ids:
            errors.append(f"record {index}: duplicate sample_id {sample_id}")
        sample_ids.add(sample_id)
        if media_id in media_ids:
            errors.append(f"record {index}: duplicate source_media_id {media_id}")
        media_ids.add(media_id)

        if label not in ALL_LABELS:
            errors.append(f"record {index}: unsupported label {label}")
        if split not in REQUIRED_SPLIT_COUNTS:
            errors.append(f"record {index}: unsupported split {split}")
        if license_code not in ALLOWED_LICENSES:
            errors.append(f"record {index}: disallowed license {license_code}")
        elif record["license_url"] != ALLOWED_LICENSES[license_code]:
            errors.append(f"record {index}: license URL does not match {license_code}")
        if not _https_url(record["image_url"]):
            errors.append(f"record {index}: image_url must use HTTPS")
        if not _https_url(record["observation_url"]):
            errors.append(f"record {index}: observation_url must use HTTPS")
        if not str(record["attribution"]).strip():
            errors.append(f"record {index}: attribution is empty")
        if not isinstance(record["width"], int) or record["width"] < 224:
            errors.append(f"record {index}: image width is below 224 px")
        if not isinstance(record["height"], int) or record["height"] < 224:
            errors.append(f"record {index}: image height is below 224 px")

        subject_splits[subject_id].add(split)
        counts[(label, split)] += 1
        licenses[license_code] += 1

    leaked_subjects = sorted(
        subject_id for subject_id, splits in subject_splits.items() if len(splits) > 1
    )
    if leaked_subjects:
        errors.append(f"subjects present in multiple splits: {', '.join(leaked_subjects[:10])}")

    for label in sorted(ALL_LABELS):
        required_counts = LOW_RESOURCE_SPLIT_COUNTS.get(label, REQUIRED_SPLIT_COUNTS)
        for split, minimum in required_counts.items():
            actual = counts[(label, split)]
            if actual < minimum:
                errors.append(f"{label}/{split}: expected at least {minimum}, found {actual}")

    for label, split_counts in LOW_RESOURCE_SPLIT_COUNTS.items():
        actual = sum(counts[(label, split)] for split in split_counts)
        warnings.append(
            f"{label} is a low-resource class with {actual} samples; "
            "its metrics must be interpreted separately"
        )

    if any(record.get("source") != "iNaturalist" for record in records):
        warnings.append("manifest contains a source other than iNaturalist")

    return {
        "schema_version": 1,
        "ready": not errors,
        "sample_count": len(records),
        "subject_count": len(subject_splits),
        "supported_labels": sorted(SUPPORTED_LABELS),
        "counts": {
            label: {split: counts[(label, split)] for split in REQUIRED_SPLIT_COUNTS}
            for label in sorted(ALL_LABELS)
        },
        "licenses": dict(sorted(licenses.items())),
        "cross_split_subjects": len(leaked_subjects),
        "errors": errors,
        "warnings": warnings,
    }


def write_report(report: dict[str, Any], path: Path) -> None:
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    report = audit_manifest(load_manifest(args.manifest))
    write_report(report, args.report)
    if not report["ready"]:
        for error in report["errors"]:
            print(f"[error] {error}")
        raise SystemExit(1)
    print(
        f"[ok] {report['sample_count']} licensed samples, "
        f"{report['cross_split_subjects']} cross-split subjects"
    )


if __name__ == "__main__":
    main()
