# github.com/Shran21

from __future__ import annotations

import subprocess

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from panel import envfile
from panel import settings as panel_settings
from panel.app import app, csrf_ok, page
from panel.auditlog import record
from rebsgo.vocabulary.pilot import ServerRoles

_CAREFUL_KEYS = {"REBSGO_PANEL_TOKEN", "REBSGO_NET_PANEL_DOOR_PORT"}

_LEGACY_NOTES = {
    "GAME_CHAT_ADDRESS": "config.legacy.chat",
}


def _booleanish(default: str) -> bool:
    return default.strip().lower() in ("true", "false")


@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request, notice: str = "", error: str = ""):
    live = envfile.current()
    sections = envfile.catalog()
    known = set()
    for section in sections:
        for entry in section["entries"]:
            known.add(entry["key"])
            entry["value"] = live.get(entry["key"], "")
            entry["is_bool"] = _booleanish(entry["default"]) or \
                entry["value"].strip().lower() in ("true", "false")
            entry["careful"] = entry["key"] in _CAREFUL_KEYS
    stray = [{"key": key, "value": value, "default": "", "help": "",
              "note_key": _LEGACY_NOTES.get(key, ""),
              "is_bool": value.strip().lower() in ("true", "false"),
              "careful": key in _CAREFUL_KEYS}
             for key, value in sorted(live.items()) if key not in known]
    own = envfile.panel_current()
    merged = panel_settings.raw()
    panel_entries = [{"key": key, "default": default,
                      "value": own.get(key, ""),
                      "effective": merged.get(key, ""),
                      "careful": careful,
                      "is_bool": False}
                     for key, default, careful in envfile.PANEL_KEYS]
    return page(request, "config.html",
                sections=sections, stray=stray,
                panel_entries=panel_entries,
                may_edit=request.state.session.wears(ServerRoles.Developer),
                notice=notice, error=error)


@app.post("/config")
async def config_save(request: Request):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse("/config?error=csrf.failed", status_code=303)
    if not session.wears(ServerRoles.Developer):
        return RedirectResponse("/config?error=config.denied", status_code=303)
    changes = {}
    for name, value in form.multi_items():
        if name.startswith("value_"):
            changes[name[len("value_"):]] = str(value).strip()
    moved = envfile.apply(changes)
    if not moved:
        return RedirectResponse("/config?notice=config.unchanged", status_code=303)
    record(session.name, "config.save", outcome="; ".join(moved)[:400])
    return RedirectResponse("/config?notice=config.saved", status_code=303)


@app.post("/config/panel")
async def config_panel_save(request: Request):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse("/config?error=csrf.failed", status_code=303)
    if not session.wears(ServerRoles.Developer):
        return RedirectResponse("/config?error=config.denied", status_code=303)
    allowed = {key for key, _, _ in envfile.PANEL_KEYS}
    changes = {}
    for name, value in form.multi_items():
        if name.startswith("panel_") and name[len("panel_"):] in allowed:
            changes[name[len("panel_"):]] = str(value).strip()
    moved = envfile.panel_apply(changes)
    if not moved:
        return RedirectResponse("/config?notice=config.unchanged", status_code=303)
    record(session.name, "config.panel.save", outcome="; ".join(moved)[:400])
    return RedirectResponse("/config?notice=config.panel.saved", status_code=303)


@app.post("/panel/restart")
async def panel_restart(request: Request):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse("/config?error=csrf.failed", status_code=303)
    if not session.wears(ServerRoles.Developer):
        return RedirectResponse("/config?error=config.denied", status_code=303)
    record(session.name, "panel.restart")
    try:
        subprocess.Popen(["sh", "-c", "sleep 1; systemctl restart rebsgo-panel"],
                         start_new_session=True)
    except OSError:
        return RedirectResponse("/config?error=config.panel.restartfail", status_code=303)
    return RedirectResponse("/config?notice=config.panel.restarting", status_code=303)
