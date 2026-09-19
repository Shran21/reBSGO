# github.com/Shran21

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from panel.app import app, bridge, csrf_ok, page
from panel.auditlog import record
from rebsgo.vocabulary.pilot import ServerRoles


def _may_speak(session) -> bool:
    return (session.wears(ServerRoles.Console)
            and not session.wears(ServerRoles.Mod))


_help_cache = None


def _command_help() -> dict:
    global _help_cache
    if _help_cache is None:
        import json
        from panel.settings import ROOT
        try:
            raw = json.loads((ROOT / "panel" / "data" / "console_help.json")
                             .read_text(encoding="utf-8"))
            _help_cache = raw.get("commands", {})
        except (OSError, ValueError):
            _help_cache = {}
    return _help_cache


@app.get("/console", response_class=HTMLResponse)
async def console_page(request: Request):
    session = request.state.session
    if not _may_speak(session):
        return RedirectResponse("/", status_code=303)
    names = bridge.console_commands() or {}
    commands = sorted(set(names.get("developer", []))
                      | set(names.get("console", []))
                      | set(names.get("aliases", {})))
    lang = getattr(request.state, "lang", "hu")
    helps = _command_help()
    manual = [{"name": name,
               "args": helps.get(name, {}).get("args", ""),
               "text": helps.get(name, {}).get(lang, "")}
              for name in commands]
    return page(request, "console.html",
                commands=commands, manual=manual,
                bridge_up=bool(names),
                is_developer=session.wears(ServerRoles.Developer))


@app.post("/console/run")
async def console_run(request: Request):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return JSONResponse({"ok": False, "lines": ["csrf"]}, status_code=400)
    if not _may_speak(session):
        return JSONResponse({"ok": False, "lines": ["forbidden"]}, status_code=403)
    line = str(form.get("line", "")).strip()
    if not line:
        return JSONResponse({"ok": False, "lines": []})
    answer = bridge.console(session.pilot_id, line)
    record(session.name, "console.run", target=line[:200],
           outcome="down" if answer is None else
           ("ok" if answer.get("ok") else "refused"))
    if answer is None:
        return JSONResponse({"ok": False, "down": True, "lines": []})
    return JSONResponse(answer)
