# github.com/Shran21

from __future__ import annotations

import asyncio
import collections
import json
import os
import subprocess
import threading
import time

import psutil
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from panel.app import app, bridge, page
from panel.bridge import uptime_seconds
from panel.settings import ROOT

_STARTED = time.time()

_SAMPLE_SECONDS = 15
_KEEP_SECONDS = 24 * 3600
_POINTS = 240
_SPANS = {"1h": 3600, "24h": _KEEP_SECONDS}
_HISTORY_FILE = ROOT / "logs" / "monitor_history.json"

_history: collections.deque = collections.deque(maxlen=_KEEP_SECONDS // _SAMPLE_SECONDS)
_history_lock = threading.Lock()


def _load_history() -> None:
    try:
        rows = json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    floor = time.time() - _KEEP_SECONDS
    with _history_lock:
        for row in rows:
            if isinstance(row, dict) and row.get("t", 0) >= floor:
                _history.append(row)


def _persist() -> None:
    with _history_lock:
        rows = list(_history)
    try:
        _HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        scratch = _HISTORY_FILE.with_suffix(".tmp")
        scratch.write_text(json.dumps(rows, separators=(",", ":")), encoding="utf-8")
        os.replace(scratch, _HISTORY_FILE)
    except OSError:
        pass


def _sampler() -> None:
    taken = 0
    while True:
        try:
            cpu = psutil.cpu_percent(interval=0.2)
            memory = psutil.virtual_memory()
            live = bridge.status()
            online = None if live is None else len(live.get("online", []))
            with _history_lock:
                _history.append({"t": int(time.time()), "cpu": cpu,
                                 "mem": memory.percent, "online": online})
            taken += 1
            if taken % 20 == 0:
                _persist()
        except Exception:
            pass
        time.sleep(_SAMPLE_SECONDS)


_load_history()
threading.Thread(target=_sampler, name="panel-monitor-history", daemon=True).start()


def _rows_within(span: str) -> list:
    floor = time.time() - _SPANS.get(span, _SPANS["1h"])
    with _history_lock:
        return [row for row in _history if row.get("t", 0) >= floor]


def _condense(values: list, points: int = _POINTS) -> list:
    if len(values) <= points:
        return values
    size = len(values) / points
    out = []
    for i in range(points):
        chunk = values[int(i * size):int((i + 1) * size)] or [values[-1]]
        out.append(round(sum(chunk) / len(chunk), 1))
    return out


def _history_slice(span: str = "1h") -> dict:
    span = span if span in _SPANS else "1h"
    rows = _rows_within(span)
    return {
        "span": span,
        "cpu": _condense([row["cpu"] for row in rows]),
        "mem": _condense([row["mem"] for row in rows]),
        "online": _condense([row["online"] if row["online"] is not None else 0
                             for row in rows]),
    }


def online_history(span: str = "1h") -> list:
    return _history_slice(span)["online"]


def _service_pid(unit: str):
    try:
        out = subprocess.run(["systemctl", "show", "-p", "MainPID", "--value", unit],
                             capture_output=True, text=True, timeout=3)
        pid = int(out.stdout.strip() or 0)
        return pid or None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def _process_slice(unit: str) -> dict:
    pid = _service_pid(unit)
    if not pid:
        return {"alive": False}
    try:
        proc = psutil.Process(pid)
        with proc.oneshot():
            return {"alive": True, "pid": pid,
                    "rss_mb": round(proc.memory_info().rss / (1024 * 1024), 1),
                    "cpu": proc.cpu_percent(interval=0.1),
                    "threads": proc.num_threads()}
    except psutil.Error:
        return {"alive": False}


def _machine() -> dict:
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    net = psutil.net_io_counters()
    load1, load5, load15 = psutil.getloadavg()
    return {
        "cpu": psutil.cpu_percent(interval=0.2),
        "cores": psutil.cpu_count() or 1,
        "load": [round(load1, 2), round(load5, 2), round(load15, 2)],
        "mem_used_mb": round(memory.used / (1024 * 1024)),
        "mem_total_mb": round(memory.total / (1024 * 1024)),
        "mem_pct": memory.percent,
        "disk_used_gb": round(disk.used / (1024 ** 3), 1),
        "disk_total_gb": round(disk.total / (1024 ** 3), 1),
        "disk_pct": disk.percent,
        "net_sent_mb": round(net.bytes_sent / (1024 * 1024), 1),
        "net_recv_mb": round(net.bytes_recv / (1024 * 1024), 1),
    }


def _snapshot(span: str = "1h") -> dict:
    from panel.sectors import sector_name
    live = bridge.status()
    if live:
        live["uptime_s"] = uptime_seconds(live)
    sectors = bridge.sectors() if live else None
    busiest = []
    if sectors:
        rows = [row for row in sectors.get("sectors", []) if "total" in row]
        rows.sort(key=lambda row: (row.get("players", 0), row.get("total", 0)),
                  reverse=True)
        busiest = [{"id": row["id"], "name": sector_name(row["id"]),
                    "players": row.get("players", 0),
                    "total": row.get("total", 0), "npcs": row.get("npcs", 0)}
                   for row in rows[:8]]
    return {
        "machine": _machine(),
        "game": _process_slice("bsgo"),
        "panel": _process_slice("rebsgo-panel"),
        "live": live,
        "busiest": busiest,
        "history": _history_slice(span),
    }


@app.get("/monitor", response_class=HTMLResponse)
async def monitor_page(request: Request, span: str = "1h"):
    snap = await run_in_threadpool(_snapshot, span)
    return page(request, "monitor.html", snap=snap, span=snap["history"]["span"])


@app.get("/monitor/data")
async def monitor_data(request: Request, span: str = "1h"):
    return JSONResponse(await run_in_threadpool(_snapshot, span))


@app.get("/monitor/events")
async def monitor_events(request: Request, span: str = "1h"):
    once = "once" in request.query_params

    async def stream():
        yield "retry: 3000\n\n"
        while True:
            snap = await run_in_threadpool(_snapshot, span)
            yield "event: snapshot\ndata: " + json.dumps(snap) + "\n\n"
            if once:
                return
            for _ in range(5):
                if await request.is_disconnected():
                    return
                await asyncio.sleep(1)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
