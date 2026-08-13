"""LLM provider abstraction for the chat endpoint.

Providers convert a system prompt + user question into a plain-text answer.
``get_llm_provider()`` lazily builds the provider from settings.LLM_PROVIDER:
- "gemini": the Google Gemini API (requires GEMINI_API_KEY).
- "local":   offline development-only provider that answers verbatim from the
             top retrieved chunk. Never enabled in production.

The provider is middleware-friendly: it is only wired to the model when the
provider fails to return a grounded answer (see rag_service).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMProviderError(Exception):
    """Raised when an LLM provider cannot produce an answer."""


class LLMProvider(ABC):
    """Interface contract for any chat-answer provider."""

    name: str = "base"

    @abstractmethod
    def answer(self, *, system_prompt: str, question: str) -> str:
        """Return a plain-text answer for ``question`` given ``system_prompt``."""


class LocalExtractiveProvider(LLMProvider):
    """Offline provider used for development and deterministic tests.

    Simulates a grounded answer by quoting the evidence labelled ``[1]``.
    This intentionally has no network access and no installed-model cost.
    """

    name = "local"

    def answer(self, *, system_prompt: str, question: str) -> str:
        # Locate the first "[1] " tagged evidence block, if present.
        marker = "[1] "
        index = system_prompt.find(marker)
        if index == -1:
            raise LLMProviderError("No evidence block [1] present in the prompt.")
        snippet = system_prompt[index + len(marker) :]
        snippet = snippet[:400].strip()
        return f"Based on the top document match: {snippet}"


class GeminiProvider(LLMProvider):
    """Google Gemini-backed provider using the google-genai SDK."""

    name = "gemini"

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.LLM_MODEL
        if not self.api_key:
            raise LLMProviderError(
                "GEMINI_API_KEY is not configured. Set LLM_PROVIDER=gemini with a "
                "valid GEMINI_API_KEY, or use LLM_PROVIDER=local for offline testing."
            )

    def answer(self, *, system_prompt: str, question: str) -> str:
        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError as exc:  # pragma: no cover - dependency always installed
            raise LLMProviderError("google-genai is not installed.") from exc

        client = genai.Client(api_key=self.api_key)
        response = client.models.generate_content(
            model=self.model,
            contents=question,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.2,
            ),
        )
        text = response.text if response.text else ""
        text = text.strip()
        if not text:
            raise LLMProviderError("Gemini returned an empty response.")
        return text


class _ProviderHolder:
    def __init__(self) -> None:
        self._instance: LLMProvider | None = None

    def get(self) -> LLMProvider:
        if self._instance is None:
            provider = _build_provider(settings.LLM_PROVIDER)
            logger.info("Initialized LLM provider: %s (model=%s)", provider.name, settings.LLM_MODEL)
            self._instance = provider
        return self._instance

    def set(self, provider: LLMProvider | None) -> None:
        """Allow tests to inject a fake provider (mirrors embedding_service)."""
        self._instance = provider


_holder = _ProviderHolder()


def _build_provider(name: str) -> LLMProvider:
    if name == "local":
        return LocalExtractiveProvider()
    if name == "gemini":
        return GeminiProvider()
    raise LLMProviderError(
        f"Unknown LLM_PROVIDER {name!r}. Supported values: 'gemini', 'local'."
    )


def get_llm_provider() -> LLMProvider:
    return _holder.get()


def set_llm_provider(provider: LLMProvider | None) -> None:
    _holder.set(provider)