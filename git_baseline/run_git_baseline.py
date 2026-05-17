from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCENARIOS = [
    "r1",
    "r2",
    "r3",
    "r4",
    "r5",
    "r6",
    "r7",
    "n1",
    "n2",
    "n3",
    "n4",
    "n5",
    "n6",
]


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        shell=False,
    )


def run_checked(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    result = run(cmd, cwd)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n"
            f"cwd: {cwd}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def copy_schema(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def evaluate_git_merge(scenario: str) -> dict[str, str]:
    scenario_dir = PROJECT_ROOT / "examples" / scenario

    base_schema = scenario_dir / "base" / "schema.sql"
    a_schema = scenario_dir / "branch_a" / "schema.sql"
    b_schema = scenario_dir / "branch_b" / "schema.sql"

    if not base_schema.exists():
        raise FileNotFoundError(base_schema)
    if not a_schema.exists():
        raise FileNotFoundError(a_schema)
    if not b_schema.exists():
        raise FileNotFoundError(b_schema)

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / f"tmp_git_{scenario}"
        repo.mkdir()

        run_checked(["git", "init"], cwd=repo)
        run_checked(["git", "config", "user.email", "baseline@example.com"], cwd=repo)
        run_checked(["git", "config", "user.name", "Git Baseline"], cwd=repo)

        copy_schema(base_schema, repo / "schema" / "schema.sql")
        run_checked(["git", "add", "."], cwd=repo)
        run_checked(["git", "commit", "-m", "base schema"], cwd=repo)

        base_commit = run_checked(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
        ).stdout.strip()

        run_checked(["git", "checkout", "-b", "branch_a", base_commit], cwd=repo)
        copy_schema(a_schema, repo / "schema" / "schema.sql")
        run_checked(["git", "add", "."], cwd=repo)
        run_checked(["git", "commit", "-m", "branch A schema"], cwd=repo)

        run_checked(["git", "checkout", "-b", "branch_b", base_commit], cwd=repo)
        copy_schema(b_schema, repo / "schema" / "schema.sql")
        run_checked(["git", "add", "."], cwd=repo)
        run_checked(["git", "commit", "-m", "branch B schema"], cwd=repo)

        run_checked(["git", "checkout", "branch_a"], cwd=repo)
        merge = run(["git", "merge", "branch_b"], cwd=repo)

        conflict = merge.returncode != 0

        return {
            "scenario": scenario,
            "git_textual_conflict": "yes" if conflict else "no",
            "return_code": str(merge.returncode),
            "stdout": merge.stdout.strip(),
            "stderr": merge.stderr.strip(),
        }


def main() -> None:
    results = []

    for scenario in SCENARIOS:
        result = evaluate_git_merge(scenario)
        results.append(result)

    out_path = PROJECT_ROOT / "git_baseline" / "comparison_results.md"

    lines = [
        "# Git merge baseline comparison",
        "",
        "| Scenario | Git textual conflict | Return code |",
        "|---|---:|---:|",
    ]

    for result in results:
        lines.append(
            f"| {result['scenario']} | "
            f"{result['git_textual_conflict']} | "
            f"{result['return_code']} |"
        )

    lines.append("")
    lines.append("## Raw outputs")
    lines.append("")

    for result in results:
        lines.append(f"### {result['scenario']}")
        lines.append("")
        lines.append("```text")
        lines.append("STDOUT:")
        lines.append(result["stdout"])
        lines.append("")
        lines.append("STDERR:")
        lines.append(result["stderr"])
        lines.append("```")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"Saved results to {out_path}")


if __name__ == "__main__":
    main()