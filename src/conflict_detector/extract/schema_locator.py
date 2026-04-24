from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


DEFAULT_SQL_EXTENSIONS = (".sql", ".ddl")


@dataclass(frozen=True)
class LocatedSchemaFile:
    path: Path
    relative_path: str
    content: str


def is_sql_file(path: Path, extensions: Sequence[str] = DEFAULT_SQL_EXTENSIONS) -> bool:
    return path.is_file() and path.suffix.lower() in {ext.lower() for ext in extensions}


def should_ignore_path(
    path: Path,
    ignore_dirs: Sequence[str] = (".git", ".idea", ".venv", "__pycache__", "node_modules"),
) -> bool:
    ignore_set = {item.lower() for item in ignore_dirs}
    return any(part.lower() in ignore_set for part in path.parts)


def read_text_file(path: Path, encoding: str = "utf-8") -> str:
    return path.read_text(encoding=encoding)


def locate_schema_files(
    root_dir: str | Path,
    *,
    recursive: bool = True,
    extensions: Sequence[str] = DEFAULT_SQL_EXTENSIONS,
    ignore_dirs: Sequence[str] = (".git", ".idea", ".venv", "__pycache__", "node_modules"),
) -> Tuple[LocatedSchemaFile, ...]:
    """
    Ищет SQL/DDL-файлы в директории и возвращает их содержимое.

    Правила MVP:
    - ищем по расширениям .sql / .ddl
    - игнорируем служебные директории
    - возвращаем файлы в стабильном лексикографическом порядке
    """
    root = Path(root_dir)
    if not root.exists():
        raise ValueError(f"Root directory does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"Root path is not a directory: {root}")

    candidate_paths: Iterable[Path]
    if recursive:
        candidate_paths = root.rglob("*")
    else:
        candidate_paths = root.iterdir()

    results: List[LocatedSchemaFile] = []

    for path in candidate_paths:
        if should_ignore_path(path, ignore_dirs=ignore_dirs):
            continue
        if not is_sql_file(path, extensions=extensions):
            continue

        relative_path = path.relative_to(root).as_posix()
        content = read_text_file(path)

        results.append(
            LocatedSchemaFile(
                path=path,
                relative_path=relative_path,
                content=content,
            )
        )

    results.sort(key=lambda item: item.relative_path.lower())
    return tuple(results)


def concatenate_schema_files(files: Sequence[LocatedSchemaFile]) -> str:
    """
    Склеивает несколько SQL/DDL файлов в один общий текст.
    Между файлами добавляется пустая строка.
    """
    if not files:
        return ""

    return "\n\n".join(item.content.strip() for item in files if item.content.strip())


def load_schema_ddl_from_directory(
    root_dir: str | Path,
    *,
    recursive: bool = True,
    extensions: Sequence[str] = DEFAULT_SQL_EXTENSIONS,
    ignore_dirs: Sequence[str] = (".git", ".idea", ".venv", "__pycache__", "node_modules"),
) -> str:
    files = locate_schema_files(
        root_dir=root_dir,
        recursive=recursive,
        extensions=extensions,
        ignore_dirs=ignore_dirs,
    )
    return concatenate_schema_files(files)
