# Praxis Workspace

This repository hosts the Praxis orchestrator system prompt and its
Claude Code control plane (hooks, subagent roster, settings).

## Layout

- `praxis-system-prompt.md` — the orchestrator prompt itself; the
  authoritative source for §1–§11 referenced elsewhere.
- `.claude/settings.json` — Claude Code settings; declares the active
  PreToolUse hook(s).
- `.claude/hooks/` — legacy location of PreToolUse hook scripts.
- `.claude/agents/` — subagent definitions (scout, planner, builder,
  verifier, scribe). Discovered automatically by Claude Code.
- `.praxis/hooks/` — current location of PreToolUse hook scripts.
  Treated as control plane.
- `.praxis/memory/` — durable cross-session memory
  (`MEMORY_ROOT`). Handoff notes, decisions, learned facts.

## Control plane

The active PreToolUse hook enforces the §5 escalation boundary. It
blocks, by default, any tool call that would:

- write outside `WORKSPACE_ROOT` (`/home/user/LinuxAgenticClaudeOS`),
- modify the control plane (`.claude/`, `.praxis/hooks/`),
- reach the network (`WebFetch`/`WebSearch`, or Bash `curl`/`wget`/
  `ssh`/`nc`/`scp`/`sftp`/`rsync`/`ftp`/`telnet` against a non-
  localhost target).

`.claude/agents/` is **exempt** from the control-plane block — see
the rationale in `.praxis/memory/morning-handoff.md` (subagent
location decision). Subagent definitions are workspace content, not
enforcement rules; they cannot widen authority (§6).

To make an authorized control-plane change, the human escalates per
§5; the orchestrator may then make the change directly.

## Conventions

- Verify with the hook test suite (`python3 .praxis/hooks/test_pre_tool_use.py`)
  before touching `.praxis/hooks/pre_tool_use.py` or
  `.claude/settings.json`.
- Update `.praxis/memory/morning-handoff.md` when handing off work
  between sessions.
- Commit messages are short, imperative, and describe the why.
