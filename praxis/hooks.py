"""PreToolUse hook integration — runs escalation-boundary.py per §5."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

from .config import Config


@dataclass
class HookResult:
    allowed: bool
    reason: str | None = None


def run_pretool_hook(
    config: Config, tool_name: str, tool_input: dict[str, Any]
) -> HookResult:
    """Invoke the §5 escalation-boundary hook before a tool call.

    Returns HookResult with allowed=True if the tool may proceed.
    """
    if not config.hook_path.exists():
        return HookResult(allowed=True)

    event = json.dumps({"tool_name": tool_name, "tool_input": tool_input})

    env = {**os.environ}
    env["PRAXIS_WORKSPACE_ROOT"] = str(config.workspace_root)
    env["PRAXIS_MEMORY_ROOT"] = str(config.memory_root)

    try:
        result = subprocess.run(
            [sys.executable, str(config.hook_path)],
            input=event,
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return HookResult(allowed=False, reason="Hook timed out")

    if result.returncode == 0:
        return HookResult(allowed=True)

    reason = result.stderr.strip() if result.stderr else f"Hook exited {result.returncode}"
    return HookResult(allowed=False, reason=reason)
