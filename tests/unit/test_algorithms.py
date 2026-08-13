"""
اختبارات الخوارزميات الحتمية — Cycle Detection + Topological Sort.

هذه الخوارزميات حاسمة لسلامة مسار التعلم ولا تُفوَّض للـLLM،
لذلك تُختبر بدقة شاملة على حالات متطرفة.
"""

import pytest

from app.algorithms.cycle_detection import detect_cycles
from app.algorithms.topological_sort import (
    topological_levels,
    topological_sort_kahn,
    validate_topological_order,
)


# ── Cycle Detection ───────────────────────────────────────

class TestCycleDetection:
    def test_no_cycle(self):
        adj = {"a": ["b"], "b": ["c"], "c": []}
        has_cycle, cycles = detect_cycles(adj)
        assert not has_cycle
        assert cycles == []

    def test_simple_cycle(self):
        adj = {"a": ["b"], "b": ["c"], "c": ["a"]}
        has_cycle, cycles = detect_cycles(adj)
        assert has_cycle
        assert len(cycles) == 1
        assert set(cycles[0][:-1]) == {"a", "b", "c"}

    def test_self_loop(self):
        adj = {"a": ["a"]}
        has_cycle, cycles = detect_cycles(adj)
        assert has_cycle
        assert cycles[0] == ["a", "a"]

    def test_multiple_cycles(self):
        adj = {
            "a": ["b"], "b": ["a"],          # دورة 1
            "c": ["d"], "d": ["e"], "e": ["c"],  # دورة 2
            "f": [],
        }
        has_cycle, cycles = detect_cycles(adj)
        assert has_cycle
        assert len(cycles) == 2

    def test_disconnected_graph_no_cycle(self):
        adj = {"a": ["b"], "b": [], "c": ["d"], "d": []}
        has_cycle, cycles = detect_cycles(adj)
        assert not has_cycle

    def test_empty_graph(self):
        has_cycle, cycles = detect_cycles({})
        assert not has_cycle

    def test_diamond_no_cycle(self):
        adj = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}
        has_cycle, cycles = detect_cycles(adj)
        assert not has_cycle

    def test_shared_node_two_cycles(self):
        adj = {"a": ["b"], "b": ["a", "c"], "c": ["b"]}
        has_cycle, cycles = detect_cycles(adj)
        assert has_cycle
        assert len(cycles) == 2

    def test_no_false_positive_long_path(self):
        nodes = [f"n{i}" for i in range(100)]
        adj = {n: [nodes[i + 1]] if i < 99 else [] for i, n in enumerate(nodes)}
        has_cycle, cycles = detect_cycles(adj)
        assert not has_cycle


# ── Topological Sort (Kahn) ───────────────────────────────

class TestTopologicalSort:
    def test_basic_order(self):
        adj = {"a": ["b"], "b": ["c"], "c": []}
        order, acyclic = topological_sort_kahn(["a", "b", "c"], adj)
        assert acyclic
        assert order.index("a") < order.index("b") < order.index("c")

    def test_diamond(self):
        adj = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}
        order, acyclic = topological_sort_kahn(["a", "b", "c", "d"], adj)
        assert acyclic
        assert order[0] == "a"
        assert order[-1] == "d"

    def test_cycle_detected(self):
        adj = {"a": ["b"], "b": ["a"]}
        order, acyclic = topological_sort_kahn(["a", "b"], adj)
        assert not acyclic

    def test_all_roots_order_undefined(self):
        adj = {"a": [], "b": [], "c": []}
        order, acyclic = topological_sort_kahn(["a", "b", "c"], adj)
        assert acyclic
        assert set(order) == {"a", "b", "c"}

    def test_validate_order_correct(self):
        adj = {"a": ["b", "c"], "b": ["d"], "c": ["d"], "d": []}
        assert validate_topological_order(["a", "b", "c", "d"], adj)
        assert validate_topological_order(["a", "c", "b", "d"], adj)
        assert not validate_topological_order(["b", "a", "c", "d"], adj)
        assert not validate_topological_order(["d", "a", "b", "c"], adj)

    def test_levels(self):
        adj = {"a": ["b"], "b": ["c"], "c": ["d"], "d": []}
        levels = topological_levels(["a", "b", "c", "d"], adj)
        assert levels["a"] == 0
        assert levels["b"] == 1
        assert levels["c"] == 2
        assert levels["d"] == 3

    def test_levels_parallel(self):
        adj = {"root": ["a", "b"], "a": [], "b": []}
        levels = topological_levels(["root", "a", "b"], adj)
        assert levels["root"] == 0
        assert levels["a"] == 1
        assert levels["b"] == 1

    def test_empty(self):
        order, acyclic = topological_sort_kahn([], {})
        assert acyclic
        assert order == []
