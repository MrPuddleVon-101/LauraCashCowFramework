#!/usr/bin/env bash
# Starts the API and the web app together. Ctrl-C stops both.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d backend/.venv ]; then
  echo "Creating the backend virtual environment"
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install -q --upgrade pip
  backend/.venv/bin/pip install -q fastapi "uvicorn[standard]" numpy httpx pydantic
fi
[ -d frontend/node_modules ] || (cd frontend && npm install)

backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --port 8077 &
API=$!
trap 'kill $API 2>/dev/null || true' EXIT INT TERM
sleep 2
(cd frontend && npm run dev)
