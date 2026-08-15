"""
OpenAIProvider — المزود السحابي (المستقبل المدفوع).

نفس الواجهة تماماً؛ التبديل يتم من .env فقط.
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


class OpenAIProvider(LLMProvider):
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.openai_api_key or ""
        self.base_url = settings.openai_base_url or "https://api.openai.com/v1"
        self.model = settings.openai_model

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

        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                json=payload,
                headers=headers,
            )
            if resp.is_error:
                try:
                    detail: Any = resp.json()
                except ValueError:
                    detail = resp.text[:2000]
                logger.error(
                    "LLM request failed status=%s model=%s endpoint=%s detail=%s",
                    resp.status_code,
                    self.model,
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    detail,
                )
                resp.raise_for_status()
            return resp.json()

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
        last_error = None
        attempts = 0
        while attempts < 3:
            attempts += 1
            data = await self._chat_completion(
                messages,
                temperature=temperature,
                extra_body={
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "structured_output",
                            "strict": True,
                            "schema": schema,
                        },
                    }
                },
            )
            raw_content = data["choices"][0].get("message", {}).get("content", "{}")
            try:
                payload = json.loads(raw_content)
            except json.JSONDecodeError as exc:
                last_error = f"invalid JSON: {exc}"
                continue
            if validate_against_schema(payload, schema):
                return payload
            last_error = "schema validation failed"
            messages = messages + [
                LLMMessage(
                    role="user",
                    content="المخرجات لم تطابق المخطط. أعد إنتاج JSON مطابق للمخطط بدقة.",
                )
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
            tool_calls.append(
                ToolCall(call_id=tc.get("id", ""), name=fn.get("name", ""), arguments=args)
            )
        return LLMResponse(
            content=msg.get("content", ""),
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason"),
            raw=data,
        )

    async def health_check(self) -> bool:
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{self.base_url.rstrip('/')}/models", headers=headers
                )
                return resp.status_code == 200
        except Exception:
            return False

    @property
    def provider_name(self) -> str:
        return "openai"
