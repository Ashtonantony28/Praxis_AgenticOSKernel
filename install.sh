#!/usr/bin/env bash
# Praxis — One-command installer
# Works on Ubuntu 24 and WSL2.
# Usage: bash install.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { printf "${CYAN}[praxis]${NC} %s\n" "$1"; }
ok()    { printf "${GREEN}[  ok  ]${NC} %s\n" "$1"; }
warn()  { printf "${YELLOW}[ warn ]${NC} %s\n" "$1"; }
fail()  { printf "${RED}[error ]${NC} %s\n" "$1"; exit 1; }

# ─── Python check ──────────────────────────────────────────────────
info "Checking Python..."

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    fail "Python not found. Install Python 3.10+ first:
  Ubuntu/WSL:  sudo apt install python3 python3-pip python3-venv
  macOS:       brew install python@3.12"
fi

PY_VERSION=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$("$PYTHON" -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$("$PYTHON" -c 'import sys; print(sys.version_info.minor)')

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    fail "Python $PY_VERSION found, but 3.10+ is required.
  Ubuntu/WSL:  sudo apt install python3.12
  macOS:       brew install python@3.12"
fi

ok "Python $PY_VERSION"

# ─── Git check ──────────────────────────────────────────────────────
info "Checking git..."

if ! command -v git &>/dev/null; then
    fail "git not found. Install it:
  Ubuntu/WSL:  sudo apt install git
  macOS:       xcode-select --install"
fi

ok "git $(git --version | cut -d' ' -f3)"

# ─── Virtual environment ───────────────────────────────────────────
info "Setting up virtual environment..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    "$PYTHON" -m venv "$VENV_DIR"
    ok "Created .venv"
else
    ok ".venv already exists"
fi

# Activate
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ─── Install core package ──────────────────────────────────────────
info "Installing praxis..."

pip install -e "$SCRIPT_DIR" --quiet 2>&1 | tail -1 || true
ok "praxis core installed (anthropic, pyyaml)"

# ─── Optional extras prompt ────────────────────────────────────────
info "Installing dev dependencies (pytest)..."
pip install -e "$SCRIPT_DIR[dev]" --quiet 2>&1 | tail -1 || true
ok "pytest installed"

# ─── Create workspace directories ──────────────────────────────────
info "Creating workspace directories..."

mkdir -p "$SCRIPT_DIR/.praxis/memory"
mkdir -p "$SCRIPT_DIR/.praxis/queue/results"
mkdir -p "$SCRIPT_DIR/.praxis/queue/checkpoints"
mkdir -p "$SCRIPT_DIR/.praxis/staging/drafts"
mkdir -p "$SCRIPT_DIR/.praxis/staging/events"
mkdir -p "$SCRIPT_DIR/.praxis/logs"
ok "Workspace directories ready"

# ─── .env file ──────────────────────────────────────────────────────
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    ok "Created .env from .env.example — edit it to add your credentials"
else
    ok ".env already exists"
fi

# ─── Optional tools check ──────────────────────────────────────────
echo ""
info "Checking optional tools..."

MISSING_OPTIONAL=()

if command -v gh &>/dev/null; then
    ok "gh CLI (GitHub integration)"
else
    warn "gh CLI not found — GitHub integration will be unavailable"
    MISSING_OPTIONAL+=("gh")
fi

if "$PYTHON" -c "import coverage" &>/dev/null 2>&1; then
    ok "coverage (code analysis)"
else
    warn "coverage not found — install with: pip install praxis[analyze]"
    MISSING_OPTIONAL+=("coverage")
fi

if command -v radon &>/dev/null; then
    ok "radon (complexity analysis)"
else
    warn "radon not found — install with: pip install praxis[analyze]"
    MISSING_OPTIONAL+=("radon")
fi

if command -v pylint &>/dev/null; then
    ok "pylint (linting)"
else
    warn "pylint not found — install with: pip install praxis[analyze]"
    MISSING_OPTIONAL+=("pylint")
fi

if command -v pip-audit &>/dev/null; then
    ok "pip-audit (vulnerability scan)"
else
    warn "pip-audit not found — install with: pip install praxis[analyze]"
    MISSING_OPTIONAL+=("pip-audit")
fi

# ─── Verify installation ───────────────────────────────────────────
echo ""
info "Verifying installation..."

if "$PYTHON" -c "import praxis; import anthropic; import yaml" 2>/dev/null; then
    ok "All core imports successful"
else
    fail "Import check failed — check the output above for errors"
fi

# ─── Summary ────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf "${GREEN}Praxis installed successfully.${NC}\n"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo ""
echo "  1. Edit .env and add your auth credentials:"
echo "     - CLAUDE_CODE_OAUTH_TOKEN (subscription) or"
echo "     - ANTHROPIC_API_KEY (pay-per-token)"
echo ""
echo "  2. Activate the virtual environment:"
echo "     source .venv/bin/activate"
echo ""
echo "  3. Run Praxis:"
echo "     python -m praxis \"hello, what can you do?\""
echo ""

if [ ${#MISSING_OPTIONAL[@]} -gt 0 ]; then
    echo "  Optional extras:"
    echo "     pip install -e .[analyze]    # code analysis tools"
    echo "     pip install -e .[local]      # local model support (Ollama)"
    echo "     pip install -e .[cloud]      # cloud model support (OpenAI)"
    echo "     pip install -e .[all]        # everything"
    echo ""
fi

echo "  Run tests:"
echo "     python -m pytest tests/ -v"
echo ""
