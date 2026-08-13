"""
GeminiProvider — المزود السحابي الثاني.

مفيد خصوصاً للـPDF المعقد بصرياً (جداول + مخططات + صور) عبر
Gemini Document Understanding / Files API.
تحوّل واجهة Gemini إلى الواجهة الموحدة LLMProvider.
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

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(LLMProvider):
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.gemini_api_key or ""
        self.model = settings.gemini_model

    def _url(self, method: str = "generateContent") -> str:
        return f"{GEMINI_API_BASE}/{self.model}:{method}?key={self.api_key}"

    async def _call(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.4,
        max_tokens: int = 4096,
        response_mime_type: Optional[str] = None,
        response_schema: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        contents = [
            {
                "role": "user" if m.role in ("user", "tool") else "model",
                "parts": [{"text": m.content}],
            }
            for m in messages
        ]
        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        gen_cfg = payload["generationConfig"]
        if response_mime_type:
            gen_cfg["responseMimeType"] = response_mime_type
        if response_schema:
            gen_cfg["responseSchema"] = response_schema
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(self._url(), json=payload)
            resp.raise_for_status()
            return resp.json()

    def _extract_text(self, data: Dict[str, Any]) -> str:
        try:
            return data["candidates"][0]["content"]["parts"][0].get("text", "")
        except (KeyError, IndexError):
            return ""

    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        data = await self._call(messages, temperature, max_tokens)
        text = self._extract_text(data)
        finish = None
        try:
            finish = data["candidates"][0].get("finishReason")
        except (KeyError, IndexError):
            pass
        return LLMResponse(content=text, finish_reason=finish, raw=data)

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
            data = await self._call(
                messages,
                temperature=temperature,
                response_mime_type="application/json",
                response_schema=schema,
            )
            text = self._extract_text(data)
            try:
                payload = json.loads(text) if text else {}
            except json.JSONDecodeError as exc:
                last_error = f"invalid JSON: {exc}"
                continue
            if validate_against_schema(payload, schema):
                return payload
            last_error = "schema validation failed"
            messages = messages + [
                LLMMessage(
                    role="user",
                    content="المخرجات لم تطابق المخطط. أعد إنتاج JSON مطابق.",
                )
            ]
        raise LLMValidationError(last_error or "unknown", attempts)

    async def generate_with_tools(
        self,
        messages: List[LLMMessage],
        tools: List[ToolDefinition],
        temperature: float = 0.2,
    ) -> LLMResponse:
        gemini_tools = [
            {
                "function_declarations": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    }
                    for t in tools
                ]
            }
        ]
        data = await self._call(messages, temperature, tools=gemini_tools)
        text = self._extract_text(data)
        tool_calls: List[ToolCall] = []
        try:
            parts = data["candidates"][0]["content"]["parts"]
            for i, part in enumerate(parts):
                if "functionCall" in part:
                    fc = part["functionCall"]
                    tool_calls.append(
                        ToolCall(
                            call_id=f"gemini-{i}",
                            name=fc.get("name", ""),
                            arguments=fc.get("args", {}),
                        )
                    )
        except (KeyError, IndexError):
            pass
        return LLMResponse(
            content=text, tool_calls=tool_calls,
            finish_reason=data.get("candidates", [{}])[0].get("finishReason"),
            raw=data,
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{GEMINI_API_BASE}/{self.model}?key={self.api_key}"
                )
                return resp.status_code == 200
        except Exception:
            return False

    @property
    def provider_name(self) -> str:
        return "gemini"
