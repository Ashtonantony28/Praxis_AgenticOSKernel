"""ClaudeCodeRuntime — Anthropic Messages API implementation of Runtime."""

from __future__ import annotations

from typing import Any

from .base import Runtime, ToolExecutor

MAX_TURNS = 50


class ClaudeCodeRuntime(Runtime):
    """Runtime backed by the Anthropic Messages API.

    Thin wrapper that reproduces the exact behavior of the Phase 0
    orchestrator's _run_loop / _process_tool_calls / _extract_text.
    """

    def __init__(self, client: Any) -> None:
        self.client = client

    def run_loop(
        self,
        *,
        model: str,
        system: str,
        user_message: str,
        tool_schemas: list[dict[str, Any]],
        tool_executor: ToolExecutor,
        max_turns: int = MAX_TURNS,
    ) -> str:
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]

        response = None
        for _ in range(max_turns):
            response = self.client.messages.create(
                model=model,
                system=system,
                messages=messages,
                tools=tool_schemas,
                max_tokens=4096,
            )

            messages = self.manage_context(messages, "assistant", response.content)

            if response.stop_reason == "end_turn":
                return self._extract_text(response)

            tool_results = self.execute_tool(response.content, tool_executor)
            if not tool_results:
                break

            messages = self.manage_context(messages, "user", tool_results)

        return self._extract_text(response) if response else ""

    def spawn_subagent(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        tool_schemas: list[dict[str, Any]],
        tool_executor: ToolExecutor,
        max_turns: int = MAX_TURNS,
    ) -> str:
        return self.run_loop(
            model=model,
            system=system,
            user_message=prompt,
            tool_schemas=tool_schemas,
            tool_executor=tool_executor,
            max_turns=max_turns,
        )

    def execute_tool(
        self,
        response_content: list[Any],
        tool_executor: ToolExecutor,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for block in response_content:
            if getattr(block, "type", None) != "tool_use":
                continue
            output = tool_executor(block.name, block.input)
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                }
            )
        return results

    def manage_context(
        self,
        messages: list[dict[str, Any]],
        role: str,
        content: Any,
    ) -> list[dict[str, Any]]:
        messages.append({"role": role, "content": content})
        return messages

    @staticmethod
    def _extract_text(response: Any) -> str:
        parts = [
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        ]
        return "\n".join(parts) if parts else ""
