"""
LLM Abstraction Layer — طبقة تجريد نماذج اللغة.

المبدأ: الـAgent ومنطق العمل لا يعرفان أي LLM موجود.
يتعاملان فقط مع LLMProvider interface.
تغيير المزود = تغيير سطر واحد في .env (لا كود).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import jsonschema


@dataclass
class LLMMessage:
    role: str  # system | user | assistant | tool
    content: str


@dataclass
class ToolDefinition:
    """تعريف أداة واحدة بصيغة OpenAI function calling."""

    name: str
    description: str
    parameters: Dict[str, Any]

    def to_openai(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolCall:
    """استدعاء أداة من الـLLM."""

    call_id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class LLMResponse:
    """الاستجابة الموحدة من أي مزود."""

    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class LLMProvider(ABC):
    """
    الواجهة المجردة الوحيدة التي يعرفها بقية النظام عن أي LLM.
    كل مزود (Ollama/OpenAI/Gemini) يرث منها ويُنفذها.
    """

    @abstractmethod
    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """توليد نص عادي."""

    @abstractmethod
    async def generate_json(
        self,
        messages: List[LLMMessage],
        schema: Dict[str, Any],
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """
        توليد JSON منظّم مطابق لـ JSON Schema.
        يجب أن يتحقق المطابق من schema قبل الإرجاع،
        ويعيد المحاولة تلقائياً عند الفشل.
        """

    @abstractmethod
    async def generate_with_tools(
        self,
        messages: List[LLMMessage],
        tools: List[ToolDefinition],
        temperature: float = 0.2,
    ) -> LLMResponse:
        """توليد مع إمكانية استدعاء أدوات (tool calling)."""

    @abstractmethod
    async def health_check(self) -> bool:
        """فحص جاهزية المزود (الموديل محمّل ويتجاوب)."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """اسم المزود الحالي للـlogging."""


class LLMValidationError(Exception):
    """رُفعت عندما يفشل JSON عدة مرات في مطابقة الـschema."""

    def __init__(self, message: str, attempts: int):
        super().__init__(f"{message} (after {attempts} attempts)")
        self.attempts = attempts


def validate_against_schema(payload: Any, schema: Dict[str, Any]) -> bool:
    """تحقق صريح من JSON مقابل schema (نستخدمه في كل المزودين)."""
    try:
        jsonschema.validate(instance=payload, schema=schema)
        return True
    except (jsonschema.ValidationError, TypeError, ValueError):
        return False
