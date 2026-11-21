from pathlib import Path

from PIL import Image
from plantguard_mining.identification import KnnPlantIdentifier, fit_artifact


def artifact() -> dict[str, object]:
    samples = []
    for label, value in (
        ("monstera_deliciosa", 0.1),
        ("epipremnum_aureum", 0.5),
        ("ficus_elastica", 0.9),
        ("unknown", 0.3),
    ):
        samples.extend((label, [value, value]) for _ in range(3))
    return fit_artifact(
        samples,
        model_version="test-model",
        recognition_threshold=0.6,
        neighbors=3,
    )


def test_knn_scores_are_normalized():
    identifier = KnnPlantIdentifier(artifact())

    scores = identifier.scores_for_features([0.9, 0.9])

    assert sum(scores.values()) == 1.0
    assert max(scores, key=scores.get) == "ficus_elastica"


def test_identifier_returns_top_three_and_recognition_decision(tmp_path: Path, monkeypatch):
    identifier = KnnPlantIdentifier(artifact())
    path = tmp_path / "plant.png"
    Image.new("RGB", (96, 96), color=(20, 100, 20)).save(path)
    monkeypatch.setattr(
        "plantguard_mining.identification.image_features", lambda _path: [0.9, 0.9]
    )

    outcome = identifier.identify_path(path)

    assert outcome.recognized is True
    assert len(outcome.candidates) == 3
    assert outcome.candidates[0].species_code == "ficus_elastica"


def test_unknown_image_is_not_forced_into_supported_species(tmp_path: Path, monkeypatch):
    identifier = KnnPlantIdentifier(artifact())
    path = tmp_path / "unknown.png"
    Image.new("RGB", (96, 96), color=(100, 100, 100)).save(path)
    monkeypatch.setattr(
        "plantguard_mining.identification.image_features", lambda _path: [0.3, 0.3]
    )

    outcome = identifier.identify_path(path)

    assert outcome.recognized is False
    assert len(outcome.candidates) == 3
