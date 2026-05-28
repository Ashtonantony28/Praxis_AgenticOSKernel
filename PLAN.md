# Praxis PLAN.md — Config Wizard (Cycle C)

## Goal
Add a `--config` command that gives users a terminal UI for changing model and
effort settings without editing code or config files.

## Deliverables

| ID   | File(s)                        | Description                                       |
|------|-------------------------------|---------------------------------------------------|
| C-01 | praxis/config_wizard.py        | Interactive terminal configuration manager         |
| C-02 | praxis/__main__.py             | Wire `--config` into the entry point              |
| C-03 | praxis/config_wizard.py        | Add effort preset menu (extends C-01)             |
| C-04 | tests/test_config_wizard.py    | Full test suite for config wizard                 |
| C-05 | README.md, CLAUDE.md, .praxis/memory/morning-handoff.md | Scribe pass |

## Constraints & regulations

- All CLAUDE.md governance rules apply throughout.
- §5 boundary is inviolable — no writes outside WORKSPACE_ROOT, no egress.
- Control-plane files (.claude/hooks/, .claude/settings.json) are NEVER touched.
- No real API calls in tests — all I/O mocked.
- `convergence.yaml` changes use the `agents:` section only — never break existing keys.
- `.env` writes are merge-mode by default (never silently overwrite existing keys).
- All 767 pre-existing tests must still pass when C-04 is done.

## Definition of done

- `python -m praxis --config` launches the menu with no errors.
- Menu reads current settings from convergence.yaml / .env / defaults.
- All 6 effort presets apply cleanly and show diff before confirmation.
- `.env` and `convergence.yaml` are written correctly per tests.
- `python -m pytest tests/ -q` reports ≥767+N tests pass, 0 failures.
- `md5sum .claude/hooks/escalation-boundary.py` = 057f07f223fd5b5fe11f2aa50af1e361 (unchanged).

## Architecture notes

- `praxis/config_wizard.py` is a standalone module (like setup_wizard.py).
  Exports one public function: `run_config_wizard(workspace_root, *, env_file, _input, _env_mode)`.
- Reads: convergence.yaml agents section + env vars; writes: .env (merge) + convergence.yaml.
- Does NOT import orchestrator or runtimes — purely file I/O.
- `convergence.yaml` gains an `agents:` section:
  ```yaml
  agents:
    orchestrator: claude-opus-4-7
    builder: claude-sonnet-4-6
    reviewer: claude-haiku-4-5
    scout: claude-haiku-4-5
    scribe: claude-haiku-4-5
  ```
- Effort preset name stored as `PRAXIS_EFFORT_PRESET=<name>` in .env.
- Max turns stored as `PRAXIS_MAX_TURNS=<n>` in .env.
