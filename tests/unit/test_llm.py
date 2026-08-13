"""
اختبارات طبقة LLM — factory والتبديل بين المزودين دون نماذج حقيقية.
"""

import pytest

from app.llm.base import (
    LLMProvider,
    LLMMessage,
    LLMResponse,
    ToolDefinition,
    validate_against_schema,
)
from app.llm.factory import get_llm


class MockProvider(LLMProvider):
    """مزود وهمي للاختبار — لا يتصل بأي خدمة."""

    @property
    def provider_name(self) -> str:
        return "mock"

    async def generate(self, messages, temperature=0.4, max_tokens=4096):
        return LLMResponse(content="رد وهمي", finish_reason="stop")

    async def generate_json(self, messages, schema=None, temperature=0.1):
        payload = {"test": True, "concepts": [], "relationships": []}
        if schema:
            ok = validate_against_schema(payload, schema)
            if not ok:
                # اسقط الحقول الزائدة لتطابق الـschema (سلوك المزود الحقيقي)
                payload = {"test": True}
        return payload

    async def generate_with_tools(self, messages, tools, temperature=0.2):
        return LLMResponse(content="", tool_calls=[], finish_reason="stop")

    async def health_check(self) -> bool:
        return True


class TestBaseInterface:
    @pytest.mark.asyncio
    async def test_mock_provider_generate(self):
        mock = MockProvider()
        result = await mock.generate([LLMMessage(role="user", content="س")])
        assert isinstance(result, LLMResponse)
        assert result.content == "رد وهمي"

    @pytest.mark.asyncio
    async def test_mock_provider_json(self):
        mock = MockProvider()
        result = await mock.generate_json(
            [LLMMessage(role="user", content="س")],
            schema={
                "type": "object",
                "properties": {"test": {"type": "boolean"}},
                "required": ["test"],
                "additionalProperties": False,
            },
        )
        assert result["test"] is True

    @pytest.mark.asyncio
    async def test_health_check(self):
        mock = MockProvider()
        assert await mock.health_check()


class TestToolDefinition:
    def test_to_openai(self):
        tool = ToolDefinition(
            name="search",
            description="بحث",
            parameters={
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": ["q"],
            },
        )
        spec = tool.to_openai()
        assert spec["type"] == "function"
        assert spec["function"]["name"] == "search"


class TestLLMResponse:
    def test_has_tool_calls(self):
        assert not LLMResponse(content="نص").has_tool_calls
        from app.llm.base import ToolCall

        resp = LLMResponse(tool_calls=[ToolCall(call_id="1", name="t", arguments={})])
        assert resp.has_tool_calls


class TestSchemaValidation:
    def test_valid(self):
        assert validate_against_schema(
            {"name": "ت"}, {"type": "object", "properties": {"name": {"type": "string"}}}
        )

    def test_invalid(self):
        assert not validate_against_schema(
            {"name": 5}, {"type": "object", "properties": {"name": {"type": "string"}}}
        )


class TestFactory:
    def test_get_llm_returns_provider(self):
        llm = get_llm()
        assert isinstance(llm, LLMProvider)
