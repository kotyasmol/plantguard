"""Pl@ntNet identification adapter with a local fail-safe."""

from __future__ import annotations

import re
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

import httpx
from plantguard_mining import IdentificationCandidate, IdentificationOutcome
from plantguard_mining.ports import ImageReference, PlantIdentifier


class PlantNetUnavailable(RuntimeError):
    """Raised when the remote identification service cannot answer safely."""


def _species_code(scientific_name: str) -> str:
    code = re.sub(r"[^a-z0-9]+", "_", scientific_name.casefold()).strip("_")
    return code or "unknown_species"


class PlantNetIdentifier:
    model_version = "plantnet-v2"

    def __init__(
        self,
        *,
        api_key: str,
        project: str = "all",
        language: str = "ru",
        timeout: float = 12.0,
        recognition_threshold: float = 0.55,
        max_results: int = 5,
        client: httpx.Client | None = None,
        cache_size: int = 128,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Pl@ntNet API key cannot be empty")
        self.api_key = api_key
        self.project = project
        self.language = language
        self.recognition_threshold = recognition_threshold
        self.max_results = max_results
        self.client = client or httpx.Client(timeout=timeout)
        self.cache_size = cache_size
        self._cache: OrderedDict[str, IdentificationOutcome] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _cache_key(image: ImageReference) -> str:
        path = Path(image.uri)
        stat = path.stat()
        return f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"

    def identify(self, image: ImageReference) -> IdentificationOutcome:
        cache_key = self._cache_key(image)
        # Serialising cache misses also prevents duplicate paid requests when the
        # identification and assessment endpoints inspect the same observation.
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                self._cache.move_to_end(cache_key)
                return cached
            outcome = self._identify_uncached(image)
            self._cache[cache_key] = outcome
            self._cache.move_to_end(cache_key)
            while len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)
            return outcome

    def _identify_uncached(self, image: ImageReference) -> IdentificationOutcome:
        path = Path(image.uri)
        try:
            with path.open("rb") as photo:
                response = self.client.post(
                    f"https://my-api.plantnet.org/v2/identify/{self.project}",
                    params={
                        "api-key": self.api_key,
                        "lang": self.language,
                        "include-related-images": "false",
                        "no-reject": "false",
                    },
                    files={"images": (path.name, photo, image.media_type)},
                    data={"organs": "auto"},
                )
            response.raise_for_status()
            payload = response.json()
        except (OSError, httpx.HTTPError, ValueError) as error:
            raise PlantNetUnavailable("Pl@ntNet identification is unavailable") from error

        candidates = tuple(
            candidate
            for item in payload.get("results", [])[: self.max_results]
            if (candidate := self._parse_candidate(item)) is not None
        )
        if not candidates:
            raise PlantNetUnavailable("Pl@ntNet returned no usable candidates")
        return IdentificationOutcome(
            candidates=candidates,
            recognized=candidates[0].confidence >= self.recognition_threshold,
            model_version=self.model_version,
        )

    @staticmethod
    def _parse_candidate(item: Any) -> IdentificationCandidate | None:
        if not isinstance(item, dict) or not isinstance(item.get("species"), dict):
            return None
        species = item["species"]
        scientific_name = str(
            species.get("scientificNameWithoutAuthor")
            or species.get("scientificName")
            or ""
        ).strip()
        if not scientific_name:
            return None
        common_names = species.get("commonNames")
        common_name = (
            str(common_names[0]).strip()
            if isinstance(common_names, list) and common_names
            else scientific_name
        )
        try:
            confidence = min(1.0, max(0.0, float(item.get("score", 0))))
        except (TypeError, ValueError):
            return None
        return IdentificationCandidate(
            species_code=_species_code(scientific_name),
            display_name=common_name,
            confidence=confidence,
            scientific_name=scientific_name,
            common_name=common_name,
        )


class HybridPlantIdentifier:
    """Prefer the broad remote catalogue and retain offline behaviour."""

    def __init__(self, primary: PlantIdentifier, fallback: PlantIdentifier) -> None:
        self.primary = primary
        self.fallback = fallback

    def identify(self, image: ImageReference) -> IdentificationOutcome:
        try:
            return self.primary.identify(image)
        except PlantNetUnavailable:
            fallback = self.fallback.identify(image)
            return IdentificationOutcome(
                candidates=fallback.candidates,
                recognized=fallback.recognized,
                model_version=f"{fallback.model_version}+plantnet-fallback",
            )
