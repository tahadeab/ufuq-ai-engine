"""
Ufuq MCP Server — مخدّم Model Context Protocol.

يوفّر أدوات منصة أُفق لأي Agent خارجي:
- search_ufuq_knowledge: بحث دلالي في معرفة المنصة
- get_learning_path: جلب مسار تعلم لمصدر
- get_concept: جلب مفهوم مع تعريفه وعلاقاته
- recommend_course: توصية مفاهيم مرتبطة بمفهوم

التشغيل: المصدّر streamable-http عبر FastAPI mount في main.py.
تخويل الاستدعاءات من خارج الشبكة عبر إعدادات منفصلة مستقبلاً.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def build_mcp_tools() -> List[Dict[str, Any]]:
    """تعريف أدوات MCP (JSON Schema لكل أداة)."""
    return [
        {
            "name": "search_ufuq_knowledge",
            "description": "بحث دلالي (hybrid RAG) في معرفة المنصة: مفاهيم ومقاطع مع citations",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "سؤال المستخدم بالعربية"},
                    "source_id": {"type": "string", "description": "معرف المصدر (اختياري)"},
                    "top_k": {"type": "integer", "default": 5},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        {
            "name": "get_learning_path",
            "description": "جلب مسار التعلم الكامل لمصدر (وحدات + أهداف + ساعات تقديرية)",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string", "description": "معرف المصدر"},
                },
                "required": ["source_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "get_concept",
            "description": "جلب مفهوم مع تعريفه وعلاقاته في الرسم المعرفي",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string", "description": "معرف المصدر"},
                    "concept_name": {"type": "string", "description": "اسم المفهوم"},
                },
                "required": ["source_id", "concept_name"],
                "additionalProperties": False,
            },
        },
        {
            "name": "recommend_course",
            "description": "توصية بمفاهيم ومصادر مرتبطة تسلسلياً بمفهوم معطى",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string", "description": "معرف المصدر"},
                    "concept_name": {"type": "string", "description": "اسم المفهوم الحالي"},
                    "max_recommendations": {"type": "integer", "default": 5},
                },
                "required": ["source_id", "concept_name"],
                "additionalProperties": False,
            },
        },
    ]


class UfuqMCPServer:
    """منفذ MCP مبسط فوق FastAPI — قابل للترقية إلى MCP SDK الرسمي."""

    def __init__(self, api_client: Optional[Any] = None):
        self.api_client = api_client
        self.tools = build_mcp_tools()

    def get_tool_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        for tool in self.tools:
            if tool["name"] == name:
                return tool
        return None

    async def handle_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """تنفيذ استدعاء أداة MCP عبر API الداخلي."""
        tool = self.get_tool_by_name(tool_name)
        if tool is None:
            return {"error": f"أداة غير موجودة: {tool_name}"}

        errors = _validate_arguments(arguments, tool["parameters"])
        if errors:
            return {"error": f"مدخلات غير صالحة: {'; '.join(errors)}"}

        try:
            if tool_name == "search_ufuq_knowledge":
                return await self._search(arguments)
            if tool_name == "get_learning_path":
                return await self._get_path(arguments)
            if tool_name == "get_concept":
                return await self._get_concept(arguments)
            if tool_name == "recommend_course":
                return await self._recommend(arguments)
            return {"error": "أداة غير معرّفة داخلياً"}
        except Exception as exc:
            logger.exception("فشل استدعاء MCP %s", tool_name)
            return {"error": str(exc)}

    async def _search(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_client:
            return {"error": "API client غير مهيّأ"}
        return await self.api_client.hybrid_search(
            source_id=arguments.get("source_id"),
            query=arguments["query"],
            top_k=arguments.get("top_k", 5),
        )

    async def _get_path(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_client:
            return {"error": "API client غير مهيّأ"}
        return await self.api_client.get_learning_path(source_id=arguments["source_id"])

    async def _get_concept(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_client:
            return {"error": "API client غير مهيّأ"}
        return await self.api_client.get_concept(
            source_id=arguments["source_id"],
            concept_name=arguments["concept_name"],
        )

    async def _recommend(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_client:
            return {"error": "API client غير مهيّأ"}
        return await self.api_client.recommend_course(
            source_id=arguments["source_id"],
            concept_name=arguments["concept_name"],
            max_recommendations=arguments.get("max_recommendations", 5),
        )


def _validate_arguments(arguments: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    for req in schema.get("required", []):
        if req not in arguments:
            errors.append(f"مطلوب: {req}")
    return errors
