import pytest
from plantguard_api.config import Settings
from pydantic import ValidationError


def test_production_requires_a_unique_photo_signing_key():
    with pytest.raises(ValidationError, match="PLANTGUARD_PHOTO_SIGNING_KEY"):
        Settings(_env_file=None, environment="production")


def test_production_accepts_a_custom_photo_signing_key():
    settings = Settings(
        _env_file=None,
        environment="production",
        photo_signing_key="production-photo-signing-key-with-32-characters",
    )

    assert settings.environment == "production"
