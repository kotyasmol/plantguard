import json

from scripts.dataset_registry import (
    ALLOWED_LICENSES,
    REQUIRED_SPLIT_COUNTS,
    audit_manifest,
)


def record(label: str, split: str, index: int) -> dict[str, object]:
    license_code = "cc-by"
    return {
        "sample_id": f"sample-{label}-{split}-{index}",
        "subject_id": f"subject-{label}-{split}-{index}",
        "source_media_id": f"media-{label}-{split}-{index}",
        "source": "iNaturalist",
        "label": label,
        "scientific_name": "Example plant",
        "split": split,
        "image_url": "https://example.test/image.jpg",
        "observation_url": "https://example.test/observation/1",
        "license": license_code,
        "license_url": ALLOWED_LICENSES[license_code],
        "attribution": "Example author, CC BY",
        "width": 640,
        "height": 480,
    }


def complete_manifest() -> list[dict[str, object]]:
    records = []
    for label in (
        "monstera_deliciosa",
        "epipremnum_aureum",
        "ficus_elastica",
        "unknown",
    ):
        for split, count in REQUIRED_SPLIT_COUNTS.items():
            records.extend(record(label, split, index) for index in range(count))
    return records


def test_complete_licensed_manifest_is_ready():
    report = audit_manifest(complete_manifest())

    assert report["ready"] is True
    assert report["sample_count"] == 496
    assert report["cross_split_subjects"] == 0


def test_audit_rejects_license_and_subject_leakage():
    records = complete_manifest()
    records[0]["license"] = "all-rights-reserved"
    records[1]["subject_id"] = records[0]["subject_id"]
    records[1]["split"] = "validation"

    report = audit_manifest(records)

    assert report["ready"] is False
    assert any("disallowed license" in error for error in report["errors"])
    assert report["cross_split_subjects"] == 1
    json.dumps(report)
