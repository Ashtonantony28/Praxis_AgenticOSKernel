"""File management integration — search, summarize, git status, disk usage."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from ..config import Config
from ..tools import _subprocess_env, _redact_secrets

SCHEMAS: dict[str, dict[str, Any]] = {
    "FileManager": {
        "name": "FileManager",
        "description": (
            "File management for workspace files. "
            "Actions: search (full-text search), summarize (file/directory overview), "
            "git_status (branch and changes), disk_usage (size breakdown)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["search", "summarize", "git_status", "disk_usage"],
                    "description": "The file management operation to perform",
                },
                "query": {
                    "type": "string",
                    "description": "Search query (required for search action)",
                },
                "path": {
                    "type": "string",
                    "description": (
                        "Relative path within workspace (optional for search, "
                        "summarize, disk_usage — defaults to workspace root)"
                    ),
                },
                "glob": {
                    "type": "string",
                    "description": "File glob pattern for search (default: all files)",
                },
            },
            "required": ["action"],
        },
    },
}


# ---------- Path validation ----------


def _resolve_path(path_str: str | None, config: Config) -> tuple[Path, str | None]:
    """Resolve a path relative to workspace root.

    Returns (resolved_path, error_string). If error_string is not None,
    the path escapes the workspace boundary.
    """
    root = config.workspace_root
    if not path_str:
        return root, None

    resolved = (root / path_str).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return resolved, "Error: path escapes workspace boundary"
    return resolved, None


# ---------- Search ----------


def _search(query: str, path: Path, glob_pattern: str | None, config: Config) -> str:
    """Full-text search across workspace files using grep."""
    grep = shutil.which("grep")
    if grep is None:
        return "Error: grep not found on system"

    cmd = [grep, "-rn", "--color=never"]
    if glob_pattern:
        cmd.extend(["--include", glob_pattern])
    cmd.extend(["--", query, str(path)])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(config.workspace_root),
            env=_subprocess_env(config),
        )
    except subprocess.TimeoutExpired:
        return "Error: search timed out after 30s"

    if result.returncode == 1:
        return f"No matches found for: {query}"
    if result.returncode != 0:
        return f"Error: grep failed: {result.stderr.strip()}"

    output = result.stdout.strip()
    # Limit output to prevent context blowout
    lines = output.splitlines()
    if len(lines) > 100:
        output = "\n".join(lines[:100])
        output += f"\n\n... ({len(lines) - 100} more matches truncated)"

    return _redact_secrets(output or "No matches found")


# ---------- Summarize ----------


def _summarize_file(path: Path) -> str:
    """Produce a structured summary of a single file."""
    try:
        stat = path.stat()
    except OSError as exc:
        return f"Error: cannot stat {path.name}: {exc}"

    size = stat.st_size
    lines: list[str] = [
        f"File: {path.name}",
        f"Size: {_human_size(size)}",
    ]

    # Try to count lines and show preview for text files
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        lines.append(f"Lines: {line_count}")

        # File extension as type hint
        suffix = path.suffix or "(no extension)"
        lines.append(f"Type: {suffix}")

        # First 20 lines as preview
        preview_lines = content.splitlines()[:20]
        if preview_lines:
            lines.append("")
            lines.append("Preview (first 20 lines):")
            for i, line in enumerate(preview_lines, 1):
                lines.append(f"  {i:4d} | {line}")
            if line_count > 20:
                lines.append(f"  ... ({line_count - 20} more lines)")
    except (OSError, UnicodeDecodeError):
        lines.append("Type: binary")

    return "\n".join(lines)


def _summarize_dir(path: Path, config: Config) -> str:
    """Produce a structured summary of a directory."""
    root = config.workspace_root
    files = 0
    dirs = 0
    total_size = 0
    tree_lines: list[str] = []

    for dirpath, dirnames, filenames in os.walk(path):
        depth = Path(dirpath).relative_to(path).parts
        if len(depth) >= 3:
            dirnames.clear()
            continue
        indent = "  " * len(depth)
        rel = Path(dirpath).relative_to(root)
        tree_lines.append(f"{indent}{rel}/")
        dirs += 1
        for f in sorted(filenames):
            fp = Path(dirpath) / f
            try:
                sz = fp.stat().st_size
            except OSError:
                sz = 0
            total_size += sz
            files += 1
            if len(depth) < 2:
                tree_lines.append(f"{indent}  {f} ({_human_size(sz)})")

    header = [
        f"Directory: {path.relative_to(root)}",
        f"Files: {files}",
        f"Directories: {dirs}",
        f"Total size: {_human_size(total_size)}",
        "",
        "Tree (depth 3):",
    ]

    # Limit tree output
    if len(tree_lines) > 80:
        tree_lines = tree_lines[:80]
        tree_lines.append(f"... (truncated)")

    return "\n".join(header + tree_lines)


def _summarize(path: Path, config: Config) -> str:
    """Summarize a file or directory."""
    if not path.exists():
        return f"Error: path does not exist: {path.name}"
    if path.is_file():
        return _summarize_file(path)
    if path.is_dir():
        return _summarize_dir(path, config)
    return f"Error: unsupported path type: {path.name}"


# ---------- Git status ----------


def _git_status(config: Config) -> str:
    """Get current branch, uncommitted changes, and recent commits."""
    git = shutil.which("git")
    if git is None:
        return "Error: git not installed"

    env = _subprocess_env(config)
    cwd = str(config.workspace_root)

    # Check if we're in a git repo
    try:
        check = subprocess.run(
            [git, "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, timeout=10, cwd=cwd, env=env,
        )
    except subprocess.TimeoutExpired:
        return "Error: git command timed out"
    if check.returncode != 0:
        return "Error: not a git repository"

    sections: list[str] = []

    # Current branch
    try:
        branch = subprocess.run(
            [git, "branch", "--show-current"],
            capture_output=True, text=True, timeout=10, cwd=cwd, env=env,
        )
        branch_name = branch.stdout.strip() or "(detached HEAD)"
        sections.append(f"Branch: {branch_name}")
    except subprocess.TimeoutExpired:
        sections.append("Branch: (timed out)")

    # Status (uncommitted changes)
    try:
        status = subprocess.run(
            [git, "status", "--porcelain"],
            capture_output=True, text=True, timeout=10, cwd=cwd, env=env,
        )
        changes = status.stdout.strip()
        if changes:
            change_lines = changes.splitlines()
            sections.append(f"\nUncommitted changes ({len(change_lines)} files):")
            for line in change_lines[:30]:
                sections.append(f"  {line}")
            if len(change_lines) > 30:
                sections.append(f"  ... ({len(change_lines) - 30} more)")
        else:
            sections.append("\nWorking tree clean")
    except subprocess.TimeoutExpired:
        sections.append("\nStatus: (timed out)")

    # Recent commits
    try:
        log = subprocess.run(
            [git, "log", "--oneline", "-10"],
            capture_output=True, text=True, timeout=10, cwd=cwd, env=env,
        )
        commits = log.stdout.strip()
        if commits:
            sections.append(f"\nRecent commits:")
            for line in commits.splitlines():
                sections.append(f"  {line}")
    except subprocess.TimeoutExpired:
        sections.append("\nRecent commits: (timed out)")

    return _redact_secrets("\n".join(sections))


# ---------- Disk usage ----------


def _disk_usage(path: Path, config: Config) -> str:
    """Report disk usage for a path within the workspace."""
    env = _subprocess_env(config)
    cwd = str(config.workspace_root)

    # Total size of target
    try:
        total = subprocess.run(
            ["du", "-sh", str(path)],
            capture_output=True, text=True, timeout=30, cwd=cwd, env=env,
        )
    except subprocess.TimeoutExpired:
        return "Error: disk usage command timed out after 30s"

    if total.returncode != 0:
        return f"Error: du failed: {total.stderr.strip()}"

    sections: list[str] = [f"Disk usage: {total.stdout.strip()}"]

    # Breakdown by immediate children (directories only)
    if path.is_dir():
        try:
            breakdown = subprocess.run(
                ["du", "-sh", "--", *[
                    str(p) for p in sorted(path.iterdir()) if p.is_dir()
                ]],
                capture_output=True, text=True, timeout=30, cwd=cwd, env=env,
            )
            if breakdown.returncode == 0 and breakdown.stdout.strip():
                lines = breakdown.stdout.strip().splitlines()
                # Sort by size descending (du output is "SIZE\tPATH")
                lines.sort(key=lambda l: l.split("\t")[0], reverse=True)
                sections.append("\nTop directories:")
                for line in lines[:15]:
                    sections.append(f"  {line}")
                if len(lines) > 15:
                    sections.append(f"  ... ({len(lines) - 15} more)")
        except (subprocess.TimeoutExpired, OSError):
            pass  # Breakdown is best-effort

    return _redact_secrets("\n".join(sections))


# ---------- Helpers ----------


def _human_size(nbytes: int) -> str:
    """Convert bytes to human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(nbytes) < 1024:
            return f"{nbytes:.1f} {unit}" if unit != "B" else f"{nbytes} B"
        nbytes /= 1024  # type: ignore[assignment]
    return f"{nbytes:.1f} TB"


# ---------- Dispatch ----------


def execute_filemanager(args: dict[str, Any], config: Config) -> str:
    action = args.get("action", "")

    if action == "search":
        query = args.get("query", "")
        if not query:
            return "Error: 'query' is required for search action"
        path, err = _resolve_path(args.get("path"), config)
        if err:
            return err
        glob_pattern = args.get("glob")
        return _search(query, path, glob_pattern, config)

    elif action == "summarize":
        path, err = _resolve_path(args.get("path"), config)
        if err:
            return err
        return _summarize(path, config)

    elif action == "git_status":
        return _git_status(config)

    elif action == "disk_usage":
        path, err = _resolve_path(args.get("path"), config)
        if err:
            return err
        return _disk_usage(path, config)

    else:
        return f"Error: unknown FileManager action '{action}'"


IMPLEMENTATIONS: dict[str, Callable[[dict[str, Any], Config], str]] = {
    "FileManager": execute_filemanager,
}
