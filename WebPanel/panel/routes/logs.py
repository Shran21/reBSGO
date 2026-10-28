# github.com/Shran21

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

import urllib.parse

from panel.app import app, bridge, csrf_ok, page, set_cookie
from panel.auditlog import record
from panel.logfiles import CHANNELS, DELETABLE, files_of, purge_old, remove, tail
from rebsgo.vocabulary.pilot import ServerRoles


def _size(count: int) -> str:
    return f"{count / (1024 * 1024):.1f} MB" if count >= 1024 * 1024 else f"{count / 1024:.0f} kB"


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request, channel: str = "server", file: int = 0,
                    q: str = "", n: int = 200, only: str = "",
                    notice: str = "", error: str = "", detail: str = ""):
    if channel not in CHANNELS:
        channel = "server"
    if only not in ("errors", "all"):
        only = "errors" if channel == "error" else "all"
    sheet = tail(channel, index=file, query=q, limit=n, only=only)
    files = files_of(channel)
    for entry in files:
        entry["size_text"] = _size(entry["size"])
    old = [entry for entry in files if entry["index"] != 0]
    response = page(request, "logs.html",
                    channel=channel, channels=list(CHANNELS),
                    files=files, file_index=int(file),
                    q=q, n=int(n), only=only,
                    lines=sheet["lines"], truncated=sheet["truncated"],
                    log_state=bridge.log_state(),
                    may_turn=request.state.session.wears(ServerRoles.Developer),
                    may_delete=channel in DELETABLE,
                    old_count=len(old), old_size=_size(sum(entry["size"] for entry in old)),
                    notice=notice, error=error, detail=detail)
    if channel == "error":
        from panel.live import error_state
        set_cookie(request, response, "panel_errseen", str(error_state()["total"]),
                   max_age=365 * 24 * 3600, httponly=True)
    return response


@app.get("/logs/tail")
async def logs_tail(request: Request, channel: str = "server", file: int = 0,
                    q: str = "", n: int = 200, only: str = "all"):
    if channel not in CHANNELS:
        return JSONResponse({"lines": [], "truncated": False})
    return JSONResponse(tail(channel, index=file, query=q, limit=n,
                             only=only if only in ("errors", "all") else "all"))


@app.post("/logs/level")
async def logs_level(request: Request):
    form = await request.form()
    session = request.state.session
    back = "/logs?channel=" + str(form.get("channel", "server"))
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse(f"{back}&error=csrf.failed", status_code=303)
    if not session.wears(ServerRoles.Developer):
        return RedirectResponse(f"{back}&error=logs.denied", status_code=303)
    level = str(form.get("level", ""))
    area = str(form.get("area", "")) or None
    answer = bridge.set_log(level, area)
    record(session.name, "log.volume", target=f"{level}" + (f" area={area}" if area else ""),
           outcome="down" if answer is None else ("ok" if answer.get("ok") else "refused"))
    if answer is None:
        return RedirectResponse(f"{back}&error=logs.down", status_code=303)
    if not answer.get("ok"):
        return RedirectResponse(f"{back}&error=logs.refused", status_code=303)
    return RedirectResponse(f"{back}&notice=logs.turned", status_code=303)


async def _log_form(request: Request):
    form = await request.form()
    channel = str(form.get("channel", ""))
    if channel not in CHANNELS:
        channel = "server"
    back = "/logs?" + urllib.parse.urlencode({"channel": channel})
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return form, channel, back, "csrf.failed"
    if not session.wears(ServerRoles.Developer):
        return form, channel, back, "logs.delete.denied"
    if channel not in DELETABLE:
        return form, channel, back, "logs.delete.kept"
    return form, channel, back, ""


@app.post("/logs/delete")
async def logs_delete(request: Request):
    form, channel, back, refusal = await _log_form(request)
    if refusal:
        return RedirectResponse(f"{back}&error={refusal}", status_code=303)
    name = str(form.get("name", ""))
    try:
        done, freed = remove(channel, name)
    except OSError:
        done, freed = "", 0
    session = request.state.session
    record(session.name, "log.delete", target=f"{channel}/{name}", outcome=done or "refused")
    if not done:
        return RedirectResponse(f"{back}&error=logs.delete.failed", status_code=303)
    return RedirectResponse(f"{back}&" + urllib.parse.urlencode(
        {"notice": f"logs.{done}", "detail": f"{name} · {_size(freed)}"}), status_code=303)


@app.post("/logs/purge")
async def logs_purge(request: Request):
    form, channel, back, refusal = await _log_form(request)
    if refusal:
        return RedirectResponse(f"{back}&error={refusal}", status_code=303)
    files, freed = purge_old(channel)
    record(request.state.session.name, "log.purge", target=channel,
           outcome=f"files={files} bytes={freed}")
    return RedirectResponse(f"{back}&" + urllib.parse.urlencode(
        {"notice": "logs.purged", "detail": f"{files} · {_size(freed)}"}), status_code=303)
