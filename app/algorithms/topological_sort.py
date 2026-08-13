"""
Topological Sort — خوارزمية Kahn الحتمية.

ترتيب خطي للمفاهيم بحيث تأتي كل المتطلبات السابقة قبل المفهوم المعتمد.
هذا الترتيب هو **العمود الفقري** لتوليد وحدات مسار التعلم:
الوحدة رقم i تغطي مفاهيم ترتيبها الطوبولوجي في الشريحة i.

المبدأ من وثيقة المشروع: هذا ضمان حتمي من الخوارزمية،
لا من LLM. أي ترتيب يأتي من LLM يُتحقق منه هنا.
"""

from __future__ import annotations

from collections import deque
from typing import Dict, List, Set, Tuple


def topological_sort_kahn(
    nodes: List[str], adjacency: Dict[str, List[str]]
) -> Tuple[List[str], bool]:
    """
    Kahn's Algorithm:
    1. احسب الدرجة الداخلة لكل عقدة.
    2. ابدأ بالعقد ذات الدرجة 0 (لا متطلبات سابقة).
    3. عند "إزالة" عقدة، قلّل درجة جيرانها؛ أضف من وصلت درجته لـ0.
    4. إذا بقت عقد غير معالجة → الرسم فيه دورة.

    Args:
        nodes: كل معرفات العقد
        adjacency: {node: [successors]}

    Returns:
        (ordered_list, is_acyclic)
    """
    in_degree: Dict[str, int] = {n: 0 for n in nodes}
    for node in nodes:
        for succ in adjacency.get(node, []):
            if succ in in_degree:
                in_degree[succ] += 1

    queue: deque = deque(sorted(n for n, d in in_degree.items() if d == 0))
    order: List[str] = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for succ in sorted(adjacency.get(node, [])):
            if succ not in in_degree:
                continue
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                queue.append(succ)

    is_acyclic = len(order) == len(nodes)
    return order, is_acyclic


def topological_levels(
    nodes: List[str], adjacency: Dict[str, List[str]]
) -> Dict[str, int]:
    """
    مستوى كل عقدة = طول أطول مسار من عقدة جذرية إليها.
    مفيد لتجميع المفاهيم في وحدات: نفس المستوى = نفس الوحدة تقريباً.
    """
    in_degree: Dict[str, int] = {n: 0 for n in nodes}
    for node in nodes:
        for succ in adjacency.get(node, []):
            if succ in in_degree:
                in_degree[succ] += 1

    level: Dict[str, int] = {}
    queue: deque = deque(sorted(n for n, d in in_degree.items() if d == 0))
    for n in queue:
        level[n] = 0

    while queue:
        node = queue.popleft()
        for succ in sorted(adjacency.get(node, [])):
            if succ not in in_degree:
                continue
            level[succ] = max(level.get(succ, 0), level[node] + 1)
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                queue.append(succ)

    # عقد في دورة تأخذ مستوى منفصل
    max_level = max(level.values()) if level else 0
    for n in nodes:
        if n not in level:
            level[n] = max_level + 1
    return level


def validate_topological_order(
    order: List[str], adjacency: Dict[str, List[str]]
) -> bool:
    """تحقق حتمي: كل عقدة تأتي بعد كل متطلباتها السابقة في الترتيب."""
    seen: Set[str] = set()
    for node in order:
        # المتطلبات السابقة لـ node = العقد التي node تابع لها
        for predecessor, successors in adjacency.items():
            if node in successors and predecessor not in seen:
                return False
        seen.add(node)
    return True
