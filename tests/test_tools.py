"""Tests for praxis.tools — tool implementations."""

from __future__ import annotations

from pathlib import Path

from praxis.config import Config
from praxis.tools import (
    execute_bash,
    execute_edit,
    execute_glob,
    execute_grep,
    execute_read,
    execute_write,
    get_tool_schemas,
)


def test_bash_echo(config: Config):
    result = execute_bash({"command": "echo hello"}, config)
    assert "hello" in result


def test_bash_exit_code(config: Config):
    result = execute_bash({"command": "exit 42"}, config)
    assert "Exit code: 42" in result


def test_read_file(config: Config, workspace: Path):
    result = execute_read({"file_path": str(workspace / "sample.txt")}, config)
    assert "1\tline one" in result
    assert "2\tline two" in result


def test_read_with_offset_and_limit(config: Config, workspace: Path):
    result = execute_read(
        {"file_path": str(workspace / "sample.txt"), "offset": 1, "limit": 1}, config
    )
    assert "2\tline two" in result
    assert "line one" not in result
    assert "line three" not in result


def test_read_nonexistent(config: Config):
    result = execute_read({"file_path": "/no/such/file.txt"}, config)
    assert "Error" in result


def test_edit_file(config: Config, workspace: Path):
    path = workspace / "sample.txt"
    result = execute_edit(
        {"file_path": str(path), "old_string": "line two", "new_string": "LINE TWO"},
        config,
    )
    assert "Edited" in result
    assert "LINE TWO" in path.read_text()


def test_edit_missing_string(config: Config, workspace: Path):
    result = execute_edit(
        {
            "file_path": str(workspace / "sample.txt"),
            "old_string": "not here",
            "new_string": "x",
        },
        config,
    )
    assert "Error" in result


def test_write_new_file(config: Config, workspace: Path):
    target = workspace / "subdir" / "new.txt"
    result = execute_write(
        {"file_path": str(target), "content": "created"}, config
    )
    assert "Wrote" in result
    assert target.read_text() == "created"


def test_grep_finds_pattern(config: Config, workspace: Path):
    result = execute_grep({"pattern": "line two", "path": str(workspace)}, config)
    assert "line two" in result


def test_grep_no_match(config: Config, workspace: Path):
    result = execute_grep({"pattern": "zzz_no_match_zzz", "path": str(workspace)}, config)
    assert "no matches" in result


def test_glob_finds_files(config: Config, workspace: Path):
    result = execute_glob({"pattern": "*.txt", "path": str(workspace)}, config)
    assert "sample.txt" in result


def test_get_tool_schemas_all():
    schemas = get_tool_schemas()
    names = {s["name"] for s in schemas}
    assert names == {"Bash", "Read", "Edit", "Write", "Grep", "Glob", "Agent"}


def test_get_tool_schemas_subset():
    schemas = get_tool_schemas(["Read", "Grep"])
    names = {s["name"] for s in schemas}
    assert names == {"Read", "Grep"}
