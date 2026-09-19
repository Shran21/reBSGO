# github.com/Shran21

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from panel import gamedata
from panel.app import app, bridge, csrf_ok, database, page
from panel.auditlog import record
from rebsgo.vocabulary.pilot import ServerRoles


@app.get("/rankings", response_class=HTMLResponse)
async def rankings_page(request: Request, guid: int = 0, period: str = "",
                        notice: str = "", error: str = ""):
    guids = database.tally_guids()
    counters = [{"guid": g, "name": gamedata.name_of(g)} for g in guids]
    counters.sort(key=lambda c: c["name"].lower())
    if not guid and counters:
        guid = counters[0]["guid"]
    periods = database.snapshot_periods()
    if period:
        board = database.snapshot_board(period, guid)
    else:
        board = database.tally_board(guid)
    return page(request, "rankings.html",
                counters=counters, guid=int(guid),
                periods=periods, period=period,
                board=board,
                counter_name=gamedata.name_of(guid) if guid else "",
                may_operate=request.state.session.wears(ServerRoles.Developer),
                notice=notice, error=error)


@app.post("/rankings/recalc")
async def rankings_recalc(request: Request):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse("/rankings?error=csrf.failed", status_code=303)
    if not session.wears(ServerRoles.Developer):
        return RedirectResponse("/rankings?error=sectors.denied", status_code=303)
    answer = bridge.rankings_recalc()
    record(session.name, "rankings.recalc",
           outcome="down" if answer is None else str(answer))
    if answer is None:
        return RedirectResponse("/rankings?error=sectors.down", status_code=303)
    return RedirectResponse("/rankings?notice=rankings.recalced", status_code=303)
