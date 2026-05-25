"""Tests for praxis.tools — tool implementations."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from praxis.config import Config
from praxis.tools import (
    _redact_secrets,
    _subprocess_env,
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


# ---------- E-1: Token propagation & secret filtering ----------


def test_subprocess_env_includes_workspace(config: Config):
    env = _subprocess_env(config)
    assert env["PRAXIS_WORKSPACE_ROOT"] == str(config.workspace_root)
    assert env["PRAXIS_MEMORY_ROOT"] == str(config.memory_root)


def test_subprocess_env_includes_oauth_token(config: Config):
    with patch.dict(os.environ, {"CLAUDE_CODE_OAUTH_TOKEN": "secret-token-123"}):
        env = _subprocess_env(config)
        assert env["CLAUDE_CODE_OAUTH_TOKEN"] == "secret-token-123"


def test_redact_secrets_oauth(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-oauth-abc123")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = _redact_secrets("output contains sk-oauth-abc123 here")
    assert "sk-oauth-abc123" not in result
    assert "[REDACTED]" in result


def test_redact_secrets_api_key(monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-xyz789")
    result = _redact_secrets("key is sk-ant-xyz789 in output")
    assert "sk-ant-xyz789" not in result
    assert "[REDACTED]" in result


def test_redact_secrets_no_match(monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = _redact_secrets("safe output with no secrets")
    assert result == "safe output with no secrets"


def test_bash_redacts_token_from_output(config: Config, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "token-in-output")
    result = execute_bash({"command": "echo token-in-output"}, config)
    assert "token-in-output" not in result
    assert "[REDACTED]" in result


def test_bash_passes_explicit_env(config: Config, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "my-test-token")
    result = execute_bash(
        {"command": "python -c \"import os; print(os.environ.get('CLAUDE_CODE_OAUTH_TOKEN', 'MISSING'))\""},
        config,
    )
    # Token value is redacted but proves it was available to the subprocess
    assert "MISSING" not in result
    assert "[REDACTED]" in result
