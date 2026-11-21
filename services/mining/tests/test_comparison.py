from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
from plantguard_mining.comparison import PhotoComparatorBaseline


def leaf_image(path: Path, size: tuple[int, int] = (180, 140)) -> Path:
    image = Image.new("RGB", size, (225, 220, 205))
    draw = ImageDraw.Draw(image)
    draw.ellipse((25, 15, size[0] - 25, size[1] - 15), fill=(35, 145, 55))
    draw.line((size[0] // 2, 25, size[0] // 2, size[1] - 25), fill=(180, 220, 140), width=4)
    image.save(path)
    return path


def test_small_lighting_change_remains_comparable(tmp_path: Path):
    first = leaf_image(tmp_path / "first.png")
    second = tmp_path / "second.png"
    with Image.open(first) as image:
        ImageEnhance.Brightness(image).enhance(1.12).save(second)

    result = PhotoComparatorBaseline().compare_paths(first, second)

    assert result.comparable is True
    assert result.reasons == ()


def test_different_framing_is_rejected(tmp_path: Path):
    first = leaf_image(tmp_path / "first.png")
    second = tmp_path / "second.png"
    image = Image.new("RGB", (180, 140), (225, 220, 205))
    draw = ImageDraw.Draw(image)
    draw.rectangle((15, 20, 55, 125), fill=(35, 145, 55))
    image.save(second)

    result = PhotoComparatorBaseline().compare_paths(first, second)

    assert result.comparable is False
    assert "framing_mismatch" in result.reasons


def test_aspect_ratio_and_blur_are_explained(tmp_path: Path):
    first = leaf_image(tmp_path / "first.png")
    second = leaf_image(tmp_path / "second.png", size=(100, 200))
    with Image.open(second) as image:
        image.filter(ImageFilter.GaussianBlur(radius=8)).save(second)

    result = PhotoComparatorBaseline().compare_paths(first, second)

    assert result.comparable is False
    assert "aspect_ratio_mismatch" in result.reasons
