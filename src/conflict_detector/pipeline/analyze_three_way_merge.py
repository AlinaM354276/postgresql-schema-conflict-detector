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
from src.conflict_detector.core.result import ThreeWayMergeAnalysisResult
from src.conflict_detector.detection.detector import (
    DetectionResult,
    detect_conflicts,
)
from src.conflict_detector.graph.schema_graph import SchemaGraph
from src.conflict_detector.merge.three_way_merge import (
    MergeAttemptResult,
    build_merge_candidate,
)
from src.conflict_detector.rules.base import ConflictRule


@dataclass(frozen=True)
class BranchThreeWayComputation:
    matching: FullMatchingResult
    delta_details: DeltaDetails
    reconstruction: ReconstructionResult


@dataclass(frozen=True)
class ThreeWayMergeArtifacts:
    branch_a: BranchThreeWayComputation
    branch_b: BranchThreeWayComputation
    detection: DetectionResult
    merge_attempt: MergeAttemptResult
    result: ThreeWayMergeAnalysisResult


def analyze_branch_against_base(
    base_graph: SchemaGraph,
    branch_graph: SchemaGraph,
) -> BranchThreeWayComputation:
    matching = build_matching(base_graph, branch_graph)
    delta_details = compute_delta(base_graph, branch_graph, matching)
    reconstruction = reconstruct_operations(
        left_graph=base_graph,
        right_graph=branch_graph,
        matching=matching,
        delta_details=delta_details,
    )

    return BranchThreeWayComputation(
        matching=matching,
        delta_details=delta_details,
        reconstruction=reconstruction,
    )


def analyze_three_way_merge(
    base_graph: SchemaGraph,
    branch_a_graph: SchemaGraph,
    branch_b_graph: SchemaGraph,
    rules: Optional[Iterable[ConflictRule]] = None,
) -> ThreeWayMergeAnalysisResult:
    branch_a = analyze_branch_against_base(base_graph, branch_a_graph)
    branch_b = analyze_branch_against_base(base_graph, branch_b_graph)

    detection = detect_conflicts(
        operations_a=branch_a.reconstruction.operations,
        operations_b=branch_b.reconstruction.operations,
        graph_a=branch_a_graph,
        graph_b=branch_b_graph,
        rules=rules,
    )

    merge_attempt = build_merge_candidate(
        base_graph=base_graph,
        operations_a=tuple(branch_a.reconstruction.operations),
        operations_b=tuple(branch_b.reconstruction.operations),
    )

    return ThreeWayMergeAnalysisResult.build(
        operations_a=branch_a.reconstruction.operations,
        operations_b=branch_b.reconstruction.operations,
        rule_conflicts=detection.conflicts,
        merge_attempt=merge_attempt,
        interference_pairs=detection.interference_pairs,
    )


def analyze_three_way_merge_with_artifacts(
    base_graph: SchemaGraph,
    branch_a_graph: SchemaGraph,
    branch_b_graph: SchemaGraph,
    rules: Optional[Iterable[ConflictRule]] = None,
) -> ThreeWayMergeArtifacts:
    branch_a = analyze_branch_against_base(base_graph, branch_a_graph)
    branch_b = analyze_branch_against_base(base_graph, branch_b_graph)

    detection = detect_conflicts(
        operations_a=branch_a.reconstruction.operations,
        operations_b=branch_b.reconstruction.operations,
        graph_a=branch_a_graph,
        graph_b=branch_b_graph,
        rules=rules,
    )

    merge_attempt = build_merge_candidate(
        base_graph=base_graph,
        operations_a=tuple(branch_a.reconstruction.operations),
        operations_b=tuple(branch_b.reconstruction.operations),
    )

    result = ThreeWayMergeAnalysisResult.build(
        operations_a=branch_a.reconstruction.operations,
        operations_b=branch_b.reconstruction.operations,
        rule_conflicts=detection.conflicts,
        merge_attempt=merge_attempt,
        interference_pairs=detection.interference_pairs,
    )

    return ThreeWayMergeArtifacts(
        branch_a=branch_a,
        branch_b=branch_b,
        detection=detection,
        merge_attempt=merge_attempt,
        result=result,
    )
