# github.com/Shran21

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from panel.app import app, bridge, csrf_ok, database, gatekeeper, page
from panel.auditlog import record
from panel.db import RESOURCE_GUIDS
from panel.sectors import sector_name
from rebsgo.admission.passwords import JelszoHiba
from rebsgo.vocabulary.pilot import ServerRoles

EDITABLE_ROLES = ("View", "Edit", "Ban", "CommunityManager",
                  "Developer", "Console", "GodMode", "Mod")

_FACTION_KEYS = {1: "faction.colonial", 2: "faction.cylon"}

_MIN_PASSWORD_LENGTH = 6


def _role_names(bits: int) -> list:
    return [r.name for r in ServerRoles if r.value and bits & r.value]


def _faction_key(value) -> str:
    return _FACTION_KEYS.get(int(value or 0), "faction.neutral")


def _whereabouts() -> dict:
    status = bridge.status() or {}
    return {pilot.get("id"): sector_name(pilot.get("sector"))
            for pilot in status.get("online", [])}


_ORDERS = {
    "online": lambda pilot: (not pilot["is_online"], str(pilot["name"] or "").lower()),
    "name": lambda pilot: str(pilot["name"] or "").lower(),
    "id": lambda pilot: int(pilot["id"]),
    "last_seen": lambda pilot: str(pilot["last_seen"] or ""),
}


@app.get("/users", response_class=HTMLResponse)
async def users_list(request: Request, q: str = "", sort: str = "online", desc: int = 0,
                     notice: str = "", error: str = ""):
    whereabouts = _whereabouts()
    banned = database.bans()
    pilots = database.pilots()
    for pilot in pilots:
        pilot["role_names"] = _role_names(int(pilot["roles_bits"] or 0))
        pilot["faction_key"] = _faction_key(pilot["faction"])
        pilot["is_online"] = pilot["id"] in whereabouts
        pilot["online_sector"] = whereabouts.get(pilot["id"])
        pilot["is_banned"] = pilot["id"] in banned
    needle = q.strip().lower()
    if needle:
        pilots = [pilot for pilot in pilots if needle in str(pilot["name"] or "").lower()]
    order = sort if sort in _ORDERS else "online"
    pilots.sort(key=_ORDERS[order], reverse=bool(desc))
    return page(request, "users.html", pilots=pilots, q=q.strip(), sort=order, desc=1 if desc else 0,
                may_create=request.state.session.wears(ServerRoles.Developer),
                notice=notice, error=error)


@app.get("/users/{pilot_id}", response_class=HTMLResponse)
async def user_detail(request: Request, pilot_id: int, notice: str = "", error: str = ""):
    pilot = database.pilot(pilot_id)
    if pilot is None:
        return RedirectResponse("/users", status_code=303)
    bits = int(pilot["roles_bits"] or 0)
    session = request.state.session
    whereabouts = _whereabouts()
    return page(request, "user_detail.html",
                pilot=pilot,
                faction_key=_faction_key(pilot["faction"]),
                is_online=pilot_id in whereabouts,
                online_sector=whereabouts.get(pilot_id),
                may_kick=session.can_console,
                may_erase=session.wears(ServerRoles.Developer),
                roles=[{"name": name,
                        "value": getattr(ServerRoles, name).value,
                        "worn": bool(bits & getattr(ServerRoles, name).value)}
                       for name in EDITABLE_ROLES],
                resources=database.resources(pilot_id),
                ban=database.bans().get(pilot_id),
                tallies=_dossier(pilot_id),
                logins=_logins(pilot_id),
                may_edit_roles=session.wears(ServerRoles.Developer),
                may_set_password=session.wears_any(ServerRoles.Developer, ServerRoles.Ban),
                may_edit_resources=session.wears_any(ServerRoles.Developer, ServerRoles.Edit),
                may_ban=session.wears_any(ServerRoles.Developer, ServerRoles.Ban),
                notice=notice, error=error)


def _logins(pilot_id: int) -> list:
    from panel.loghistory import logins_of
    try:
        return logins_of(pilot_id)
    except Exception:
        return []


