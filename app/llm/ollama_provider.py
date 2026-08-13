"""
OllamaProvider — تشغيل LLM محلي عبر Ollama.

- يستخدم واجهة OpenAI-compatible (/v1/chat/completions) المدمجة في Ollama،
  لذلك نستفيد من function calling وJSON mode القياسية.
- يمكن أيضاً استخدام OpenAI SDK الرسمي مباشرة (ollama يعرض نفسه كـ OpenAI endpoint).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    LLMValidationError,
    ToolCall,
    ToolDefinition,
    validate_against_schema,
)
from app.config import get_settings

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.llm_model
        self.api_url = f"{self.base_url}/v1"

    # ────────────────────────────────
    # OpenAI-compatible chat completions
    # ────────────────────────────────
    async def _chat_completion(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.4,
        max_tokens: int = 4096,
        extra_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if extra_body:
            payload.update(extra_body)

        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await client.post(
                f"{self.api_url}/chat/completions", json=payload
            )
            resp.raise_for_status()
            return resp.json()

    # ────────────────────────────────
    # واجهة LLMProvider
    # ────────────────────────────────
    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        data = await self._chat_completion(messages, temperature, max_tokens)
        choice = data["choices"][0]
        msg = choice.get("message", {})
        return LLMResponse(
            content=msg.get("content", ""),
            finish_reason=choice.get("finish_reason"),
            raw=data,
        )

    async def generate_json(
        self,
        messages: List[LLMMessage],
        schema: Dict[str, Any],
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """
        JSON Mode + response_format=json_object + تحقق صريح من schema
        مع retry تلقائي (حتى 3 محاولات).
        """
        last_error = None
        attempts = 0
        max_attempts = 3

        while attempts < max_attempts:
            attempts += 1
            data = await self._chat_completion(
                messages,
                temperature=temperature,
                extra_body={"response_format": {"type": "json_object"}},
            )
            raw_content = data["choices"][0].get("message", {}).get("content", "{}")

            try:
                payload = json.loads(raw_content)
            except json.JSONDecodeError as exc:
                last_error = f"invalid JSON: {exc}"
                logger.warning("attempt %d: %s", attempts, last_error)
                continue

            if validate_against_schema(payload, schema):
                return payload

            last_error = "schema validation failed"
            logger.warning("attempt %d: %s", attempts, last_error)
            # إعادة المحاولة برسالة تصحيحية
            messages = messages + [
                LLMMessage(
                    role="user",
                    content=(
                        "المخرجات السابقة لم تطابق المخطط المطلوب. "
                        "راجع المخطط وأعد إنتاج JSON صحيح يطابقه بالكامل. "
                        f"الخطأ: {last_error}"
                    ),
                ),
            ]

        raise LLMValidationError(last_error or "unknown", attempts)

    async def generate_with_tools(
        self,
        messages: List[LLMMessage],
        tools: List[ToolDefinition],
        temperature: float = 0.2,
    ) -> LLMResponse:
        data = await self._chat_completion(
            messages,
            temperature=temperature,
            extra_body={"tools": [t.to_openai() for t in tools]},
        )
        choice = data["choices"][0]
        msg = choice.get("message", {})
        tool_calls: List[ToolCall] = []

        for tc in msg.get("tool_calls", []) or []:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(call_id=tc.get("id", ""), name=fn.get("name", ""), arguments=args))

        return LLMResponse(
            content=msg.get("content", ""),
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason"),
            raw=data,
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # فحص وصول Ollama + وجود الموديل
                resp = await client.get(f"{self.base_url}/api/tags", timeout=30.0)
                if resp.status_code != 200:
                    return False
                models = [m.get("name", "") for m in resp.json().get("models", [])]
                return self.model in models or any(self.model.split(":")[0] in m for m in models)
        except Exception:
            logger.exception("Ollama health check failed")
            return False

    @property
    def provider_name(self) -> str:
        return "ollama"
