from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol, runtime_checkable

from src.conflict_detector.core.models import Conflict, Operation
from src.conflict_detector.graph.schema_graph import SchemaGraph


@dataclass(frozen=True)
class RuleContext:
    """
    Контекст проверки правила.

    Пока MVP-контекст минимален:
    - две операции
    - граф ветки A
    - граф ветки B

    Позже сюда можно добавить:
    - базовый граф S0
    - matching
    - delta
    - метаданные merge-сценария
    """
    operation_a: Operation
    operation_b: Operation
    graph_a: SchemaGraph
    graph_b: SchemaGraph


@dataclass(frozen=True)
class RuleCheckResult:
    """
    Результат срабатывания правила.

    Для MVP достаточно:
    - сработало ли правило
    - сам Conflict, если он найден

    Это чуть более явно, чем просто Conflict | None,
    и облегчает последующее расширение.
    """
    matched: bool
    conflict: Optional[Conflict] = None

    @classmethod
    def no_match(cls) -> "RuleCheckResult":
        return cls(matched=False, conflict=None)

    @classmethod
    def from_conflict(cls, conflict: Conflict) -> "RuleCheckResult":
        return cls(matched=True, conflict=conflict)


@runtime_checkable
class ConflictRule(Protocol):
    """
    Протокол правила обнаружения конфликта.

    Любое правило должно:
    - иметь стабильный rule_id
    - уметь проверять пару операций
    """
    rule_id: str

    def check(self, context: RuleContext) -> RuleCheckResult:
        ...


@dataclass(frozen=True)
class BaseConflictRule:
    """
    Базовая реализация правила.

    Удобна как родительский класс для concrete rules.
    """
    rule_id: str
    description: str = ""

    def check(self, context: RuleContext) -> RuleCheckResult:
        raise NotImplementedError("Rule must implement check(context)")


def same_target(operation_a: Operation, operation_b: Operation) -> bool:
    """
    Базовая эвристика: операции направлены на один и тот же target.
    """
    target_a = getattr(operation_a, "target", None)
    target_b = getattr(operation_b, "target", None)
    return target_a is not None and target_a == target_b


def make_metadata(**kwargs: Any) -> Dict[str, Any]:
    """
    Удобный helper для будущего формирования metadata конфликта.
    В base-слое возвращаем обычный dict; freeze произойдёт в месте создания Conflict.
    """
    return kwargs
