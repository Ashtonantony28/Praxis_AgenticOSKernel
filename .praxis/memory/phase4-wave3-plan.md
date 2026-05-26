# Phase 4 Wave 3 — File Management Integration Plan

**Date:** 2026-05-25  
**Status:** Planning complete, ready for build

---

## Scope decision

### Included (4 actions)

| Action | Value | Complexity | Mode |
|--------|-------|------------|------|
| `search(query, path, glob)` | High | Low — `grep -rn` subprocess | Assistant, Workstation |
| `git_status()` | High | Low — `git` subprocess | Workstation |
| `summarize(path)` | Medium | Low — os.walk + stat | Assistant, Workstation |
| `disk_usage(path)` | Medium | Low — `du -sh` subprocess | Operator |

### Cut

| Action | Reason |
|--------|--------|
| `watch(path, pattern)` | Requires persistent background state (inotify/polling), daemon integration, thread management. High complexity, low MVP value. Defer to future wave if needed. |
| Project context auto-detection | Nice-to-have, not a tool action. Can be layered on top of summarize later. |

### Rationale

Four actions cover all three operating modes with zero external dependencies. Every action is a thin subprocess wrapper following the established integration pattern. `watch` would be the only action requiring persistent state — cutting it keeps the integration stateless like the other five modules.

---

## Design

- **Tool name:** `FileManager`
- **File:** `praxis/integrations/files.py`
- **Pattern:** SCHEMAS dict + IMPLEMENTATIONS dict + execute_filemanager dispatch (matches github.py, web.py, etc.)

### Boundary enforcement

Every path argument is resolved against `config.workspace_root`. If the resolved path does not start with `workspace_root`, the action returns an error string. No reads or writes outside the sandbox.

### Actions

1. **`search(query, path?, glob?)`** — `grep -rn --include=GLOB QUERY PATH` within workspace. Returns matching lines with file:line format. Default path is workspace root, default glob is `*`.

2. **`git_status()`** — runs `git status --porcelain`, `git branch --show-current`, `git log --oneline -10` in workspace root. Returns structured output. Fails cleanly if not a git repo.

3. **`summarize(path)`** — for files: type, line count, size, first 20 lines. For directories: file count, total size, tree listing (max depth 3). All via stdlib (os.walk, os.stat).

4. **`disk_usage(path?)`** — `du -sh` on path (default: workspace root), plus top-10 largest subdirectories via `du -sh * | sort -rh | head -10`. Returns human-readable sizes.

### Error handling

- Path escape → `"Error: path escapes workspace boundary"`
- git not installed / not a repo → clean error string
- grep no matches → `"No matches found for: {query}"`
- Timeouts → `"Error: command timed out after {n}s"`
