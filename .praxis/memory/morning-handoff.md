# Morning handoff — Phase A runtime-abstraction refactor

**Status: HALTED before any change. Repo is untouched.**

## Why I stopped

The Phase A task description assumes a codebase that does not exist in this
repository on any branch:

1. **No `CLAUDE.md`** — the task said to read it; it isn't here.
2. **No prior `morning-handoff.md`** — this file is the first one.
3. **No Python orchestrator.** The task said to "refactor the orchestrator
   and subagent-spawning code to call the Runtime interface instead of the
   SDK directly." There is no orchestrator code in this repo. The
   orchestrator IS the Claude Agent SDK session itself, driven by the
   markdown prompts in `praxis-system-prompt.md` and `.claude/agents/*.md`.
4. **No test suite.** The task said "confirm the full existing test suite
   still passes (all 62 cases)." There are zero tests, zero test runner
   config, zero test files on any branch.

Full repo inventory (identical on every populated branch — main,
`claude/blissful-franklin-VIMiH`, `claude/plan-execute-mode-switch-zCz38`):

```
praxis-system-prompt.md
.claude/agents/{builder,planner,scout,scribe,verifier}.md
.claude/hooks/escalation-boundary.py
.claude/settings.json
.praxis/memory/.gitkeep
.gitignore
```

Other branches (`fix-pre-tool-use-hook-tRzjd`, `jolly-clarke-Gpap8`,
`loving-mendel-7qxgd`, `remove-escalation-hook-kfZ5Q`,
`review-morning-handoff-JVdUE`, `wizardly-sagan-fSJLM`,
`zealous-turing-WkWhs`) are empty.

## Why proceeding would have been wrong

"Pure refactor, behavior identical before and after" is the load-bearing
constraint of Phase A. With no orchestrator code to wrap and no tests to
verify against, executing the plan would have meant:

- inventing ~several hundred lines of net-new Python (a fictional
  orchestrator that calls the SDK, plus `runtime/base.py`, plus
  `runtime/claude_code.py`, plus a fabricated test suite),
- calling that a "refactor" though it is pure greenfield,
- declaring success against tests I wrote myself.

That is the exact scope explosion §5 and the "if you're changing what the
system does rather than how it is structured, stop" guardrail prohibit.
A real Phase A refactor presupposes a Phase 0 in which the orchestrator
exists as code. Phase 0 has not happened.

## Two reconciliations to choose from in the morning

**Option 1 — The premise is wrong, and Phase A is actually Phase 0.**
What you really want first is to *build* the minimum orchestrator in
Python: a small driver that consumes `praxis-system-prompt.md`, calls the
Claude Agent SDK in a loop, dispatches tool calls through the hook, and
spawns the markdown-defined subagents. Once that exists and has a real
test suite, *then* the Phase A runtime-abstraction refactor is meaningful
because there is something to abstract. I can do that next session if
you confirm.

**Option 2 — The orchestrator lives in another repository.**
If `LinuxAgenticClaudeOS` (referenced in `praxis-system-prompt.md` as
`WORKSPACE_ROOT`) is a separate repo that contains the actual Python
orchestrator and 62 tests, this session was pointed at the wrong repo.
Tell me which repo / branch and I'll re-run Phase A against it.

## What I touched

Only this file. No code, no config, no commits, no pushes.

— Session ended at the §10 "surface uncertainty honestly" boundary
  rather than fabricating a refactor.
