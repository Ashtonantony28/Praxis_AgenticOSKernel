"""Tests for praxis.subagents — YAML frontmatter parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from praxis.subagents import (
    MODEL_MAP,
    SubagentDef,
    _parse_frontmatter,
    load_subagents,
    parse_agent_file,
)


def test_parse_frontmatter_basic():
    text = "---\nname: test\nmodel: haiku\n---\n\nBody here."
    front, body = _parse_frontmatter(text)
    assert front["name"] == "test"
    assert front["model"] == "haiku"
    assert body == "Body here."


def test_parse_frontmatter_missing_raises():
    with pytest.raises(ValueError, match="No YAML frontmatter"):
        _parse_frontmatter("Just plain markdown.")


def test_parse_agent_file_tools_list(tmp_path: Path):
    md = tmp_path / "agent.md"
    md.write_text(
        "---\nname: builder\ndescription: Builds things\n"
        "tools: Read, Edit, Write, Bash\nmodel: sonnet\n---\n\nDo the work."
    )
    defn = parse_agent_file(md)
    assert defn.tools == ["Read", "Edit", "Write", "Bash"]


def test_parse_agent_file_model_mapping(tmp_path: Path):
    md = tmp_path / "agent.md"
    md.write_text("---\nname: s\ntools: Read\nmodel: haiku\n---\n\nBody.")
    defn = parse_agent_file(md)
    assert defn.model == MODEL_MAP["haiku"]


def test_parse_agent_file_system_prompt(tmp_path: Path):
    body = "You are **Scout**. Investigate."
    md = tmp_path / "agent.md"
    md.write_text(f"---\nname: scout\ntools: Read\nmodel: haiku\n---\n\n{body}")
    defn = parse_agent_file(md)
    assert defn.system_prompt == body


def test_load_subagents_from_real_agents(workspace: Path):
    agents = load_subagents(workspace / ".claude" / "agents")
    assert set(agents.keys()) == {"builder", "planner", "scout", "scribe", "verifier"}


def test_load_subagents_empty_dir(tmp_path: Path):
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    assert load_subagents(agents_dir) == {}


def test_all_real_agents_have_required_fields(workspace: Path):
    agents = load_subagents(workspace / ".claude" / "agents")
    for name, defn in agents.items():
        assert defn.name, f"{name} missing name"
        assert defn.tools, f"{name} missing tools"
        assert defn.model in MODEL_MAP.values(), f"{name} has unmapped model: {defn.model}"
        assert defn.system_prompt, f"{name} missing system_prompt"
