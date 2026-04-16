from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Set, Tuple

from src.conflict_detector.core.models import Conflict, Operation
from src.conflict_detector.graph.schema_graph import SchemaGraph
from src.conflict_detector.rules.base import ConflictRule, RuleContext
from src.conflict_detector.rules.basic_rules import BASIC_RULES


@dataclass(frozen=True)
class DetectionResult:
    conflicts: Tuple[Conflict, ...]

    def __iter__(self):
        return iter(self.conflicts)

    def __len__(self) -> int:
        return len(self.conflicts)

    def is_empty(self) -> bool:
        return len(self.conflicts) == 0


def conflict_key(conflict: Conflict) -> Tuple[str, Tuple[str, ...], str]:
    """
    Ключ для дедупликации конфликтов.

    Используем:
    - rule_id
    - object_ids
    - message

    Пока этого достаточно для MVP.
    """
    return (
        conflict.rule_id,
        tuple(sorted(conflict.object_ids)),
        conflict.message,
    )


def detect_conflicts(
    operations_a: Iterable[Operation],
    operations_b: Iterable[Operation],
    graph_a: SchemaGraph,
    graph_b: SchemaGraph,
    rules: Iterable[ConflictRule] | None = None,
) -> DetectionResult:
    """
    Главная функция обнаружения конфликтов.

    Алгоритм MVP:
    1. перебираем все пары операций из двух веток
    2. применяем все правила
    3. собираем найденные конфликты
    4. убираем дубли
    """
    active_rules = list(rules) if rules is not None else list(BASIC_RULES)

    ops_a = list(operations_a)
    ops_b = list(operations_b)

    found_conflicts: List[Conflict] = []
    seen: Set[Tuple[str, Tuple[str, ...], str]] = set()

    for op_a in ops_a:
        for op_b in ops_b:
            context = RuleContext(
                operation_a=op_a,
                operation_b=op_b,
                graph_a=graph_a,
                graph_b=graph_b,
            )

            for rule in active_rules:
                result = rule.check(context)
                if not result.matched or result.conflict is None:
                    continue

                key = conflict_key(result.conflict)
                if key in seen:
                    continue

                seen.add(key)
                found_conflicts.append(result.conflict)

    return DetectionResult(conflicts=tuple(found_conflicts))
