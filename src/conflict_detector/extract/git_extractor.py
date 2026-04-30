from __future__ import annotations

import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

from src.conflict_detector.extract.schema_locator import (
    load_schema_ddl_from_directory,
)


@dataclass(frozen=True)
class ExtractedGitSchemas:
    base_ddl: str
    branch_a_ddl: str
    branch_b_ddl: str
    merge_base: str
    branch_a: str
    branch_b: str
    repo_path: str


def run_git_command(repo_path: str | Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def get_merge_base(
    repo_path: str | Path,
    branch_a: str,
    branch_b: str,
) -> str:
    return run_git_command(
        repo_path,
        ["merge-base", branch_a, branch_b],
    )


def export_commit_to_directory(
    repo_path: str | Path,
    commit: str,
    output_dir: str | Path,
) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    archive_path = output_dir / "repo_snapshot.tar"

    subprocess.run(
        [
            "git",
            "-C",
            str(repo_path),
            "archive",
            "--format=tar",
            f"--output={archive_path}",
            commit,
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    with tarfile.open(archive_path, "r") as archive:
        archive.extractall(output_dir)

    archive_path.unlink(missing_ok=True)


def extract_schema_from_commit(
    repo_path: str | Path,
    commit: str,
) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        export_commit_to_directory(
            repo_path=repo_path,
            commit=commit,
            output_dir=tmpdir,
        )

        return load_schema_ddl_from_directory(tmpdir)


def extract_three_schemas_from_git(
    repo_path: str | Path,
    branch_a: str,
    branch_b: str,
) -> ExtractedGitSchemas:
    merge_base = get_merge_base(repo_path, branch_a, branch_b)

    base_ddl = extract_schema_from_commit(repo_path, merge_base)
    branch_a_ddl = extract_schema_from_commit(repo_path, branch_a)
    branch_b_ddl = extract_schema_from_commit(repo_path, branch_b)

    return ExtractedGitSchemas(
        base_ddl=base_ddl,
        branch_a_ddl=branch_a_ddl,
        branch_b_ddl=branch_b_ddl,
        merge_base=merge_base,
        branch_a=branch_a,
        branch_b=branch_b,
        repo_path=str(repo_path),
    )
