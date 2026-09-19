# github.com/Shran21

from __future__ import annotations

import subprocess
import time

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from panel.app import app, bridge, csrf_ok, page
from panel.auditlog import record
from panel.policy import PolicySealed, read_policy, sealed, write_policy
from panel.sectors import SECTOR_NAMES, beacon_allowed, outpost_allowed, sector_name
from rebsgo.vocabulary.pilot import ServerRoles


def _may_operate(session) -> bool:
    return session.wears(ServerRoles.Developer)


_SECTOR_ORDERS = {
    "id": lambda row: row["id"],
    "name": lambda row: row["name"].lower(),
    "players": lambda row: row.get("players") or 0,
    "npcs": lambda row: row.get("npcs") or 0,
    "asteroids": lambda row: row.get("asteroids") or 0,
    "total": lambda row: row.get("total") or 0,
}


@app.get("/sectors", response_class=HTMLResponse)
async def sectors_page(request: Request, sort: str = "name", desc: int = 0,
                       notice: str = "", error: str = "", detail: str = ""):
    live = bridge.sectors()
    by_id = {row.get("id"): row for row in (live or {}).get("sectors", [])}
    policy = read_policy()
    rows = []
    for sector_id in sorted(SECTOR_NAMES):
        row = dict(by_id.get(sector_id) or {})
        row["id"] = sector_id
        row["name"] = sector_name(sector_id)
        row["disabled"] = sector_id in policy["disabled"]
        row["limit"] = policy["limits"].get(sector_id, "")
        row["op_colonial_may"], row["op_cylon_may"] = outpost_allowed(sector_id)
        row["beacon_colonial_may"], row["beacon_cylon_may"] = beacon_allowed(sector_id)
        rows.append(row)
    if sort not in _SECTOR_ORDERS:
        sort = "name"
    rows.sort(key=_SECTOR_ORDERS[sort], reverse=bool(desc))
    return page(request, "sectors.html",
                rows=rows, live=live is not None,
                sort=sort, desc=int(bool(desc)),
                may_operate=_may_operate(request.state.session),
                sealed=sealed(), notice=notice, error=error, detail=detail)


@app.post("/sectors/policy")
async def save_policy(request: Request):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse("/sectors?error=csrf.failed", status_code=303)
    if not _may_operate(session):
        return RedirectResponse("/sectors?error=sectors.denied", status_code=303)
    disabled = set()
    limits = {}
    for sector_id in SECTOR_NAMES:
        if form.get(f"disabled_{sector_id}") is not None:
            disabled.add(sector_id)
        raw = str(form.get(f"limit_{sector_id}", "")).strip()
        if raw.isdigit() and int(raw) > 0:
            limits[sector_id] = int(raw)
    before = read_policy()
    try:
        write_policy(disabled, limits)
    except PolicySealed:
        return RedirectResponse("/sectors?error=sectors.policy.sealed", status_code=303)
    record(session.name, "sectors.policy",
           target=f"closed={sorted(disabled)} limits={limits}",
           outcome=f"was closed={sorted(before['disabled'])} limits={before['limits']}")
    answer = bridge.policy_reload()
    key = "sectors.policy.saved" if answer else "sectors.policy.saved_cold"
    return RedirectResponse(f"/sectors?notice={key}", status_code=303)


@app.post("/sectors/{sector_id}/event")
async def start_event(request: Request, sector_id: int):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse("/sectors?error=csrf.failed", status_code=303)
    if not _may_operate(session):
        return RedirectResponse("/sectors?error=sectors.denied", status_code=303)
    answer = bridge.sector_event(sector_id)
    record(session.name, "sector.event", target=f"sector={sector_id}",
           outcome="down" if answer is None else str(answer))
    if answer is None:
        return RedirectResponse("/sectors?error=sectors.down", status_code=303)
    if not answer.get("ok"):
        if answer.get("reason") == "empty":
            return RedirectResponse("/sectors?error=sectors.event.empty", status_code=303)
        return RedirectResponse(
            f"/sectors?error=sectors.event.refused&detail={answer.get('reason', '')}",
            status_code=303)
    return RedirectResponse("/sectors?notice=sectors.event.armed", status_code=303)


@app.post("/sectors/{sector_id}/op")
async def move_outpost_points(request: Request, sector_id: int):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse("/sectors?error=csrf.failed", status_code=303)
    if not _may_operate(session):
        return RedirectResponse("/sectors?error=sectors.denied", status_code=303)
    faction = str(form.get("faction", ""))
    try:
        points = int(str(form.get("points", "0")))
    except ValueError:
        points = 0
    if faction not in ("colonial", "cylon") or points == 0:
        return RedirectResponse("/sectors?error=sectors.op.bad", status_code=303)
    answer = bridge.sector_op(sector_id, faction, points)
    record(session.name, "sector.op", target=f"sector={sector_id} {faction} {points:+d}",
           outcome="down" if answer is None else str(answer))
    if answer is None:
        return RedirectResponse("/sectors?error=sectors.down", status_code=303)
    return RedirectResponse("/sectors?notice=sectors.op.moved", status_code=303)


@app.post("/sectors/{sector_id}/restart")
async def restart_sector(request: Request, sector_id: int):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse("/sectors?error=csrf.failed", status_code=303)
    if not _may_operate(session) or not session.can_console:
        return RedirectResponse("/sectors?error=sectors.denied", status_code=303)

    status = bridge.status()
    if status is None:
        return RedirectResponse("/sectors?error=sectors.down", status_code=303)
    inside = [pilot for pilot in status.get("online", [])
              if pilot.get("sector") == sector_id]
    for pilot in inside:
        bridge.console(session.pilot_id, f"pilot.kick {pilot.get('id')}")
        record(session.name, "pilot.kick", target=f"pilot={pilot.get('id')}",
               outcome=f"for sector {sector_id} restart")

    def _still_inside() -> bool:
        picture = bridge.sectors() or {}
        for row in picture.get("sectors", []):
            if row.get("id") == sector_id:
                return bool(row.get("players"))
        return False

    if inside:
        for _ in range(24):
            time.sleep(0.5)
            if not _still_inside():
                break

    answer = bridge.sector_restart(sector_id)
    record(session.name, "sector.restart", target=f"sector={sector_id}",
           outcome="down" if answer is None else str(answer))
    if answer is None:
        return RedirectResponse("/sectors?error=sectors.down", status_code=303)
    if not answer.get("ok"):
        names = ", ".join(answer.get("pilots", [])) or answer.get("reason", "")
        return RedirectResponse(
            f"/sectors?error=sectors.restart.refused&detail={names}", status_code=303)
    return RedirectResponse("/sectors?notice=sectors.restarted", status_code=303)


@app.post("/server/restart")
async def restart_server(request: Request):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse("/?error=csrf.failed", status_code=303)
    if not _may_operate(session):
        return RedirectResponse("/?error=sectors.denied", status_code=303)
    record(session.name, "server.restart", outcome="issued")
    try:
        subprocess.Popen(["systemctl", "restart", "bsgo"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return RedirectResponse("/?error=server.restart.failed", status_code=303)
    return RedirectResponse("/?notice=server.restart.issued", status_code=303)
