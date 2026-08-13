"""
Cycle Detection — خوارزمية حتمية 100% (لا LLM).

اكتشاف الدورات في العلاقات ذات الاتجاه (خصوصاً prerequisite_of).
يُستخدم كخطوة تحقق إجبارية قبل توليد مسار التعلم:
مسار تعلم من رسم فيه دورة متطلبات = مستحيل منطقياً.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple


def detect_cycles(
    adjacency: Dict[str, List[str]]
) -> Tuple[bool, List[List[str]]]:
    """
    كشف كل الدورات باستخدام DFS بلون العقد (أبيض/رمادي/أسود).

    Args:
        adjacency: {node: [successors]}

    Returns:
        (has_cycle, list_of_cycles) حيث كل دورة قائمة معرفات مرتبة.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {n: WHITE for n in adjacency}
    cycles: List[List[str]] = []
    path: List[str] = []
    path_set: Set[str] = set()

    def dfs(node: str) -> None:
        color[node] = GRAY
        path.append(node)
        path_set.add(node)

        for successor in adjacency.get(node, []):
            if color.get(successor, WHITE) == GRAY and successor in path_set:
                # دورة: خذ الشريحة من أول ظهور للعقدة في المسار
                start = path.index(successor)
                cycle = path[start:] + [successor]
                # تجنّب تكرار نفس الدورة بمقارنات بسيطة
                canonical = _canonicalize(cycle)
                if canonical not in seen:
                    seen.add(canonical)
                    cycles.append(cycle)
            elif color.get(successor, WHITE) == WHITE:
                dfs(successor)

        path.pop()
        path_set.discard(node)
        color[node] = BLACK

    seen: Set[Tuple[str, ...]] = set()
    for node in adjacency:
        if color[node] == WHITE:
            dfs(node)

    return bool(cycles), cycles


def _canonicalize(cycle: List[str]) -> Tuple[str, ...]:
    """تمثيل معياري للدورة للتخلص من التكرار الدوراني."""
    core = cycle[:-1]
    if not core:
        return tuple()
    rotations = [tuple(core[i:] + core[:i]) for i in range(len(core))]
    return min(rotations)


def detect_cycles_bidirectional(
    edges: List[Tuple[str, str, str]],
    directed_types: List[str],
) -> Tuple[bool, List[List[str]]]:
    """
    بناء الرسم الموجه من قائمة الحواف (source, target, relation)
    حيث نوجه العلاقات المحددة (مثل prerequisite_of) فقط.
    """
    adjacency: Dict[str, List[str]] = {}
    for source, target, relation in edges:
        if relation in directed_types:
            adjacency.setdefault(source, [])
            adjacency.setdefault(target, [])
            adjacency[source].append(target)
    return detect_cycles(adjacency)
