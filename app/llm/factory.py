"""
LLM Factory — بناء المزود المناسب من الإعدادات فقط.

لا يوجد في بقية المشروع أي import لمزود معين.
كل ما يُستورد هو get_llm() التي تعيد LLMProvider interface.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.llm.base import LLMProvider
from app.config import get_settings

logger = logging.getLogger(__name__)

_instance: Optional[LLMProvider] = None


def get_llm() -> LLMProvider:
    """يعيد المزود المُعدَّد في .env (cached singleton)."""
    global _instance
    if _instance is not None:
        return _instance

    settings = get_settings()
    provider = settings.llm_provider.lower()

    if settings.ci_mode:
        from app.llm.mock_provider import MockLLMProvider

        _instance = MockLLMProvider()
        logger.warning("CI mode — MockLLMProvider نشط (لا اتصالات خارجية)")
        return _instance

    if provider in ("ollama", "local"):
        from app.llm.ollama_provider import OllamaProvider

        _instance = OllamaProvider()
    elif provider == "openai":
        from app.llm.openai_provider import OpenAIProvider

        _instance = OpenAIProvider()
    elif provider == "gemini":
        from app.llm.gemini_provider import GeminiProvider

        _instance = GeminiProvider()
    else:
        raise ValueError(f"LLM provider غير مدعوم: {provider}")

    logger.info("LLM provider نشط: %s (model=%s, mode=%s)", _instance.provider_name,
                settings.llm_model, settings.ai_mode)
    return _instance


def reset_llm() -> None:
    """للاختبارات: إعادة بناء المزود بعد تغيير الإعدادات."""
    global _instance
    _instance = None