def _dossier(pilot_id: int) -> list:
    from panel import gamedata
    rows = database.pilot_tallies(pilot_id)[:24]
    for row in rows:
        row["name"] = gamedata.name_of(row["guid"])
        row["value"] = int(row["value"]) if float(row["value"]).is_integer() \
            else round(float(row["value"]), 2)
    return rows


_BAN_HOURS = {"1h": 1, "24h": 24, "7d": 7 * 24, "30d": 30 * 24,
              "forever": 100 * 365 * 24}


@app.post("/users/{pilot_id}/ban")
async def ban_pilot(request: Request, pilot_id: int):
    from datetime import datetime, timedelta, timezone
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse(f"/users/{pilot_id}?error=csrf.failed", status_code=303)
    if not session.wears_any(ServerRoles.Developer, ServerRoles.Ban):
        return RedirectResponse(f"/users/{pilot_id}?error=ban.denied", status_code=303)
    if pilot_id == session.pilot_id:
        return RedirectResponse(f"/users/{pilot_id}?error=ban.self", status_code=303)
    hours = _BAN_HOURS.get(str(form.get("length", "")))
    if hours is None:
        return RedirectResponse(f"/users/{pilot_id}?error=ban.length", status_code=303)
    reason = str(form.get("reason", "")).strip()[:200]
    until = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
    database.set_ban(pilot_id, until, reason, session.name)
    record(session.name, "ban.set", target=f"pilot={pilot_id}",
           outcome=f"until={until} reason={reason!r}")
    if pilot_id in bridge.online_ids():
        bridge.console(session.pilot_id, f"pilot.kick {pilot_id}")
        record(session.name, "pilot.kick", target=f"pilot={pilot_id}",
               outcome="on ban")
    return RedirectResponse(f"/users/{pilot_id}?notice=ban.set", status_code=303)


@app.post("/users/{pilot_id}/unban")
async def unban_pilot(request: Request, pilot_id: int):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse(f"/users/{pilot_id}?error=csrf.failed", status_code=303)
    if not session.wears_any(ServerRoles.Developer, ServerRoles.Ban):
        return RedirectResponse(f"/users/{pilot_id}?error=ban.denied", status_code=303)
    database.clear_ban(pilot_id)
    record(session.name, "ban.clear", target=f"pilot={pilot_id}")
    return RedirectResponse(f"/users/{pilot_id}?notice=ban.cleared", status_code=303)


@app.post("/users/{pilot_id}/roles")
async def save_roles(request: Request, pilot_id: int):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse(f"/users/{pilot_id}?error=csrf.failed", status_code=303)
    if not session.wears(ServerRoles.Developer):
        return RedirectResponse(f"/users/{pilot_id}?error=user.roles.denied", status_code=303)
    if pilot_id in bridge.online_ids():
        return RedirectResponse(f"/users/{pilot_id}?error=user.roles.online_locked",
                                status_code=303)
    bits = 0
    for name in EDITABLE_ROLES:
        if form.get(f"role_{name}") is not None:
            bits |= getattr(ServerRoles, name).value
    database.set_role_bits(pilot_id, bits)
    record(session.name, "roles.set", target=f"pilot={pilot_id}", outcome=f"bits={bits}")
    return RedirectResponse(f"/users/{pilot_id}?notice=user.roles.saved", status_code=303)


@app.post("/users/{pilot_id}/password")
async def save_password(request: Request, pilot_id: int):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse(f"/users/{pilot_id}?error=csrf.failed", status_code=303)
    if not session.wears_any(ServerRoles.Developer, ServerRoles.Ban):
        return RedirectResponse(f"/users/{pilot_id}?error=user.password.denied",
                                status_code=303)
    password = str(form.get("password", ""))
    if len(password) < _MIN_PASSWORD_LENGTH:
        return RedirectResponse(f"/users/{pilot_id}?error=user.password.short",
                                status_code=303)
    try:
        gatekeeper.password_store.beallit(pilot_id, password)
    except JelszoHiba:
        record(session.name, "password.set", target=f"pilot={pilot_id}", outcome="failed")
        return RedirectResponse(f"/users/{pilot_id}?error=user.password.short",
                                status_code=303)
    record(session.name, "password.set", target=f"pilot={pilot_id}")
    return RedirectResponse(f"/users/{pilot_id}?notice=user.password.saved", status_code=303)


