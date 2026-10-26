from __future__ import annotations

import warnings
from dataclasses import dataclass
from io import BytesIO

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

ALLOWED_IMAGE_FORMATS = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}
ALLOWED_IMAGE_TYPES = set(ALLOWED_IMAGE_FORMATS.values())


class PhotoValidationError(ValueError):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ValidatedPhoto:
    content: bytes
    media_type: str
    width: int
    height: int


async def validate_photo_upload(
    photo: UploadFile,
    *,
    max_bytes: int,
    max_pixels: int,
) -> ValidatedPhoto:
    if photo.content_type not in ALLOWED_IMAGE_TYPES:
        raise PhotoValidationError("Поддерживаются изображения JPEG, PNG и WebP", status_code=415)

    content = await photo.read(max_bytes + 1)
    if not content:
        raise PhotoValidationError("Файл изображения пуст")
    if len(content) > max_bytes:
        raise PhotoValidationError("Файл изображения слишком большой", status_code=413)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as image:
                detected_type = ALLOWED_IMAGE_FORMATS.get(image.format or "")
                width, height = image.size
                frame_count = getattr(image, "n_frames", 1)
                if detected_type != photo.content_type:
                    raise PhotoValidationError(
                        "Заявленный тип файла не соответствует содержимому изображения"
                    )
                if width * height > max_pixels:
                    raise PhotoValidationError(
                        "Разрешение изображения слишком большое", status_code=413
                    )
                if frame_count != 1:
                    raise PhotoValidationError("Анимированные изображения не поддерживаются")
                image.verify()
    except PhotoValidationError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise PhotoValidationError(
            "Разрешение изображения слишком большое", status_code=413
        ) from None
    except (OSError, SyntaxError, UnidentifiedImageError, ValueError):
        raise PhotoValidationError("Файл повреждён или не является изображением") from None

    return ValidatedPhoto(
        content=content,
        media_type=photo.content_type,
        width=width,
        height=height,
    )
