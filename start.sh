#!/usr/bin/env bash
set -e

# ── Colors ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ── Config ─────────────────────────────────────────────────────────────────────
# Read HOST from .env, default to 0.0.0.0
if [ -f ".env" ]; then
    HOST="$(grep -m1 '^HOST=' .env | cut -d= -f2-)"
fi
HOST="${HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
CELERY_WORKER="${CELERY_WORKER:-1}"   # set to 0 to skip
PROD="${PROD:-0}"                     # set to 1 for production frontend build

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ── Cleanup ─────────────────────────────────────────────────────────────────────
PIDS=()
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait "${PIDS[@]}" 2>/dev/null || true
    echo -e "${GREEN}All processes stopped.${NC}"
}
trap cleanup EXIT INT TERM

# ── Checks ─────────────────────────────────────────────────────────────────────
command -v python3 >/dev/null 2>&1 || { echo -e "${RED}python3 not found${NC}"; exit 1; }
command -v node    >/dev/null 2>&1 || { echo -e "${RED}node not found${NC}";    exit 1; }

if [ ! -d ".venv" ]; then
    echo -e "${RED}No .venv found — run: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt${NC}"
    exit 1
fi

if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}Installing frontend dependencies...${NC}"
    (cd frontend && npm install)
fi

# ── Redis ──────────────────────────────────────────────────────────────────────
if ! redis-cli ping >/dev/null 2>&1; then
    echo -e "${YELLOW}Starting Redis...${NC}"
    redis-server --daemonize yes
    sleep 1
    redis-cli ping >/dev/null 2>&1 || { echo -e "${RED}Failed to start Redis${NC}"; exit 1; }
fi
echo -e "${GREEN}Redis:   ok${NC}"

# ── Backend (FastAPI) ──────────────────────────────────────────────────────────
echo -e "${GREEN}Starting backend on ${HOST}:${BACKEND_PORT}${NC}"
source .venv/bin/activate
uvicorn app.main:app --host "$HOST" --port "$BACKEND_PORT" &
PIDS+=($!)
sleep 1

# ── Celery worker ──────────────────────────────────────────────────────────────
if [ "$CELERY_WORKER" = "1" ]; then
    echo -e "${GREEN}Starting Celery worker${NC}"
    celery -A app.tasks.celery_app worker --loglevel=warning &
    PIDS+=($!)
fi

# ── Frontend ────────────────────────────────────────────────────────────────────
if [ "$PROD" = "1" ]; then
    echo -e "${YELLOW}Building frontend for production...${NC}"
    (cd frontend && npm run build)
    echo -e "${GREEN}Serving frontend from FastAPI on ${HOST}:${BACKEND_PORT}${NC}"
    DASHBOARD_HOST="$HOST"
    DASHBOARD_PORT="$BACKEND_PORT"
else
    echo -e "${GREEN}Starting frontend (dev) on :${FRONTEND_PORT}${NC}"
    (cd frontend && npm run dev -- --port "$FRONTEND_PORT") &
    PIDS+=($!)
    DASHBOARD_HOST="localhost"
    DASHBOARD_PORT="$FRONTEND_PORT"
fi

# ── Ready ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Backend:   http://${HOST}:${BACKEND_PORT}${NC}"
echo -e "${GREEN}  API docs:  http://${HOST}:${BACKEND_PORT}/docs${NC}"
echo -e "${GREEN}  Dashboard: http://${DASHBOARD_HOST}:${DASHBOARD_PORT}${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop all services.${NC}"
echo ""

# ── Wait ───────────────────────────────────────────────────────────────────────
wait
