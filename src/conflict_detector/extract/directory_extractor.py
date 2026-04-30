from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.conflict_detector.extract.schema_locator import (
    load_schema_ddl_from_directory,
)


@dataclass(frozen=True)
class ExtractedDirectorySchemas:
    base_ddl: str
    branch_a_ddl: str
    branch_b_ddl: str


def extract_schemas_from_directories(
    base_dir: str | Path,
    branch_a_dir: str | Path,
    branch_b_dir: str | Path,
) -> ExtractedDirectorySchemas:
    base_ddl = load_schema_ddl_from_directory(base_dir)
    branch_a_ddl = load_schema_ddl_from_directory(branch_a_dir)
    branch_b_ddl = load_schema_ddl_from_directory(branch_b_dir)

    return ExtractedDirectorySchemas(
        base_ddl=base_ddl,
        branch_a_ddl=branch_a_ddl,
        branch_b_ddl=branch_b_ddl,
    )
