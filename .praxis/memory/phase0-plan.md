# Phase 0 Plan — Minimal Python Orchestrator

**Status:** Approved for implementation
**Date:** 2026-05-25

---

## Goal

Build the smallest Python program that, when run, *is* Praxis — the
markdown spec (`praxis-system-prompt.md`) plus the subagent definitions
in `.claude/agents/*.md` drive a real Claude API session, with the §5
hook enforced on every tool call.

---

## Three design questions

### 1. How does a caller invoke a named subagent?

The orchestrator registers an `Agent` tool with the model. When the model
calls `Agent(name="scout", prompt="...")`, the orchestrator:

1. Looks up the `SubagentDef` loaded from `.claude/agents/scout.md`
2. Creates a **new agent loop** with:
   - system prompt = the markdown body (everything after YAML frontmatter)
   - tools = the subset listed in the frontmatter `tools` field
   - model = the frontmatter `model` field, mapped to a full model ID
3. Runs the subagent loop to completion
4. Returns the subagent's final text response as the tool result

Model mapping (from frontmatter shorthand to API model ID):
- `haiku` → `claude-haiku-4-5-20251001`
- `sonnet` → `claude-sonnet-4-6`
- `opus` → `claude-opus-4-6`

### 2. How does context pass between them?

- The `prompt` from the Agent tool call becomes the **user message** in the subagent session.
- The subagent's final text output becomes the **tool result** returned to the orchestrator.
- Subagents share the same filesystem (`WORKSPACE_ROOT`) — this is the primary shared-state mechanism.
- No other context passes. Subagent sessions are isolated; they don't see the orchestrator's conversation history.

### 3. How does the hook stay in the loop?

- Every tool execution — in both orchestrator and subagent sessions — passes through `hooks.run_pretool_hook()` before execution.
- The hook is: `subprocess.run(escalation-boundary.py, input=JSON_event, capture_output=True)`
- Exit 0 → allow (execute the tool)
- Exit 2 → block (return error to model, do not execute)
- The hook subprocess receives `PRAXIS_WORKSPACE_ROOT` and `PRAXIS_MEMORY_ROOT` as env vars.
- Subagents inherit the same hook unconditionally — it's hardwired in the shared `execute_tool()` path, not configurable per-agent.

---

## Architecture

```
praxis/
  __init__.py           # version string
  __main__.py           # `python -m praxis` entrypoint
  config.py             # resolve WORKSPACE_ROOT, MEMORY_ROOT from env
  subagents.py          # parse .claude/agents/*.md YAML frontmatter
  hooks.py              # run escalation-boundary.py as PreToolUse check
  tools.py              # tool JSON schemas + execute_tool() dispatch
  orchestrator.py       # agent loop: messages API → tool dispatch → hook

tests/
  conftest.py           # fixtures: FakeClient, temp workspace, mock hook
  test_config.py        # config resolution + restrictive fallback
  test_subagents.py     # YAML frontmatter parsing from real .md files
  test_hooks.py         # hook subprocess protocol: allow, block
  test_tools.py         # tool implementations against real filesystem
  test_orchestrator.py  # end-to-end with mocked Anthropic client

pyproject.toml          # anthropic, pyyaml, pytest
```

Target: ≤500 lines orchestrator, ≤300 lines tests.

---

## SDK choice

Use the standard `anthropic` Python SDK with `client.messages.create()`
and tool use. The agent loop is a simple while loop:

```python
def run_agent_loop(client, model, system, tools, user_message):
    messages = [{"role": "user", "content": user_message}]
    while True:
        response = client.messages.create(
            model=model, system=system,
            messages=messages, tools=tool_schemas,
            max_tokens=4096,
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "end_turn":
            return extract_text(response)
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input)  # hook runs here
                tool_results.append({"type": "tool_result", ...})
        messages.append({"role": "user", "content": tool_results})
```

No higher-level framework. This is the minimal loop that makes the spec
executable.

---

## Module details

