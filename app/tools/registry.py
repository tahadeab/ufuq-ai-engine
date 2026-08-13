"""
Tool Registry — سجل الأدوات الموحد.

المبدأ: الـAgent يرى الأدوات عبر ToolRegistry فقط.
كل أداة: اسم + مدخلات JSON Schema + تنفيذ + تحقق من المدخلات.
التسجيل هنا يجعل إضافة/إزالة أداة عملية configuration وليست تعديلاً في orchestrator.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from app.llm.base import ToolDefinition

logger = logging.getLogger(__name__)


@dataclass
class RegisteredTool:
    name: str
    description: str
    parameters: Dict[str, Any]          # JSON Schema للمدخلات
    handler: Callable
    category: str = "general"           # document | rag | knowledge | learning


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, RegisteredTool] = {}

    def register(self, tool: RegisteredTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"أداة مسجلة مسبقاً: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> RegisteredTool:
        if name not in self._tools:
            raise KeyError(f"أداة غير معروفة: {name}")
        return self._tools[name]

    def list_tools(self) -> List[str]:
        return sorted(self._tools)

    def tools_as_definitions(self) -> List[ToolDefinition]:
        return [
            ToolDefinition(
                name=t.name, description=t.description, parameters=t.parameters
            )
            for t in self._tools.values()
        ]

    async def execute(self, name: str, arguments: Dict[str, Any]) -> Any:
        tool = self.get(name)
        errors = _validate_arguments(arguments, tool.parameters)
        if errors:
            return {"error": f"مدخلات غير صالحة للأداة {name}: {'; '.join(errors)}"}
        try:
            result = await tool.handler(**arguments)
            return result if isinstance(result, dict) else {"result": result}
        except Exception as exc:
            logger.exception("فشل تنفيذ الأداة %s", name)
            return {"error": f"{type(exc).__name__}: {exc}"}


def _validate_arguments(arguments: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    """تحقق بسيط من المدخلات المطلوبة قبل تنفيذ الأداة."""
    errors: List[str] = []
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    for req in required:
        if req not in arguments or arguments[req] is None:
            errors.append(f"مطلوب: {req}")
    for key, value in arguments.items():
        prop = properties.get(key)
        if prop is None:
            errors.append(f"خاصية غير معروفة: {key}")
            continue
        if prop.get("type") == "integer" and not isinstance(value, int):
            errors.append(f"{key} يجب أن يكون عدداً صحيحاً")
        elif prop.get("type") == "number" and not isinstance(value, (int, float)):
            errors.append(f"{key} يجب أن يكون رقماً")
    return errors


_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
