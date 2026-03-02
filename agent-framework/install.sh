#!/usr/bin/env bash
#
# Agent Framework — Install Script
#
# Usage:
#   ./install.sh              Interactive setup
#   ./install.sh --no-venv    Skip virtual environment creation
#   ./install.sh --dry-run    Show what would happen without making changes
#   ./install.sh --help       Show this help
#
set -euo pipefail

# ── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ── Defaults ────────────────────────────────────────────────────────────────
DRY_RUN=false
NO_VENV=false
VENV_DIR="venv"
MIN_PYTHON="3.10"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Parse arguments ─────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)   DRY_RUN=true; shift ;;
        --no-venv)   NO_VENV=true; shift ;;
        --venv-dir)  VENV_DIR="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: ./install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run     Show what would happen without making changes"
            echo "  --no-venv     Skip virtual environment creation"
            echo "  --venv-dir    Custom venv directory (default: venv)"
            echo "  --help        Show this help"
            exit 0
            ;;
        *) echo -e "${RED}Unknown option: $1${NC}"; exit 1 ;;
    esac
done

# ── Helpers ─────────────────────────────────────────────────────────────────
info()    { echo -e "${BLUE}ℹ${NC}  $*"; }
success() { echo -e "${GREEN}✓${NC}  $*"; }
warn()    { echo -e "${YELLOW}⚠${NC}  $*"; }
fail()    { echo -e "${RED}✗${NC}  $*"; exit 1; }
step()    { echo -e "\n${BOLD}── $* ──${NC}"; }
run() {
    if $DRY_RUN; then
        echo -e "  ${YELLOW}[dry-run]${NC} $*"
    else
        eval "$@"
    fi
}

# ── Banner ──────────────────────────────────────────────────────────────────
echo -e "${BOLD}"
echo "╔══════════════════════════════════════════╗"
echo "║       Agent Framework — Installer        ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

if $DRY_RUN; then
    warn "Dry run mode — no changes will be made"
    echo ""
fi

# ── Step 1: Python version check ───────────────────────────────────────────
step "1/6  Checking Python"

if ! command -v python3 &>/dev/null; then
    fail "python3 not found. Install Python ${MIN_PYTHON}+ first."
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
MIN_MAJOR=$(echo "$MIN_PYTHON" | cut -d. -f1)
MIN_MINOR=$(echo "$MIN_PYTHON" | cut -d. -f2)

if [[ "$PYTHON_MAJOR" -lt "$MIN_MAJOR" ]] || { [[ "$PYTHON_MAJOR" -eq "$MIN_MAJOR" ]] && [[ "$PYTHON_MINOR" -lt "$MIN_MINOR" ]]; }; then
    fail "Python ${PYTHON_VERSION} found, but ${MIN_PYTHON}+ is required."
fi

success "Python ${PYTHON_VERSION} (>= ${MIN_PYTHON})"

# ── Step 2: Virtual environment ─────────────────────────────────────────────
step "2/6  Virtual environment"

PYTHON_CMD="python3"

if $NO_VENV; then
    info "Skipping virtual environment (--no-venv)"
else
    VENV_PATH="${SCRIPT_DIR}/${VENV_DIR}"

    if [[ -d "$VENV_PATH" ]]; then
        info "Virtual environment already exists at ${VENV_DIR}/"
    else
        info "Creating virtual environment at ${VENV_DIR}/"
        run "python3 -m venv '${VENV_PATH}'"
    fi

    if ! $DRY_RUN; then
        # shellcheck disable=SC1091
        source "${VENV_PATH}/bin/activate"
        PYTHON_CMD="${VENV_PATH}/bin/python"
        success "Activated: ${VENV_PATH}"
    else
        PYTHON_CMD="${VENV_PATH}/bin/python"
        success "Would activate: ${VENV_PATH}"
    fi
fi

# ── Step 3: Install dependencies ────────────────────────────────────────────
step "3/6  Installing dependencies"

REQUIREMENTS="${SCRIPT_DIR}/requirements.txt"

if [[ ! -f "$REQUIREMENTS" ]]; then
    fail "requirements.txt not found at ${REQUIREMENTS}"
fi

info "Installing from requirements.txt..."
run "'${PYTHON_CMD}' -m pip install -q -r '${REQUIREMENTS}'"

if ! $DRY_RUN; then
    # Verify critical imports
    "${PYTHON_CMD}" -c "import anthropic" 2>/dev/null && success "anthropic SDK installed" || warn "anthropic SDK not verified"
fi

# ── Step 4: API key check ──────────────────────────────────────────────────
step "4/6  API key configuration"

