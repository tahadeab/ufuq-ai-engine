"""
Agent Policy — قواعد الانتقال والاسترداد.

المبدأ: السياسة حتمية (لا LLM فيها). قرارات متى نعتمد إعادة محاولة
ومتى نسترد بمسار بديل قواعد صريحة قابلة للاختبار.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.agent.state import AgentState

logger = logging.getLogger(__name__)


@dataclass
class RecoveryAction:
    action: str           # retry | fallback | fail
    message: str


class AgentPolicy:
    """قرارات انتقالية صرفة (pure functions قابلة للاختبار)."""

    @staticmethod
    def decide_on_step_failure(
        retries_remaining: int, step_index: int, plan_length: int, is_last_step: bool
    ) -> RecoveryAction:
        """
        قاعدة:
        - خطوة غير أخيرة + retries > 0 → retry (تبقى في EXECUTING)
        - خطوة غير أخيرة + retries = 0 → fallback (RECOVERING ثم تجربة بديل)
        - خطوة أخيرة + retries > 0 → retry
        - خطوة أخيرة + retries = 0 → fail حاسم
        """
        if retries_remaining > 0:
            return RecoveryAction("retry", "إعادة محاولة تنفيذ الخطوة")
        if not is_last_step:
            return RecoveryAction(
                "fallback", "استنفدت المحاولات — تجربة مسار بديل"
            )
        return RecoveryAction("fail", "فشل حاسم في خطوة أخيرة — المهمة فشلت")

    @staticmethod
    def should_complete(result: dict, required_fields: list) -> bool:
        """الانتقال إلى COMPLETED يتطلب حقول النتيجة الأساسية."""
        missing = [f for f in required_fields if f not in result or result[f] is None]
        return len(missing) == 0

    @staticmethod
    def build_plan(task_type: str) -> list:
        """بناء الخطة الافتراضية حسب نوع المهمة."""
        if task_type == "process_source":
            return [
                {"tool": "parse_source", "description": "تخليط المستند واستخراج البنية"},
                {"tool": "get_chunks", "description": "الحصول على المقاطع الدلالية"},
                {"tool": "extract_concepts", "description": "استخراج المفاهيم عبر LLM"},
                {"tool": "extract_relationships", "description": "استخراج العلاقات"},
                {"tool": "build_graph", "description": "بناء الرسم المعرفي والتحقق"},
                {"tool": "topological_sort", "description": "الترتيب الطوبولوجي الحتمي"},
                {"tool": "generate_learning_path", "description": "توليد مسار التعلم"},
                {"tool": "generate_lesson", "description": "توليد الدروس"},
                {"tool": "generate_assessment", "description": "توليد الاختبارات"},
            ]
        if task_type == "generate_path":
            return [
                {"tool": "get_chunks", "description": "الحصول على المقاطع"},
                {"tool": "build_graph", "description": "إعادة بناء الرسم من الذاكرة"},
                {"tool": "topological_sort", "description": "الترتيب الطوبولوجي"},
                {"tool": "generate_learning_path", "description": "توليد مسار التعلم"},
            ]
        return []
