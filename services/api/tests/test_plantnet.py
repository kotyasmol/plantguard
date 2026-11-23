from pathlib import Path

import httpx
from plantguard_api.plantnet import (
    HybridPlantIdentifier,
    PlantNetIdentifier,
    PlantNetUnavailable,
)
from plantguard_mining import IdentificationCandidate, IdentificationOutcome
from plantguard_mining.ports import ImageReference


def plant_image(tmp_path: Path) -> ImageReference:
    path = tmp_path / "plant.jpg"
    path.write_bytes(b"test-image")
    return ImageReference(uri=str(path), media_type="image/jpeg")


def test_plantnet_returns_five_localized_candidates_and_caches(tmp_path: Path):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.path == "/v2/identify/all"
        assert request.url.params["api-key"] == "free-key"
        assert request.url.params["lang"] == "ru"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "score": score,
                        "species": {
                            "scientificNameWithoutAuthor": scientific,
                            "commonNames": [common],
                        },
                    }
                    for score, scientific, common in (
                        (0.91, "Crassula ovata", "Толстянка яйцевидная"),
                        (0.04, "Crassula arborescens", "Толстянка древовидная"),
                        (0.02, "Portulacaria afra", "Портулакария африканская"),
                        (0.01, "Crassula perforata", "Толстянка продырявленная"),
                        (0.01, "Crassula multicava", "Толстянка многополостная"),
                        (0.01, "Sedum adolphi", "Очиток Адольфа"),
                    )
                ]
            },
        )

    identifier = PlantNetIdentifier(
        api_key="free-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    image = plant_image(tmp_path)

    first = identifier.identify(image)
    second = identifier.identify(image)

    assert first == second
    assert calls == 1
    assert first.recognized is True
    assert len(first.candidates) == 5
    assert first.candidates[0].species_code == "crassula_ovata"
    assert first.candidates[0].scientific_name == "Crassula ovata"
    assert first.candidates[0].common_name == "Толстянка яйцевидная"


def test_plantnet_rejects_low_confidence_result(tmp_path: Path):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "score": 0.21,
                        "species": {
                            "scientificNameWithoutAuthor": "Crassula ovata",
                            "commonNames": [],
                        },
                    }
                ]
            },
        )

    identifier = PlantNetIdentifier(
        api_key="free-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    outcome = identifier.identify(plant_image(tmp_path))

    assert outcome.recognized is False
    assert outcome.candidates[0].display_name == "Crassula ovata"


def test_hybrid_identifier_uses_local_fallback(tmp_path: Path):
    class UnavailableIdentifier:
        def identify(self, _image: ImageReference) -> IdentificationOutcome:
            raise PlantNetUnavailable

    class LocalIdentifier:
        def identify(self, _image: ImageReference) -> IdentificationOutcome:
            return IdentificationOutcome(
                candidates=(IdentificationCandidate("ficus_elastica", "Фикус", 0.8),),
                recognized=True,
                model_version="local-test",
            )

    identifier = HybridPlantIdentifier(UnavailableIdentifier(), LocalIdentifier())

    outcome = identifier.identify(plant_image(tmp_path))

    assert outcome.recognized is True
    assert outcome.candidates[0].species_code == "ficus_elastica"
    assert outcome.model_version == "local-test+plantnet-fallback"
