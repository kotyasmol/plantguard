from .config import get_settings
from .photo_links import PhotoLinkSigner
from .photo_storage import LocalPhotoStorage, PhotoStorage


def get_photo_storage() -> PhotoStorage:
    return LocalPhotoStorage(get_settings().photo_storage_path)


def get_photo_link_signer() -> PhotoLinkSigner:
    return PhotoLinkSigner(get_settings().photo_signing_key)
