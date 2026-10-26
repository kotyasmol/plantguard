from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol
from uuid import uuid4

MEDIA_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
EXTENSION_MEDIA_TYPES = {
    extension: media_type for media_type, extension in MEDIA_TYPE_EXTENSIONS.items()
}


class InvalidStorageKey(ValueError):
    pass


class PhotoNotFoundError(FileNotFoundError):
    pass


@dataclass(frozen=True)
class StoredPhoto:
    storage_key: str
    size_bytes: int
    checksum_sha256: str


@dataclass(frozen=True)
class PhotoFile:
    path: Path
    media_type: str


class PhotoStorage(Protocol):
    def save(self, content: bytes, media_type: str) -> StoredPhoto: ...

    def locate(self, storage_key: str) -> PhotoFile: ...

    def delete(self, storage_key: str) -> None: ...


class LocalPhotoStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def save(self, content: bytes, media_type: str) -> StoredPhoto:
        try:
            extension = MEDIA_TYPE_EXTENSIONS[media_type]
        except KeyError:
            raise ValueError(f"unsupported media type: {media_type}") from None

        object_id = uuid4().hex
        storage_key = f"{object_id[:2]}/{object_id[2:4]}/{object_id}{extension}"
        destination = self._resolve(storage_key)
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)

        descriptor, temporary_name = tempfile.mkstemp(prefix=".upload-", dir=destination.parent)
        try:
            with os.fdopen(descriptor, "wb") as temporary_file:
                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.chmod(temporary_name, 0o600)
            os.replace(temporary_name, destination)
        except BaseException:
            Path(temporary_name).unlink(missing_ok=True)
            raise

        return StoredPhoto(
            storage_key=storage_key,
            size_bytes=len(content),
            checksum_sha256=hashlib.sha256(content).hexdigest(),
        )

    def locate(self, storage_key: str) -> PhotoFile:
        path = self._resolve(storage_key)
        if path.is_symlink() or not path.is_file():
            raise PhotoNotFoundError(storage_key)
        try:
            media_type = EXTENSION_MEDIA_TYPES[path.suffix.lower()]
        except KeyError:
            raise PhotoNotFoundError(storage_key) from None
        return PhotoFile(path=path, media_type=media_type)

    def delete(self, storage_key: str) -> None:
        photo = self.locate(storage_key)
        photo.path.unlink()
        self._remove_empty_parents(photo.path.parent)

    def _resolve(self, storage_key: str) -> Path:
        key = PurePosixPath(storage_key)
        if key.is_absolute() or not key.parts or any(part in {"", ".", ".."} for part in key.parts):
            raise InvalidStorageKey(storage_key)
        if "\\" in storage_key:
            raise InvalidStorageKey(storage_key)

        candidate = self.root.joinpath(*key.parts).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            raise InvalidStorageKey(storage_key) from None
        return candidate

    def _remove_empty_parents(self, directory: Path) -> None:
        while directory != self.root:
            try:
                directory.rmdir()
            except OSError:
                break
            directory = directory.parent
