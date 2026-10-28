#!/bin/sh
# github.com/Shran21
cd "$(dirname "$0")" || exit 1
ENV_HOST=${PANEL_HOST:-}; ENV_PORT=${PANEL_PORT:-}
[ -f panel.env ] && . ./panel.env
[ -n "$ENV_HOST" ] && PANEL_HOST=$ENV_HOST
[ -n "$ENV_PORT" ] && PANEL_PORT=$ENV_PORT
PY=./venv/bin/python
[ -x "$PY" ] || PY=python3
exec "$PY" -m uvicorn panel.app:app \
    --host "${PANEL_HOST:-0.0.0.0}" \
    --port "${PANEL_PORT:-27055}" \
    --log-level warning
