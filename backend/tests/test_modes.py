"""Real/demo configuration and effective provenance fail closed."""

import pytest

from app.config import Settings


@pytest.mark.parametrize(
    "options",
    [
        {"mode": "typo"},
        {"asr_provider": "typo"},
        {"llm_provider": "external"},
        {"mode": "real"},
        {"mode": "real", "asr_provider": "faster_whisper", "llm_provider": "mock"},
        {"asr_compute_type": "invalid"},
    ],
)
def test_invalid_configuration_rejected(options):
    with pytest.raises(ValueError):
        Settings(_env_file=None, **options)


def test_local_implementation_needs_no_api_key():
    settings = Settings(
        _env_file=None,
        mode="real",
        asr_provider="faster_whisper",
        llm_provider="local_keywords",
        llm_api_key="",
    )
    assert settings.mode == "real" and settings.llm_api_key == ""


def test_demo_defaults_explicit():
    settings = Settings(_env_file=None)
    assert settings.mode == "demo" and settings.asr_provider == settings.llm_provider == "mock"