@app.post("/users/new")
async def create_account(request: Request):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse("/users?error=csrf.failed", status_code=303)
    if not session.wears(ServerRoles.Developer):
        return RedirectResponse("/users?error=account.denied", status_code=303)
    name = str(form.get("name", "")).strip()
    password = str(form.get("password", ""))
    try:
        faction = int(form.get("faction", 0) or 0)
    except ValueError:
        faction = 0
    if faction not in (0, 1, 2):
        faction = 0
    if len(password) < _MIN_PASSWORD_LENGTH:
        return RedirectResponse("/users?error=user.password.short", status_code=303)
    pilot_id, refusal = database.create_pilot(name, faction)
    if refusal:
        return RedirectResponse(f"/users?error={refusal}", status_code=303)
    try:
        gatekeeper.password_store.beallit(pilot_id, password)
    except JelszoHiba:
        database.erase_pilot(pilot_id)
        return RedirectResponse("/users?error=user.password.short", status_code=303)
    record(session.name, "account.create", target=f"pilot={pilot_id} name={name}",
           outcome=f"faction={faction}")
    return RedirectResponse(f"/users/{pilot_id}?notice=account.created", status_code=303)


@app.post("/users/{pilot_id}/erase")
async def erase_account(request: Request, pilot_id: int):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse(f"/users/{pilot_id}?error=csrf.failed", status_code=303)
    if not session.wears(ServerRoles.Developer):
        return RedirectResponse(f"/users/{pilot_id}?error=account.denied", status_code=303)
    if pilot_id in bridge.online_ids():
        return RedirectResponse(f"/users/{pilot_id}?error=account.online",
                                status_code=303)
    if pilot_id == session.pilot_id:
        return RedirectResponse(f"/users/{pilot_id}?error=account.self",
                                status_code=303)
    removed = database.erase_pilot(pilot_id)
    record(session.name, "account.erase", target=f"pilot={pilot_id}",
           outcome="; ".join(f"{table}={count}" for table, count in sorted(removed.items()))
           or "nothing")
    return RedirectResponse("/users?notice=account.erased", status_code=303)


@app.post("/users/{pilot_id}/kick")
async def kick_pilot(request: Request, pilot_id: int):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse(f"/users/{pilot_id}?error=csrf.failed", status_code=303)
    if not session.can_console:
        return RedirectResponse(f"/users/{pilot_id}?error=user.kick.denied",
                                status_code=303)
    if pilot_id not in bridge.online_ids():
        return RedirectResponse(f"/users/{pilot_id}?error=user.kick.offline",
                                status_code=303)
    answer = bridge.console(session.pilot_id, f"pilot.kick {pilot_id}")
    record(session.name, "pilot.kick", target=f"pilot={pilot_id}",
           outcome="down" if answer is None else "sent")
    if answer is None:
        return RedirectResponse(f"/users/{pilot_id}?error=user.kick.failed",
                                status_code=303)
    return RedirectResponse(f"/users/{pilot_id}?notice=user.kicked", status_code=303)


@app.post("/users/{pilot_id}/resources")
async def save_resources(request: Request, pilot_id: int):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse(f"/users/{pilot_id}?error=csrf.failed", status_code=303)
    if not session.wears_any(ServerRoles.Developer, ServerRoles.Edit):
        return RedirectResponse(f"/users/{pilot_id}?error=user.resources.denied",
                                status_code=303)
    if pilot_id in bridge.online_ids():
        return RedirectResponse(f"/users/{pilot_id}?error=user.resources.online_locked",
                                status_code=303)
    for guid, key in RESOURCE_GUIDS:
        raw = form.get(f"amount_{guid}")
        if raw is None:
            continue
        try:
            amount = int(str(raw).replace(" ", "") or "0")
        except ValueError:
            continue
        changed, old = database.set_resource(pilot_id, guid, amount)
        if changed:
            record(session.name, "resource.set", target=f"pilot={pilot_id} {key}",
                   outcome=f"{old} -> {amount}")
    return RedirectResponse(f"/users/{pilot_id}?notice=user.resources.saved", status_code=303)
