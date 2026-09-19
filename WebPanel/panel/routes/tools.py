# github.com/Shran21

from __future__ import annotations

import threading

from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from panel import backups, gamedata
from panel.app import app, bridge, csrf_ok, page
from panel.auditlog import record
from rebsgo.vocabulary.pilot import ServerRoles


@app.get("/tools", response_class=HTMLResponse)
async def tools_page(request: Request, q: str = "", notice: str = "", error: str = ""):
    from panel import restarter
    session = request.state.session
    return page(request, "tools.html",
                maintenance=bridge.maintenance(),
                backups=backups.full_backups(),
                backup_busy=backups.busy.locked(),
                results=gamedata.search(q) if q else [],
                q=q,
                restart_plan=restarter.status(),
                may_operate=session.wears(ServerRoles.Developer),
                may_console=session.can_console,
                notice=notice, error=error)


@app.post("/server/restart-plan")
async def restart_plan(request: Request):
    from panel import restarter
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse("/tools?error=csrf.failed", status_code=303)
    if not session.wears(ServerRoles.Developer):
        return RedirectResponse("/tools?error=sectors.denied", status_code=303)
    try:
        minutes = int(str(form.get("minutes", "10")))
    except ValueError:
        minutes = 10
    armed = restarter.schedule(
        minutes, session.name,
        lambda line: bridge.console(session.pilot_id, line))
    key = "tools.restart.armed" if armed else "tools.restart.taken"
    return RedirectResponse(f"/tools?notice={key}", status_code=303)


@app.post("/server/restart-cancel")
async def restart_cancel(request: Request):
    from panel import restarter
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse("/tools?error=csrf.failed", status_code=303)
    if not session.wears(ServerRoles.Developer):
        return RedirectResponse("/tools?error=sectors.denied", status_code=303)
    restarter.cancel(session.name,
                     lambda line: bridge.console(session.pilot_id, line))
    return RedirectResponse("/tools?notice=tools.restart.cancelled", status_code=303)


@app.post("/tools/broadcast")
async def broadcast(request: Request):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse("/tools?error=csrf.failed", status_code=303)
    if not session.can_console:
        return RedirectResponse("/tools?error=sectors.denied", status_code=303)
    message = str(form.get("message", "")).strip()[:200]
    if not message:
        return RedirectResponse("/tools", status_code=303)
    quoted = '"' + message.replace('"', "'") + '"'
    answer = bridge.console(session.pilot_id, f"notice.all {quoted}")
    record(session.name, "broadcast", target=message,
           outcome="down" if answer is None else "sent")
    if answer is None:
        return RedirectResponse("/tools?error=sectors.down", status_code=303)
    return RedirectResponse("/tools?notice=tools.broadcast.sent", status_code=303)


@app.post("/tools/samehost")
async def same_host_report(request: Request):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse("/tools?error=csrf.failed", status_code=303)
    if not session.can_console:
        return RedirectResponse("/tools?error=sectors.denied", status_code=303)
    answer = bridge.console(session.pilot_id, "pilot.address")
    if answer is None:
        return RedirectResponse("/tools?error=sectors.down", status_code=303)
    lines = answer.get("lines") or ["-"]
    return page(request, "tools.html",
                maintenance=bridge.maintenance(), backups=backups.full_backups(),
                backup_busy=backups.busy.locked(), results=[], q="",
                samehost="\n".join(lines),
                may_operate=session.wears(ServerRoles.Developer),
                may_console=session.can_console, notice="", error="")


@app.post("/tools/maintenance")
async def maintenance_toggle(request: Request):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse("/tools?error=csrf.failed", status_code=303)
    if not session.wears(ServerRoles.Developer):
        return RedirectResponse("/tools?error=sectors.denied", status_code=303)
    turn_on = str(form.get("on", "")) == "1"
    message = str(form.get("message", "")).strip()[:200]
    answer = bridge.set_maintenance(turn_on, message)
    record(session.name, "maintenance", target="on" if turn_on else "off",
           outcome="down" if answer is None else message)
    if answer is None:
        return RedirectResponse("/tools?error=sectors.down", status_code=303)
    key = "tools.maintenance.on" if turn_on else "tools.maintenance.off"
    return RedirectResponse(f"/tools?notice={key}", status_code=303)


@app.get("/tools/backup/{name}")
async def backup_download(request: Request, name: str):
    session = request.state.session
    if not session.wears(ServerRoles.Developer):
        return RedirectResponse("/tools?error=sectors.denied", status_code=303)
    listed = {entry["name"] for entry in backups.full_backups()}
    if name not in listed:
        return RedirectResponse("/tools?error=tools.backup.gone", status_code=303)
    record(session.name, "backup.download", target=name)
    return FileResponse(backups.backup_dir() / name, filename=name,
                        media_type="application/gzip")


@app.post("/tools/backup")
async def backup_now(request: Request):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse("/tools?error=csrf.failed", status_code=303)
    if not session.wears(ServerRoles.Developer):
        return RedirectResponse("/tools?error=sectors.denied", status_code=303)
    if not backups.busy.acquire(blocking=False):
        return RedirectResponse("/tools?error=tools.backup.busy", status_code=303)
    threading.Thread(target=backups.run_full, args=(session.name,),
                     name="panel-backup", daemon=True).start()
    return RedirectResponse("/tools?notice=tools.backup.started", status_code=303)
