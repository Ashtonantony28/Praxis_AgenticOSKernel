# Phase A — Runtime Abstraction Plan

**Goal:** Pure refactor. Extract a `Runtime` interface from the Orchestrator so
providers can be swapped without changing orchestrator logic. Behavior identical
before and after.

---

## 1. The Runtime Interface (4 responsibilities)

```
praxis/runtime/
  __init__.py          # exports Runtime, ClaudeCodeRuntime
  base.py              # abstract Runtime class
  claude_code.py       # ClaudeCodeRuntime — reproduces today's exact behavior
```

### Abstract methods

| Method | Signature | What it does |
|--------|-----------|-------------|
| `run_loop` | `(model, system, user_message, tool_schemas, tool_executor, max_turns) → str` | Full agent conversation loop: call API, parse response, dispatch tools via callback, repeat until done, return final text. |
| `spawn_subagent` | `(model, system, prompt, tool_schemas, tool_executor, max_turns) → str` | Run a subagent session. Default: same as run_loop. Different runtimes may use separate sessions/instances. |
| `execute_tool` | `(response_content, tool_executor) → list[dict]` | Extract tool_use blocks from provider response, invoke tool_executor(name, input) for each, return formatted tool_result list. |
| `manage_context` | `(messages, role, content) → list[dict]` | Append a message to the conversation history. Provider-specific because message format may differ. |

`tool_executor: Callable[[str, dict], str]` — the Orchestrator provides this callback.
It handles §5 hook enforcement + tool dispatch + Agent-as-subagent routing.

---

## 2. Scout inventory → Interface mapping

| Coupling point | Currently | After refactor |
|---------------|-----------|---------------|
| `__main__.py:15` — `anthropic.Anthropic()` | Creates client directly | Creates `ClaudeCodeRuntime(client)`, passes to Orchestrator |
| `orchestrator.py:63` — `client.messages.create()` | In `_run_loop` | Moves to `ClaudeCodeRuntime.run_loop()` |
| `orchestrator.py:73` — `stop_reason == "end_turn"` | In `_run_loop` | Moves to `ClaudeCodeRuntime.run_loop()` |
| `orchestrator.py:89-98` — block parsing + tool_result format | In `_process_tool_calls` | Moves to `ClaudeCodeRuntime.execute_tool()` |
| `orchestrator.py:126-129` — text extraction | In `_extract_text` | Private method on `ClaudeCodeRuntime` |
| `orchestrator.py:70-80` — message list management | In `_run_loop` | Via `ClaudeCodeRuntime.manage_context()` |

**Unchanged:** `tools.py` (schemas + impls), `hooks.py`, `config.py`, `subagents.py`.

---

## 3. Refactored Orchestrator

```python
class Orchestrator:
    def __init__(self, runtime: Runtime, config: Config):
        self.runtime = runtime  # was: self.client
        self.config = config
        ...

    def run(self, user_message, model="claude-sonnet-4-6") -> str:
        return self.runtime.run_loop(
            model=model, system=self.system_prompt,
            user_message=user_message,
            tool_schemas=get_tool_schemas(),
            tool_executor=self._execute_with_hook,
        )

    def run_subagent(self, name, prompt) -> str:
        defn = self.subagents[name]
        return self.runtime.spawn_subagent(
            model=defn.model, system=defn.system_prompt,
            prompt=prompt,
            tool_schemas=get_tool_schemas(defn.tools),
            tool_executor=self._execute_with_hook,
        )

    def _execute_with_hook(self, tool_name, tool_input) -> str:
        # UNCHANGED — §5 hook + dispatch (including Agent → run_subagent)
        ...
```

---

## 4. Test changes

Minimal — only `test_orchestrator.py` and `conftest.py`:

```python
# Before:
client = FakeClient(responses)
orch = Orchestrator(client, config)

# After:
client = FakeClient(responses)
runtime = ClaudeCodeRuntime(client)
orch = Orchestrator(runtime, config)
```

All 43 tests keep the same assertions. FakeClient still works because
ClaudeCodeRuntime calls `self.client.messages.create()` internally.

---

## 5. File change list (ordered)

1. **Create** `praxis/runtime/__init__.py` — exports
2. **Create** `praxis/runtime/base.py` — abstract Runtime class
3. **Create** `praxis/runtime/claude_code.py` — ClaudeCodeRuntime (move API-specific code here)
4. **Edit** `praxis/orchestrator.py` — depend on Runtime, remove API-specific code
5. **Edit** `praxis/__main__.py` — construct ClaudeCodeRuntime
6. **Edit** `tests/test_orchestrator.py` — wrap FakeClient in ClaudeCodeRuntime
7. No changes to: config.py, hooks.py, subagents.py, tools.py, conftest.py, other test files

---

## 6. What a second provider must implement

A new provider (e.g., OpenAI) subclasses `Runtime` and implements:
- `run_loop` — using their API call protocol
- `spawn_subagent` — their session management
- `execute_tool` — parsing their tool_call format, formatting results
- `manage_context` — their message format

Tool implementations, hook enforcement, and subagent definitions are reused unchanged.
