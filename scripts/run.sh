#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3101}"
PYTHON="$ROOT/app/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo "Project .venv missing; install app/requirements-product.lock.txt into app/.venv first." >&2
  exit 1
fi
if [[ ! -f "$ROOT/app/frontend/node_modules/next/dist/bin/next" ]]; then
  echo "Frontend node_modules missing; run pnpm install --frozen-lockfile in app/frontend first." >&2
  exit 1
fi
if [[ ! -f "$ROOT/app/frontend/.next/BUILD_ID" ]]; then
  echo "Frontend production build missing; run pnpm build in app/frontend first." >&2
  exit 1
fi

mkdir -p "$ROOT/reports"
unset OPENAI_API_KEY TOAPIS_API_KEY TAVILY_API_KEY LONDON_TAVILY_API_KEY \
  LONDON_JEV_API_KEY LONDON_EPC_TOKEN LONDON_NOTIFICATION_URL
export LONDON_TAVILY_ENABLED="0" LONDON_JEV_SHADOW_ENABLED="0" \
  LONDON_JEV_ROUTING_ENABLED="0"
export NEXT_PUBLIC_MARKET_API_URL="http://127.0.0.1:${BACKEND_PORT}/api/market"
export NEXT_PUBLIC_AGENT_OS_URL="http://127.0.0.1:${BACKEND_PORT}"
(
  cd "$ROOT/app"
  exec "$PYTHON" -m london_product.offline_runtime --port "$BACKEND_PORT" --frontend-port "$FRONTEND_PORT"
) >"$ROOT/reports/offline-backend.out.log" 2>"$ROOT/reports/offline-backend.err.log" &
BACK_PID=$!
(
  cd "$ROOT/app/frontend"
  exec node node_modules/next/dist/bin/next start -p "$FRONTEND_PORT" -H 127.0.0.1
) >"$ROOT/reports/offline-frontend.out.log" 2>"$ROOT/reports/offline-frontend.err.log" &
FRONT_PID=$!
cleanup() { kill "$BACK_PID" "$FRONT_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

for _ in $(seq 1 45); do
  if curl --fail --silent "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null \
    && curl --fail --silent "http://127.0.0.1:${FRONTEND_PORT}/ask" >/dev/null; then
    echo "Offline product ready: http://127.0.0.1:${FRONTEND_PORT}/ask (API ${BACKEND_PORT})"
    wait "$BACK_PID" "$FRONT_PID"
  fi
  sleep 1
done
echo "Offline product did not become ready; inspect reports/offline-*.log." >&2
exit 1