### config.py (~30 lines)
- Read `PRAXIS_WORKSPACE_ROOT` and `PRAXIS_MEMORY_ROOT` from env.
- If unset, fall back to restrictive defaults: cwd for workspace, cwd/.praxis/memory for memory.
- Expose `Config` dataclass with `workspace_root`, `memory_root`, `hook_path`, `allowed_domains`.
- `hook_path` = `workspace_root / ".claude/hooks/escalation-boundary.py"`.

### subagents.py (~60 lines)
- `SubagentDef` dataclass: `name`, `description`, `tools` (list[str]), `model` (str), `system_prompt` (str).
- `load_subagents(agents_dir: Path) -> dict[str, SubagentDef]`: glob `*.md`, parse YAML frontmatter, extract body.
- `MODEL_MAP`: shorthand → full model ID.

### hooks.py (~40 lines)
- `run_pretool_hook(config, tool_name, tool_input) -> HookResult`: subprocess call to escalation-boundary.py.
- `HookResult`: `allowed: bool`, `reason: str | None`.
- Passes `PRAXIS_WORKSPACE_ROOT` and `PRAXIS_MEMORY_ROOT` as env vars to subprocess.
- JSON on stdin: `{"tool_name": name, "tool_input": input}`.

### tools.py (~150 lines)
- `TOOL_SCHEMAS`: dict mapping tool name → JSON schema for the API.
- `execute_tool(name, input, config) -> str`: dispatch to implementation.
- Tool implementations:
  - `Bash`: `subprocess.run(cmd, shell=True, capture_output=True, timeout=timeout)`
  - `Read`: open file, return contents with line numbers
  - `Edit`: find `old_string` in file, replace with `new_string`, write back
  - `Write`: write content to file_path
  - `Grep`: `subprocess.run(["grep", "-rn", pattern, path])`
  - `Glob`: `pathlib.Path.glob()` or `subprocess.run(["find", ...])`
  - `Agent`: delegates to `orchestrator.run_subagent()`

### orchestrator.py (~120 lines)
- `Orchestrator` class:
  - `__init__(client, config)`: loads system prompt, subagents, tool schemas
  - `run(user_message) -> str`: the main agent loop
  - `run_subagent(name, prompt) -> str`: spawn subagent with restricted tools/model
- Before each tool execution: call `hooks.run_pretool_hook()`. If blocked, return error string as tool result instead of executing.

### __main__.py (~20 lines)
- Parse args (optional: `--workspace-root`)
- Create `anthropic.Anthropic()` client
- Create `Config`, `Orchestrator`
- Read user input from stdin, run, print result

---

## Steps

1. **[reversible] Fix stale paths** — Update `praxis-system-prompt.md` §0 WORKSPACE_ROOT and `settings.json` hook path. Verify: grep for old path returns 0 matches.

2. **[reversible] Create `pyproject.toml`** — Dependencies: anthropic, pyyaml, pytest. Verify: file exists with correct deps.

3. **[reversible] Create `praxis/` package** — `__init__.py`, `config.py`, `subagents.py`, `hooks.py`, `tools.py`, `orchestrator.py`, `__main__.py`. Verify: `python -c "import praxis"` succeeds.

4. **[reversible] Create `tests/`** — `conftest.py`, `test_config.py`, `test_subagents.py`, `test_hooks.py`, `test_tools.py`, `test_orchestrator.py`. Verify: `python -m pytest tests/ -v` — all pass.

5. **[reversible] End-to-end smoke test** — Verify hook blocks an out-of-workspace write, allows an in-workspace read. At least one subagent definition loads correctly. Verify: specific test cases pass.

## Escalation points

- None. All work is inside WORKSPACE_ROOT, creates new files, fully reversible via git.

## Definition of done

- `python -m pytest tests/ -v` passes all tests
- Hook enforcement verified: blocked tool returns error, allowed tool executes
- At least one subagent definition loads and could be dispatched
- `python -c "from praxis.orchestrator import Orchestrator"` works
- No real API calls in tests (all mocked)
- CLAUDE.md exists with project conventions
- morning-handoff.md updated to reflect Phase 0 completion
