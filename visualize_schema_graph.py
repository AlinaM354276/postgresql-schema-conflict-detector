from pathlib import Path

from src.conflict_detector.parser.ddl_parser import parse_ddl_to_graph


def escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def graph_to_dot(graph, title: str = "SchemaGraph") -> str:
    lines = [
        "digraph SchemaGraph {",
        '  graph [rankdir=LR, label="' + escape(title) + '", labelloc=t];',
        '  node [shape=box, style="rounded"];',
        '  edge [fontsize=10];',
        "",
    ]

    for object_id, obj in graph.vertices.items():
        label = f"{object_id}\\n{obj.object_type.value}"
        lines.append(f'  "{escape(object_id)}" [label="{escape(label)}"];')

    lines.append("")

    for edge_id, edge in graph.edges.items():
        label = edge.edge_type.value
        lines.append(
            f'  "{escape(edge.source_id)}" -> "{escape(edge.target_id)}" '
            f'[label="{escape(label)}"];'
        )

    lines.append("}")
    return "\n".join(lines)


def main():
    ddl_path = Path("examples/r5/base/schema.sql")
    out_path = Path("reports/r5_base_graph.dot")

    ddl = ddl_path.read_text(encoding="utf-8")
    graph = parse_ddl_to_graph(ddl)

    dot = graph_to_dot(graph, title="R5 base schema graph")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(dot, encoding="utf-8")

    print(f"DOT saved to: {out_path}")


if __name__ == "__main__":
    main()