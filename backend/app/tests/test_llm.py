"""LLM provider tests: local extractive provider, Gemini config, unknown provider."""

import pytest

from app.core.config import settings
from app.rag.prompts import build_system_prompt
from app.services.llm_service import (
    LLMProviderError,
    LocalExtractiveProvider,
    get_llm_provider,
    set_llm_provider,
)


def test_local_provider_returns_top_evidence():
    provider = LocalExtractiveProvider()
    prompt = build_system_prompt("[1] The shuttle runs every 15 minutes.\n\n[2] Cafeteria opens at 9am.")
    answer = provider.answer(system_prompt=prompt, question="When does the shuttle run?")
    assert "every 15 minutes" in answer


def test_local_provider_raises_without_evidence():
    provider = LocalExtractiveProvider()
    with pytest.raises(LLMProviderError):
        provider.answer(system_prompt="no tagged evidence here", question="hi")


def test_gemini_provider_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    from app.services.llm_service import GeminiProvider

    with pytest.raises(LLMProviderError):
        GeminiProvider()


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "nope")
    set_llm_provider(None)
    with pytest.raises(LLMProviderError):
        get_llm_provider()


def test_get_llm_provider_returns_fake_from_fixture(fake_llm_provider):
    assert get_llm_provider() is fake_llm_provider


def test_set_llm_provider_resets(monkeypatch):
    from app.services.llm_service import LocalExtractiveProvider

    monkeypatch.setattr(settings, "LLM_PROVIDER", "local")
    set_llm_provider(None)
    assert isinstance(get_llm_provider(), LocalExtractiveProvider)