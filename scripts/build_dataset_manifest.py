#!/usr/bin/env python3
"""Build a deterministic, license-filtered image registry from iNaturalist."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dataset_registry import ALLOWED_LICENSES, REQUIRED_SPLIT_COUNTS, audit_manifest, write_report

API_URL = "https://api.inaturalist.org/v1/observations"
USER_AGENT = "PlantGuard dataset registry/1.0"
SUPPORTED_TAXA = {
    "monstera_deliciosa": ["Monstera deliciosa"],
    "epipremnum_aureum": ["Epipremnum aureum"],
    "ficus_elastica": ["Ficus elastica"],
    "unknown": [
        "Aloe vera",
        "Tradescantia zebrina",
    ],
}


def fetch_page(scientific_name: str, page: int) -> dict[str, Any]:
    query = urlencode(
        {
            "taxon_name": scientific_name,
            "quality_grade": "research",
            "photos": "true",
            "photo_license": ",".join(ALLOWED_LICENSES),
            "per_page": 200,
            "page": page,
            "order_by": "id",
            "order": "asc",
        }
    )
    request = Request(f"{API_URL}?{query}", headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def _medium_url(url: str) -> str:
    return url.replace("/square.", "/medium.")


def collect(scientific_name: str, label: str, limit: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    page = 1
    while len(records) < limit:
        payload = fetch_page(scientific_name, page)
        results = payload.get("results", [])
        if not results:
            break
        for observation in results:
            taxon = observation.get("taxon") or {}
            if taxon.get("name") != scientific_name:
                continue
            eligible_photos = [
                photo
                for photo in observation.get("photos", [])
                if str(photo.get("license_code", "")).lower() in ALLOWED_LICENSES
            ]
            if not eligible_photos:
                continue
            photo = eligible_photos[0]
            dimensions = photo.get("original_dimensions") or {}
            width = dimensions.get("width")
            height = dimensions.get("height")
            if not isinstance(width, int) or not isinstance(height, int):
                continue
            if min(width, height) < 224:
                continue
            license_code = str(photo["license_code"]).lower()
            observation_id = str(observation["id"])
            photo_id = str(photo["id"])
            records.append(
                {
                    "sample_id": f"inat-{photo_id}",
                    "subject_id": f"inat-observation-{observation_id}",
                    "source_media_id": photo_id,
                    "source": "iNaturalist",
                    "label": label,
                    "scientific_name": scientific_name,
                    "split": "",
                    "image_url": _medium_url(str(photo["url"])),
                    "observation_url": f"https://www.inaturalist.org/observations/{observation_id}",
                    "license": license_code,
                    "license_url": ALLOWED_LICENSES[license_code],
                    "attribution": str(photo.get("attribution") or "").strip(),
                    "width": width,
                    "height": height,
                }
            )
            if len(records) >= limit:
                break
        page += 1
        if page > int(payload.get("total_results", 0) / 200) + 2:
            break
        time.sleep(0.2)
    return records


def assign_splits(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    required_total = sum(REQUIRED_SPLIT_COUNTS.values())
    if len(records) < required_total:
        raise RuntimeError(f"not enough eligible records: {len(records)} < {required_total}")
    ordered = sorted(
        records,
        key=lambda item: hashlib.sha256(str(item["subject_id"]).encode()).hexdigest(),
    )[:required_total]
    offset = 0
    for split, count in REQUIRED_SPLIT_COUNTS.items():
        for record in ordered[offset : offset + count]:
            record["split"] = split
        offset += count
    return ordered


def build_manifest() -> list[dict[str, Any]]:
    total = sum(REQUIRED_SPLIT_COUNTS.values())
    manifest: list[dict[str, Any]] = []
    for label, taxa in SUPPORTED_TAXA.items():
        candidates: list[dict[str, Any]] = []
        per_taxon = total if len(taxa) == 1 else (total // len(taxa)) + 8
        for taxon in taxa:
            collected = collect(taxon, label, per_taxon)
            print(f"[source] {taxon}: {len(collected)} eligible observations")
            candidates.extend(collected)
        manifest.extend(assign_splits(candidates))
    return sorted(manifest, key=lambda item: str(item["sample_id"]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("datasets/plantguard-v1/manifest.jsonl"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("datasets/plantguard-v1/audit-report.json"),
    )
    args = parser.parse_args()

    records = build_manifest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )
    report = audit_manifest(records)
    write_report(report, args.report)
    if not report["ready"]:
        raise SystemExit("generated manifest did not pass its audit")
    print(f"[ok] wrote {len(records)} records to {args.output}")


if __name__ == "__main__":
    main()
