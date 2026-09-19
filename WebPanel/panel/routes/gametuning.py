# github.com/Shran21

from __future__ import annotations

import json
from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from panel.app import app, csrf_ok, page
from panel.auditlog import record
from panel.settings import GAME_ROOT
from rebsgo.vocabulary.pilot import ServerRoles

TEMPLATES_ROOT = GAME_ROOT / "GameData" / "templates"

FILES = (
    {"slug": "revenant", "path": "Event/revenant_haunt.json",
     "title": "gametuning.revenant",
     "fields": (
         ("enabled", "bool", None, None),
         ("maxHaunted", "int", 0, 58),
         ("perSector", "int", 1, 5),
         ("barredSectorIds", "intlist", None, None),
         ("gearLevel", "int", 1, 15),
         ("lifeTimeSeconds", "int", 60, 86400),
         ("respawnDelaySeconds", "int", 0, 86400),
         ("patrolRadius", "float", 100, 20000),
         ("sweepSeconds", "int", 10, 3600),
     ),
     "locked": ("shipGuid", "lootId")},
    {"slug": "droneswarm", "path": "Event/drone_swarm.json",
     "title": "gametuning.droneswarm",
     "fields": (
         ("enabled", "bool", None, None),
         ("waveMin", "int", 1, 30),
         ("waveMax", "int", 1, 30),
         ("respawnDelaySeconds", "int", 0, 3600),
         ("spawnRadius", "float", 50, 5000),
         ("patrolRadius", "float", 100, 20000),
         ("gearLevel", "int", 1, 15),
         ("lifeTimeSeconds", "int", 0, 86400),
         ("sweepSeconds", "int", 5, 3600),
     ),
     "locked": ("commandShipGuid",)},
    {"slug": "sectorevents", "path": "Event/sector_events.json",
     "title": "gametuning.sectorevents",
     "fields": (
         ("enabled", "bool", None, None),
         ("autoDisabledSectorIds", "intlist", None, None),
         ("intervalMinutes", "int", 5, 1440),
         ("startJitterMinutes", "int", 0, 720),
         ("maxAliveNpcs", "int", 1, 60),
         ("attackerRatio", "float", 0.1, 10.0),
         ("durationSeconds", "int", 60, 7200),
         ("emptyGraceSeconds", "int", 0, 3600),
         ("waveGapSeconds", "int", 0, 1800),
         ("repeatLastWave", "bool", None, None),
     ),
     "locked": ("eventCardGuid",)},
    {"slug": "mines", "path": "Weapons/mines.json",
     "title": "gametuning.mines",
     "fields": (
         ("triggerRadius", "float", 10, 2000),
         ("blastRadius", "float", 10, 5000),
         ("fallbackLifeTimeSeconds", "float", 10, 3600),
     ),
     "locked": ("warheads",)},
    {"slug": "carrier", "path": "Carrier/base_mode.json",
     "title": "gametuning.carrier",
     "fields": (
         ("dockRange", "float", 100, 10000),
         ("partyOnly", "bool", None, None),
         ("transponderPartyOnly", "bool", None, None),
         ("requireFortifiedForAnchor", "bool", None, None),
         ("repairEnabled", "bool", None, None),
     ),
     "locked": ("carrierShipGuids",)},
)


def _spec(slug: str):
    for spec in FILES:
        if spec["slug"] == slug:
            return spec
    return None


def _text_of(path: Path) -> str:
    from rebsgo.gamedata.vfs import vfs
    text = vfs().read_text(path)
    if text is None:
        raise OSError(f"unreadable: {path}")
    return text


def sealed() -> bool:
    from rebsgo.gamedata.vfs import vfs
    return vfs().pak_mod


def _load(spec) -> dict:
    return json.loads(_text_of(TEMPLATES_ROOT / spec["path"]))


def _indent_of(path: Path) -> int:
    try:
        for line in _text_of(path).splitlines()[1:4]:
            stripped = len(line) - len(line.lstrip(" "))
            if stripped:
                return stripped
    except OSError:
        pass
    return 1


def _rows(spec, data: dict) -> list:
    rows = []
    for name, kind, low, high in spec["fields"]:
        value = data.get(name)
        if kind == "intlist":
            shown = ", ".join(str(v) for v in (value or []))
        else:
            shown = "" if value is None else value
        rows.append({"name": name, "kind": kind, "low": low, "high": high,
                     "value": shown})
    return rows


def _parse(kind: str, raw: str, low, high):
    raw = raw.strip()
    if kind == "bool":
        if raw not in ("true", "false"):
            raise ValueError(raw)
        return raw == "true"
    if kind == "intlist":
        if not raw:
            return []
        return sorted({int(piece) for piece in raw.replace(";", ",").split(",")
                       if piece.strip()})
    if kind == "int":
        value = int(raw)
    else:
        value = int(raw) if raw.lstrip("+-").isdigit() else float(raw)
    if low is not None and value < low:
        raise ValueError(raw)
    if high is not None and value > high:
        raise ValueError(raw)
    return value


@app.get("/gametuning", response_class=HTMLResponse)
async def gametuning_page(request: Request, notice: str = "", error: str = ""):
    cards = []
    for spec in FILES:
        try:
            data = _load(spec)
        except (OSError, ValueError):
            continue
        cards.append({"slug": spec["slug"], "title": spec["title"],
                      "path": spec["path"],
                      "comment": data.get("_comment") or data.get("comment") or "",
                      "rows": _rows(spec, data),
                      "locked": [{"name": name, "value": json.dumps(data.get(name))}
                                 for name in spec["locked"] if name in data]})
    return page(request, "gametuning.html", cards=cards, sealed=sealed(),
                may_edit=request.state.session.wears(ServerRoles.Developer),
                notice=notice, error=error)


@app.post("/gametuning/{slug}")
async def gametuning_save(request: Request, slug: str):
    form = await request.form()
    session = request.state.session
    if not csrf_ok(request, str(form.get("csrf", ""))):
        return RedirectResponse("/gametuning?error=csrf.failed", status_code=303)
    if not session.wears(ServerRoles.Developer):
        return RedirectResponse("/gametuning?error=gametuning.denied", status_code=303)
    spec = _spec(slug)
    if spec is None:
        return RedirectResponse("/gametuning?error=gametuning.unknown", status_code=303)
    if sealed():
        return RedirectResponse("/gametuning?error=gametuning.sealed", status_code=303)
    path = TEMPLATES_ROOT / spec["path"]
    try:
        data = _load(spec)
    except (OSError, ValueError):
        return RedirectResponse("/gametuning?error=gametuning.unreadable", status_code=303)

    moved = []
    try:
        for name, kind, low, high in spec["fields"]:
            raw = form.get("field_" + name)
            if raw is None:
                continue
            value = _parse(kind, str(raw), low, high)
            if value != data.get(name):
                moved.append(f"{name}: {data.get(name)!r} -> {value!r}")
                data[name] = value
    except (ValueError, TypeError):
        return RedirectResponse("/gametuning?error=gametuning.badvalue", status_code=303)

    if not moved:
        return RedirectResponse("/gametuning?notice=gametuning.unchanged", status_code=303)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=_indent_of(path)) + "\n",
                    encoding="utf-8")
    record(session.name, "gametuning.save", target=spec["path"],
           outcome="; ".join(moved)[:400])
    return RedirectResponse("/gametuning?notice=gametuning.saved", status_code=303)
