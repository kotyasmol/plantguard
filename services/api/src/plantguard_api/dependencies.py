from functools import lru_cache

from plantguard_mining import (
    GroundedExplanationGenerator,
    KnnPlantIdentifier,
    PhotoComparatorBaseline,
    RussianSymptomExtractor,
    VisualConditionBaseline,
)

from .config import get_settings
from .llm import CompatibleExplanationPlanner
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


@lru_cache
def get_symptom_extractor() -> RussianSymptomExtractor:
    return RussianSymptomExtractor()


@lru_cache
def get_photo_comparator() -> PhotoComparatorBaseline:
    return PhotoComparatorBaseline()


@lru_cache
def get_explanation_generator() -> GroundedExplanationGenerator:
    settings = get_settings()
    if settings.llm_base_url and settings.llm_api_key and settings.llm_model:
        planner = CompatibleExplanationPlanner(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value(),
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
        )
        return GroundedExplanationGenerator(planner)
    return GroundedExplanationGenerator()
