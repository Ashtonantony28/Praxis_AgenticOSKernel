"""Configuration resolution per §0 — restrictive fallback if unset."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    workspace_root: Path
    memory_root: Path
    hook_path: Path
    allowed_domains: frozenset[str]

    @classmethod
    def from_env(cls) -> Config:
        ws = os.environ.get("PRAXIS_WORKSPACE_ROOT")
        workspace_root = Path(ws).resolve() if ws else Path.cwd().resolve()

        mem = os.environ.get("PRAXIS_MEMORY_ROOT")
        memory_root = Path(mem).resolve() if mem else workspace_root / ".praxis" / "memory"

        hook_path = workspace_root / ".claude" / "hooks" / "escalation-boundary.py"

        domains_str = os.environ.get("PRAXIS_ALLOWED_DOMAINS", "")
        allowed_domains = frozenset(d.strip() for d in domains_str.split(",") if d.strip())

        return cls(
            workspace_root=workspace_root,
            memory_root=memory_root,
            hook_path=hook_path,
            allowed_domains=allowed_domains,
        )
