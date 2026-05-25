"""Tests for praxis.config — §0 restrictive fallback semantics."""

from __future__ import annotations

from pathlib import Path

from praxis.config import Config


def test_from_env_with_vars(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PRAXIS_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("PRAXIS_MEMORY_ROOT", str(tmp_path / "mem"))
    cfg = Config.from_env()
    assert cfg.workspace_root == tmp_path.resolve()
    assert cfg.memory_root == (tmp_path / "mem").resolve()


def test_from_env_no_vars_falls_back_to_cwd(monkeypatch):
    monkeypatch.delenv("PRAXIS_WORKSPACE_ROOT", raising=False)
    monkeypatch.delenv("PRAXIS_MEMORY_ROOT", raising=False)
    cfg = Config.from_env()
    assert cfg.workspace_root == Path.cwd().resolve()
    assert cfg.memory_root == Path.cwd().resolve() / ".praxis" / "memory"


def test_memory_root_defaults_under_workspace(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PRAXIS_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.delenv("PRAXIS_MEMORY_ROOT", raising=False)
    cfg = Config.from_env()
    assert cfg.memory_root == tmp_path.resolve() / ".praxis" / "memory"


def test_hook_path_derived_from_workspace(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PRAXIS_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.delenv("PRAXIS_MEMORY_ROOT", raising=False)
    cfg = Config.from_env()
    expected = tmp_path.resolve() / ".claude" / "hooks" / "escalation-boundary.py"
    assert cfg.hook_path == expected


def test_allowed_domains_empty_by_default(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PRAXIS_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.delenv("PRAXIS_ALLOWED_DOMAINS", raising=False)
    cfg = Config.from_env()
    assert cfg.allowed_domains == frozenset()


def test_allowed_domains_parsed_from_env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PRAXIS_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("PRAXIS_ALLOWED_DOMAINS", "example.com, api.test.io")
    cfg = Config.from_env()
    assert cfg.allowed_domains == frozenset({"example.com", "api.test.io"})
