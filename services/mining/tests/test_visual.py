from pathlib import Path

from PIL import Image, ImageDraw
from plantguard_mining.visual import VisualConditionBaseline


def save(path: Path, color: tuple[int, int, int]) -> Path:
    Image.new("RGB", (128, 128), color=color).save(path)
    return path


def test_yellowing_is_reported_as_visible_finding(tmp_path: Path):
    result = VisualConditionBaseline().analyze_path(
        save(tmp_path / "yellow.png", (180, 180, 30))
    )

    assert result.analyzable is True
    assert "leaf-yellowing" in {finding.code for finding in result.findings}


def test_local_dark_spots_are_reported(tmp_path: Path):
    path = save(tmp_path / "spots.png", (40, 150, 45))
    image = Image.open(path)
    draw = ImageDraw.Draw(image)
    for x, y in ((30, 30), (70, 45), (50, 90)):
        draw.ellipse((x - 12, y - 12, x + 12, y + 12), fill=(10, 45, 10))
    image.save(path)

    result = VisualConditionBaseline().analyze_path(path)

    assert "leaf-dark-spots" in {finding.code for finding in result.findings}


def test_low_plant_coverage_is_not_analyzable(tmp_path: Path):
    result = VisualConditionBaseline().analyze_path(
        save(tmp_path / "wall.png", (180, 180, 180))
    )

    assert result.analyzable is False
    assert result.findings == ()