if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
    MASKED="***${ANTHROPIC_API_KEY: -4}"
    success "ANTHROPIC_API_KEY is set (${MASKED})"
else
    warn "ANTHROPIC_API_KEY is not set"
    echo ""
    echo "  You need an Anthropic API key to use the agent framework."
    echo "  Get one at: https://console.anthropic.com/settings/keys"
    echo ""
    echo "  Set it with:"
    echo "    export ANTHROPIC_API_KEY='sk-ant-...'"
    echo ""
    echo "  Or add to your shell profile (~/.bashrc, ~/.zshrc):"
    echo "    echo 'export ANTHROPIC_API_KEY=\"sk-ant-...\"' >> ~/.zshrc"
    echo ""
fi

# ── Step 5: Config file ────────────────────────────────────────────────────
step "5/6  Configuration"

CONFIG_FILE="${SCRIPT_DIR}/framework/config.json"

if [[ -f "$CONFIG_FILE" ]]; then
    success "Config file exists: framework/config.json"
    info "Model: $(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['model'])" 2>/dev/null || echo 'unknown')"
else
    info "Creating default config file..."
    run "cat > '${CONFIG_FILE}' << 'CONF'
{
  \"model\": \"claude-opus-4-20250115\",
  \"max_tokens\": 8192,
  \"agent_dirs\": [\"agents\"],
  \"mcp_servers\": {
    \"agent-registry\": \"framework/mcp-servers/agent-registry\",
    \"knowledge-search\": \"framework/mcp-servers/knowledge-search\",
    \"plan-execution\": \"framework/mcp-servers/plan-execution\"
  },
  \"batch_api\": {
    \"enabled\": true,
    \"timeout_minutes\": 60,
    \"poll_interval_seconds\": 30
  }
}
CONF"
    success "Created framework/config.json"
fi

# ── Step 6: Validation ──────────────────────────────────────────────────────
step "6/6  Validation"

# Check directory structure
STACKS_DIR="${SCRIPT_DIR}/stacks"
FRAMEWORK_DIR="${SCRIPT_DIR}/framework"

[[ -d "$STACKS_DIR" ]] && success "stacks/ directory found" || warn "stacks/ directory not found"
[[ -d "$FRAMEWORK_DIR" ]] && success "framework/ directory found" || fail "framework/ directory missing"

# Count agents
AGENT_COUNT=0
if [[ -d "$STACKS_DIR" ]]; then
    AGENT_COUNT=$(find "$STACKS_DIR" -name "*.agent.md" -not -type l 2>/dev/null | wc -l | tr -d ' ')
fi
FRAMEWORK_AGENT_COUNT=$(find "$FRAMEWORK_DIR/core" -name "*.agent.md" -not -type l 2>/dev/null | wc -l | tr -d ' ')
TOTAL_AGENTS=$((AGENT_COUNT + FRAMEWORK_AGENT_COUNT))

if [[ $TOTAL_AGENTS -gt 0 ]]; then
    success "Found ${TOTAL_AGENTS} agents (${AGENT_COUNT} stack + ${FRAMEWORK_AGENT_COUNT} framework)"
else
    warn "No agents found. Create a stack first."
fi

# Run agent validator if available
VALIDATOR="${SCRIPT_DIR}/framework/scripts/validate-agent.py"
if [[ -f "$VALIDATOR" ]] && ! $DRY_RUN; then
    info "Running agent validation..."
    VALIDATION_OUTPUT=$("${PYTHON_CMD}" "$VALIDATOR" --all 2>&1 | tail -1)
    if echo "$VALIDATION_OUTPUT" | grep -q "0 errors"; then
        success "Agent validation: ${VALIDATION_OUTPUT}"
    else
        warn "Agent validation: ${VALIDATION_OUTPUT}"
    fi
fi

# ── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║         Installation Complete!            ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════╝${NC}"
echo ""

if ! $NO_VENV && ! $DRY_RUN; then
    echo -e "  Activate the venv:  ${BLUE}source ${VENV_DIR}/bin/activate${NC}"
fi

echo -e "  List agents:        ${BLUE}python framework/scripts/agent-cli.py list${NC}"
echo -e "  Run a task:         ${BLUE}python framework/scripts/agent-cli.py task \"your task\" --stack STACK${NC}"
echo -e "  Invoke an agent:    ${BLUE}python framework/scripts/agent-cli.py invoke AGENT \"task\"${NC}"
echo -e "  Execute a plan:     ${BLUE}python framework/scripts/agent-cli.py plan PLAN.json --mode batch${NC}"
echo ""

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    echo -e "  ${YELLOW}Remember to set ANTHROPIC_API_KEY before running agents.${NC}"
    echo ""
fi
