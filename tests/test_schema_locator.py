from __future__ import annotations

from pathlib import Path

from src.conflict_detector.extract.schema_locator import (
    concatenate_schema_files,
    is_sql_file,
    load_schema_ddl_from_directory,
    locate_schema_files,
    should_ignore_path,
)


def test_is_sql_file(tmp_path: Path):
    sql_file = tmp_path / "schema.sql"
    sql_file.write_text("CREATE TABLE users (id integer);", encoding="utf-8")

    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("hello", encoding="utf-8")

    assert is_sql_file(sql_file) is True
    assert is_sql_file(txt_file) is False


def test_should_ignore_path():
    assert should_ignore_path(Path(".git/config")) is True
    assert should_ignore_path(Path("src/__pycache__/a.pyc")) is True
    assert should_ignore_path(Path("schemas/users.sql")) is False


def test_locate_schema_files_non_recursive(tmp_path: Path):
    file_a = tmp_path / "a.sql"
    file_a.write_text("CREATE TABLE a (id integer);", encoding="utf-8")

    nested = tmp_path / "nested"
    nested.mkdir()
    file_b = nested / "b.sql"
    file_b.write_text("CREATE TABLE b (id integer);", encoding="utf-8")

    files = locate_schema_files(tmp_path, recursive=False)

    assert len(files) == 1
    assert files[0].relative_path == "a.sql"


def test_locate_schema_files_recursive(tmp_path: Path):
    file_a = tmp_path / "a.sql"
    file_a.write_text("CREATE TABLE a (id integer);", encoding="utf-8")

    nested = tmp_path / "nested"
    nested.mkdir()
    file_b = nested / "b.ddl"
    file_b.write_text("CREATE TABLE b (id integer);", encoding="utf-8")

    files = locate_schema_files(tmp_path, recursive=True)

    relative_paths = [item.relative_path for item in files]
    assert len(files) == 2
    assert "a.sql" in relative_paths
    assert "nested/b.ddl" in relative_paths


def test_locate_schema_files_ignores_service_dirs(tmp_path: Path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    git_file = git_dir / "ignored.sql"
    git_file.write_text("CREATE TABLE ignored (id integer);", encoding="utf-8")

    sql_dir = tmp_path / "schemas"
    sql_dir.mkdir()
    sql_file = sql_dir / "users.sql"
    sql_file.write_text("CREATE TABLE users (id integer);", encoding="utf-8")

    files = locate_schema_files(tmp_path, recursive=True)

    assert len(files) == 1
    assert files[0].relative_path == "schemas/users.sql"


def test_concatenate_schema_files(tmp_path: Path):
    file_a = tmp_path / "a.sql"
    file_a.write_text("CREATE TABLE a (id integer);", encoding="utf-8")

    file_b = tmp_path / "b.sql"
    file_b.write_text("CREATE TABLE b (id integer);", encoding="utf-8")

    files = locate_schema_files(tmp_path, recursive=False)
    ddl = concatenate_schema_files(files)

    assert "CREATE TABLE a" in ddl
    assert "CREATE TABLE b" in ddl


def test_load_schema_ddl_from_directory(tmp_path: Path):
    file_a = tmp_path / "users.sql"
    file_a.write_text(
        "CREATE TABLE users (id integer PRIMARY KEY, email text NOT NULL);",
        encoding="utf-8",
    )

    nested = tmp_path / "migrations"
    nested.mkdir()
    file_b = nested / "orders.sql"
    file_b.write_text(
        "CREATE TABLE orders (id integer PRIMARY KEY, user_id integer REFERENCES users(id));",
        encoding="utf-8",
    )

    ddl = load_schema_ddl_from_directory(tmp_path, recursive=True)

    assert "CREATE TABLE users" in ddl
    assert "CREATE TABLE orders" in ddl
