from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from src.conflict_detector.comparison.delta import DeltaDetails, compute_delta
from src.conflict_detector.comparison.matching import (
    FullMatchingResult,
    build_matching,
)
from src.conflict_detector.comparison.reconstruct import (
    ReconstructionResult,
    reconstruct_operations,
)
from src.conflict_detector.core.result import MergeAnalysisResult
from src.conflict_detector.detection.detector import (
    DetectionResult,
    detect_conflicts,
)
from src.conflict_detector.graph.schema_graph import SchemaGraph
from src.conflict_detector.rules.base import ConflictRule


@dataclass(frozen=True)
class BranchComputation:
    """
    Промежуточный результат анализа одной ветки относительно базовой схемы S0.
    """
    matching: FullMatchingResult
    delta_details: DeltaDetails
    reconstruction: ReconstructionResult


@dataclass(frozen=True)
class MergePipelineArtifacts:
    """
    Полный набор промежуточных артефактов pipeline.
    Полезно для отладки, тестов и будущих отчётов.
    """
    branch_a: BranchComputation
    branch_b: BranchComputation
    detection: DetectionResult
    result: MergeAnalysisResult


def analyze_branch(
    base_graph: SchemaGraph,
    branch_graph: SchemaGraph,
) -> BranchComputation:
    """
    Анализ одной ветки относительно базовой схемы.

    Шаги:
    1. matching(base, branch)
    2. delta(base, branch, matching)
    3. reconstruct(base, branch, matching, delta)
    """
    matching = build_matching(base_graph, branch_graph)
    delta_details = compute_delta(base_graph, branch_graph, matching)
    reconstruction = reconstruct_operations(
        left_graph=base_graph,
        right_graph=branch_graph,
        matching=matching,
        delta_details=delta_details,
    )

    return BranchComputation(
        matching=matching,
        delta_details=delta_details,
        reconstruction=reconstruction,
    )


def analyze_merge(
    base_graph: SchemaGraph,
    branch_a_graph: SchemaGraph,
    branch_b_graph: SchemaGraph,
    rules: Optional[Iterable[ConflictRule]] = None,
) -> MergeAnalysisResult:
    """
    Главная функция MVP-анализа трёхстороннего merge.

    Вход:
    - base_graph: S0
    - branch_a_graph: SA
    - branch_b_graph: SB

    Выход:
    - итоговый MergeAnalysisResult
    """
    branch_a = analyze_branch(base_graph, branch_a_graph)
    branch_b = analyze_branch(base_graph, branch_b_graph)

    detection = detect_conflicts(
        operations_a=branch_a.reconstruction.operations,
        operations_b=branch_b.reconstruction.operations,
        graph_a=branch_a_graph,
        graph_b=branch_b_graph,
        rules=rules,
    )

    return MergeAnalysisResult.build(
        operations_a=branch_a.reconstruction.operations,
        operations_b=branch_b.reconstruction.operations,
        conflicts=detection.conflicts,
    )


def analyze_merge_with_artifacts(
    base_graph: SchemaGraph,
    branch_a_graph: SchemaGraph,
    branch_b_graph: SchemaGraph,
    rules: Optional[Iterable[ConflictRule]] = None,
) -> MergePipelineArtifacts:
    """
    Расширенная версия analyze_merge:
    возвращает не только финальный результат,
    но и все промежуточные артефакты pipeline.
    """
    branch_a = analyze_branch(base_graph, branch_a_graph)
    branch_b = analyze_branch(base_graph, branch_b_graph)

    detection = detect_conflicts(
        operations_a=branch_a.reconstruction.operations,
        operations_b=branch_b.reconstruction.operations,
        graph_a=branch_a_graph,
        graph_b=branch_b_graph,
        rules=rules,
    )

    result = MergeAnalysisResult.build(
        operations_a=branch_a.reconstruction.operations,
        operations_b=branch_b.reconstruction.operations,
        conflicts=detection.conflicts,
    )

    return MergePipelineArtifacts(
        branch_a=branch_a,
        branch_b=branch_b,
        detection=detection,
        result=result,
    )
