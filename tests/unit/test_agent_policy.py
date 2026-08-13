"""
اختبارات Agent Policy وState — قواعد الانتقال الحتمية.
"""

import pytest

from app.agent.policy import AgentPolicy
from app.agent.state import AgentMemory, AgentState, VALID_TRANSITIONS


class TestTransitions:
    def test_valid_transitions_matrix(self):
        # IDLE لا يمكن أن يقفز إلى COMPLETED مباشرة
        assert AgentState.COMPLETED not in VALID_TRANSITIONS[AgentState.IDLE]
        # EXECUTING → RECOVERING صالح
        assert AgentState.RECOVERING in VALID_TRANSITIONS[AgentState.EXECUTING]
        # FAILED → IDLE (إعادة ضبط)
        assert AgentState.IDLE in VALID_TRANSITIONS[AgentState.FAILED]

    def test_memory_transition(self):
        mem = AgentMemory(task_id="t-1")
        assert mem.state == AgentState.IDLE
        mem.transition(AgentState.PLANNING)
        assert mem.state == AgentState.PLANNING

    def test_invalid_transition_raises(self):
        mem = AgentMemory(task_id="t-1")
        with pytest.raises(RuntimeError):
            mem.transition(AgentState.COMPLETED)


class TestPolicy:
    def setup_method(self):
        self.policy = AgentPolicy()

    def test_retry_when_attempts_left(self):
        action = self.policy.decide_on_step_failure(
            retries_remaining=2, step_index=0, plan_length=5, is_last_step=False
        )
        assert action.action == "retry"

    def test_fallback_on_non_final_step(self):
        action = self.policy.decide_on_step_failure(
            retries_remaining=0, step_index=0, plan_length=5, is_last_step=False
        )
        assert action.action == "fallback"

    def test_fail_on_final_step(self):
        action = self.policy.decide_on_step_failure(
            retries_remaining=0, step_index=4, plan_length=5, is_last_step=True
        )
        assert action.action == "fail"

    def test_build_plan_process_source(self):
        plan = self.policy.build_plan("process_source")
        tools = [s["tool"] for s in plan]
        assert "parse_source" in tools
        assert "extract_concepts" in tools
        assert "build_graph" in tools
        assert "topological_sort" in tools
        assert "generate_learning_path" in tools
        # التحقق من الترتيب المنطقي
        assert tools.index("extract_concepts") < tools.index("build_graph")
        assert tools.index("build_graph") < tools.index("topological_sort")
        assert tools.index("topological_sort") < tools.index("generate_learning_path")

    def test_build_plan_generate_path(self):
        plan = self.policy.build_plan("generate_path")
        tools = [s["tool"] for s in plan]
        assert "topological_sort" in tools
        assert "generate_learning_path" in tools
        assert "parse_source" not in tools

    def test_build_plan_unknown(self):
        assert self.policy.build_plan("unknown") == []

    def test_should_complete(self):
        assert self.policy.should_complete(
            {"concepts": [], "graph": {}}, ["concepts", "graph"]
        )
        assert not self.policy.should_complete(
            {"concepts": []}, ["concepts", "graph"]
        )
        assert not self.policy.should_complete(
            {"concepts": [], "graph": None}, ["concepts", "graph"]
        )
