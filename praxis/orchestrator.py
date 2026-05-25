"""Core agent loop — drives the Claude API with tool dispatch and §5 hook."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import Config
from .hooks import HookResult, run_pretool_hook
from .subagents import load_subagents
from .tools import TOOL_IMPLEMENTATIONS, get_tool_schemas

MAX_TURNS = 50  # safety limit on agent loop iterations


class Orchestrator:
    """Minimal orchestrator that makes praxis-system-prompt.md executable."""

    def __init__(self, client: Any, config: Config) -> None:
        self.client = client
        self.config = config
        self.system_prompt = self._load_system_prompt()
        self.subagents = load_subagents(config.workspace_root / ".claude" / "agents")

    def _load_system_prompt(self) -> str:
        path = self.config.workspace_root / "praxis-system-prompt.md"
        return path.read_text()

    def run(self, user_message: str, model: str = "claude-sonnet-4-6") -> str:
        """Run the orchestrator agent loop with the full system prompt."""
        return self._run_loop(
            model=model,
            system=self.system_prompt,
            user_message=user_message,
            tool_names=None,
        )

    def run_subagent(self, name: str, prompt: str) -> str:
        """Spawn a subagent session by name."""
        if name not in self.subagents:
            available = ", ".join(sorted(self.subagents))
            return f"Error: unknown subagent '{name}'. Available: {available}"
        defn = self.subagents[name]
        return self._run_loop(
            model=defn.model,
            system=defn.system_prompt,
            user_message=prompt,
            tool_names=defn.tools,
        )

    def _run_loop(
        self,
        model: str,
        system: str,
        user_message: str,
        tool_names: list[str] | None,
    ) -> str:
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
        tool_schemas = get_tool_schemas(tool_names)

        response = None
        for _ in range(MAX_TURNS):
            response = self.client.messages.create(
                model=model,
                system=system,
                messages=messages,
                tools=tool_schemas,
                max_tokens=4096,
            )

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                return self._extract_text(response)

            tool_results = self._process_tool_calls(response.content)
            if not tool_results:
                break

            messages.append({"role": "user", "content": tool_results})

        return self._extract_text(response) if response else ""

    def _process_tool_calls(
        self, content: list[Any]
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for block in content:
            if getattr(block, "type", None) != "tool_use":
                continue
            output = self._execute_with_hook(block.name, block.input)
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                }
            )
        return results

    def _execute_with_hook(
        self, tool_name: str, tool_input: dict[str, Any]
    ) -> str:
        # §5 hook check — every tool, every time
        hook = run_pretool_hook(self.config, tool_name, tool_input)
        if not hook.allowed:
            return f"BLOCKED by §5 escalation boundary: {hook.reason}"

        # Agent tool is dispatched here, not in tools.py
        if tool_name == "Agent":
            return self.run_subagent(
                tool_input.get("name", ""), tool_input.get("prompt", "")
            )

        impl = TOOL_IMPLEMENTATIONS.get(tool_name)
        if impl is None:
            return f"Error: unknown tool '{tool_name}'"

        try:
            return impl(tool_input, self.config)
        except Exception as exc:
            return f"Error executing {tool_name}: {exc}"

    @staticmethod
    def _extract_text(response: Any) -> str:
        parts = [
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        ]
        return "\n".join(parts) if parts else ""
