from functools import lru_cache

from plantguard_mining import KnnPlantIdentifier, VisualConditionBaseline

from .config import get_settings
from .photo_links import PhotoLinkSigner
from .photo_storage import LocalPhotoStorage, PhotoStorage


def get_photo_storage() -> PhotoStorage:
    return LocalPhotoStorage(get_settings().photo_storage_path)


def get_photo_link_signer() -> PhotoLinkSigner:
    return PhotoLinkSigner(get_settings().photo_signing_key)


@lru_cache
def get_plant_identifier() -> KnnPlantIdentifier:
    return KnnPlantIdentifier.load_default()


@lru_cache
def get_visual_condition_analyzer() -> VisualConditionBaseline:
    return VisualConditionBaseline()
