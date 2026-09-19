# github.com/Shran21

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from panel.app import app, bridge, csrf_ok, page, set_cookie
from panel.auditlog import record
from panel.logfiles import CHANNELS, files_of, tail
from rebsgo.vocabulary.pilot import ServerRoles


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request, channel: str = "server", file: int = 0,
                    q: str = "", n: int = 200, only: str = "",
                    notice: str = "", error: str = ""):
    if channel not in CHANNELS:
        channel = "server"
    if only not in ("errors", "all"):
        only = "errors" if channel == "error" else "all"
    sheet = tail(channel, index=file, query=q, limit=n, only=only)
    response = page(request, "logs.html",
                    channel=channel, channels=list(CHANNELS),
                    files=files_of(channel), file_index=int(file),
                    q=q, n=int(n), only=only,
                    lines=sheet["lines"], truncated=sheet["truncated"],
                    log_state=bridge.log_state(),
                    may_turn=request.state.session.wears(ServerRoles.Developer),
                    notice=notice, error=error)
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
