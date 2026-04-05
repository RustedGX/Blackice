#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# run_paper_trader.sh
#
# Launches the Blackice paper trading agent with $20,000 starting balance.
# Starts the FastAPI backend if it is not already running.
#
# Usage:
#   bash agents/run_paper_trader.sh                   # default (5-min cycles)
#   bash agents/run_paper_trader.sh --cycles 5         # 5 cycles then exit
#   bash agents/run_paper_trader.sh --interval 60      # 1-min cycles
#   bash agents/run_paper_trader.sh --dry-run          # no trades placed
#   bash agents/run_paper_trader.sh --balance 50000    # custom balance
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_URL="${BLACKICE_API:-http://localhost:8000}"
BACKEND_PID_FILE="${REPO_DIR}/.backend.pid"
VENV="${REPO_DIR}/.venv"

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Activate virtualenv if present ───────────────────────────────────────────
if [[ -f "${VENV}/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "${VENV}/bin/activate"
    info "Activated virtualenv: ${VENV}"
fi

# ── Check Python deps ─────────────────────────────────────────────────────────
python -c "import httpx" 2>/dev/null || {
    warn "httpx not found — installing …"
    pip install httpx --quiet
}

# ── Check if backend is running ───────────────────────────────────────────────
is_backend_up() {
    curl -sf "${BACKEND_URL}/health" >/dev/null 2>&1
}

start_backend() {
    info "Starting Blackice backend on port 8000 …"
    cd "${REPO_DIR}"
    PYTHONPATH="${REPO_DIR}" \
        uvicorn backend.main:app --host 0.0.0.0 --port 8000 \
        --log-level warning \
        &
    local pid=$!
    echo "${pid}" > "${BACKEND_PID_FILE}"
    info "Backend PID: ${pid}"

    # Wait up to 15 seconds for the backend to become healthy
    for i in $(seq 1 15); do
        sleep 1
        if is_backend_up; then
            info "Backend is healthy (${i}s)."
            return 0
        fi
    done
    error "Backend did not become healthy within 15 seconds."
}

if is_backend_up; then
    info "Backend already running at ${BACKEND_URL}"
else
    start_backend
fi

# ── Ensure ANTHROPIC_API_KEY is set ──────────────────────────────────────────
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
    warn "ANTHROPIC_API_KEY is not set. Claude signals will fail."
    warn "Export the key: export ANTHROPIC_API_KEY=sk-ant-..."
fi

# ── Run the agent ─────────────────────────────────────────────────────────────
info "Starting Paper Trading Agent …"
info "  Balance  : \$20,000"
info "  Log file : ${REPO_DIR}/agents/trading_log.jsonl"
info "  Report   : ${REPO_DIR}/agents/session_report.json"
echo ""

cd "${REPO_DIR}"
PYTHONPATH="${REPO_DIR}" python -m agents.paper_trader \
    --balance 20000 \
    --api "${BACKEND_URL}" \
    "$@"

# ── Cleanup: stop backend if we started it ────────────────────────────────────
if [[ -f "${BACKEND_PID_FILE}" ]]; then
    BG_PID="$(cat "${BACKEND_PID_FILE}")"
    if kill -0 "${BG_PID}" 2>/dev/null; then
        info "Stopping backend (PID ${BG_PID}) …"
        kill "${BG_PID}"
    fi
    rm -f "${BACKEND_PID_FILE}"
fi
