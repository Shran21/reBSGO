# github.com/Shran21

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
import time

from fastapi import Request
from fastapi.responses import StreamingResponse

from panel.app import app, bridge
from panel.logfiles import CHANNELS, count_errors

_PULSE_SECONDS = 3
_TICK_SECONDS = 10

_state = {"version": 0, "log_version": 0, "changed": [],
          "errors_total": 0, "errors_size": 0, "error_last_at": 0}
_lock = threading.Lock()
_ERROR_LOG = CHANNELS.get("error")


def _errors_between(start: int, end: int) -> int:
    try:
        with open(_ERROR_LOG, "rb") as reader:
            reader.seek(start)
            raw = reader.read(end - start)
    except OSError:
        return 0
    return count_errors(raw.decode("utf-8", errors="replace"))


def _watch_errors() -> None:
    if _ERROR_LOG is None:
        return
    try:
        size = os.stat(_ERROR_LOG).st_size
    except OSError:
        return
    seen = _state["errors_size"]
    if size < seen:
        seen = 0
    if size > seen:
        fresh = _errors_between(seen, size)
        if fresh:
            _state["errors_total"] += fresh
            _state["error_last_at"] = int(time.time())
    _state["errors_size"] = size


def error_state() -> dict:
    with _lock:
        return {"total": _state["errors_total"], "last_at": _state["error_last_at"]}


def _signature() -> str:
    status = bridge.status()
    if not status:
        return "down"
    online = sorted((str(p.get("id")), str(p.get("sector"))) for p in status.get("online", []))
    seed = json.dumps([online, status.get("sectors")], sort_keys=True, default=str)
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()


def _log_sizes() -> dict:
    sizes = {}
    for name, path in CHANNELS.items():
        try:
            sizes[name] = os.stat(path).st_size
        except OSError:
            sizes[name] = -1
    return sizes


def _pulse() -> None:
    last_signature = None
    last_logs: dict = {}
    while True:
        try:
            signature = _signature()
            logs = _log_sizes()
            with _lock:
                _watch_errors()
                if signature != last_signature:
                    _state["version"] += 1
                    last_signature = signature
                if last_logs:
                    changed = [name for name, size in logs.items() if last_logs.get(name) != size]
                    if changed:
                        _state["log_version"] += 1
                        _state["changed"] = changed
                last_logs = logs
        except Exception:
            pass
        time.sleep(_PULSE_SECONDS)


threading.Thread(target=_pulse, name="panel-pulse", daemon=True).start()


@app.get("/events")
async def events(request: Request):
    once = request.query_params.get("once") is not None

    async def stream():
        with _lock:
            seen, seen_logs = _state["version"], _state["log_version"]
        yield f"retry: 3000\nevent: hello\ndata: {seen}\n\n"
        if once:
            return
        last_tick = time.monotonic()
        while True:
            if await request.is_disconnected():
                return
            await asyncio.sleep(1)
            with _lock:
                version = _state["version"]
                log_version = _state["log_version"]
                changed = list(_state["changed"])
            if version != seen:
                seen = version
                last_tick = time.monotonic()
                yield f"event: change\ndata: {version}\n\n"
            if log_version != seen_logs:
                seen_logs = log_version
                yield "event: logs\ndata: " + json.dumps(changed) + "\n\n"
            if time.monotonic() - last_tick >= _TICK_SECONDS:
                last_tick = time.monotonic()
                yield f"event: tick\ndata: {int(time.time())}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
