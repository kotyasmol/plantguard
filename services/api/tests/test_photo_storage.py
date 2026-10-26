from pathlib import Path

import pytest
from plantguard_api.photo_links import PhotoLinkSigner
from plantguard_api.photo_storage import InvalidStorageKey, LocalPhotoStorage, PhotoNotFoundError


def test_local_storage_rejects_path_traversal(tmp_path: Path):
    storage = LocalPhotoStorage(tmp_path)

    with pytest.raises(InvalidStorageKey):
        storage.locate("../outside.jpg")

    with pytest.raises(InvalidStorageKey):
        storage.locate("folder\\outside.jpg")


def test_local_storage_reports_missing_photo(tmp_path: Path):
    storage = LocalPhotoStorage(tmp_path)

    with pytest.raises(PhotoNotFoundError):
        storage.locate("aa/bb/missing.jpg")


def test_photo_link_signature_expires_and_is_bound_to_http_method():
    signer = PhotoLinkSigner("test-photo-signing-key-with-32-characters")
    signature = signer.sign("GET", "aa/bb/photo.jpg", expires=200)

    assert signer.verify("GET", "aa/bb/photo.jpg", 200, signature, now=199)
    assert not signer.verify("DELETE", "aa/bb/photo.jpg", 200, signature, now=199)
    assert not signer.verify("GET", "aa/bb/photo.jpg", 200, signature, now=201)
