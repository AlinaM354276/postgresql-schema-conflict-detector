from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.conflict_detector.detection.detector import InterferencePair


def _short_op(op) -> str:
    if hasattr(op, "operation_type"):
        t = op.operation_type.value
    else:
        t = type(op).__name__

    if hasattr(op, "target") and op.target:
        return f"{t}({op.target})"

    if hasattr(op, "source"):
        return f"{t}({op.source}->{op.target})"

    return t


def _simplify_impact(obj: str) -> str:
    if "->" in obj:
        return obj.split("->")[1]
    return obj


def build_dot(pairs: Iterable[InterferencePair]) -> str:
    lines = [
        "digraph ConflictGraph {",
        '  graph [rankdir=LR, labelloc="t", label="Interference graph (conflicts)"];',
        '  node [shape=box, style="rounded"];',
    ]

    for i, pair in enumerate(pairs):
        a_id = f"A{i}"
        b_id = f"B{i}"

        a_label = _short_op(pair.operation_a)
        b_label = _short_op(pair.operation_b)

        lines.append(f'"{a_id}" [label="{a_label}", color="blue"];')
        lines.append(f'"{b_id}" [label="{b_label}", color="red"];')

        shared = sorted({_simplify_impact(x) for x in pair.shared_impact})

        shared_label = "\\n".join(shared[:5])
        if len(shared) > 5:
            shared_label += "\\n..."

        lines.append(f'"{a_id}" -> "{b_id}" [label="{shared_label}"];')

    if not list(pairs):
        lines.append('"none" [label="No conflicts", color="gray"];')

    lines.append("}")
    return "\n".join(lines)


def save_conflict_graph_dot(pairs: Iterable[InterferencePair], path: str | Path):
    dot = build_dot(pairs)
    Path(path).write_text(dot, encoding="utf-8")
