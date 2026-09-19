# github.com/Shran21

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse

from panel.app import app, bridge, page
from panel.policy import read_policy
from panel.sectors import SECTOR_POSITIONS, sector_name

_WIDTH, _HEIGHT, _MARGIN = 1000.0, 700.0, 55.0


def _projected() -> dict:
    if not SECTOR_POSITIONS:
        return {}
    xs = [x for x, _y in SECTOR_POSITIONS.values()]
    ys = [y for _x, y in SECTOR_POSITIONS.values()]
    span_x = (max(xs) - min(xs)) or 1.0
    span_y = (max(ys) - min(ys)) or 1.0
    scale = min((_WIDTH - 2 * _MARGIN) / span_x, (_HEIGHT - 2 * _MARGIN) / span_y)
    return {sector_id: (
        _MARGIN + (x - min(xs)) * scale,
        _MARGIN + (y - min(ys)) * scale)
        for sector_id, (x, y) in SECTOR_POSITIONS.items()}


_PLACES = _projected()


@app.get("/map", response_class=HTMLResponse)
async def map_page(request: Request):
    live = bridge.sectors()
    by_id = {row.get("id"): row for row in (live or {}).get("sectors", [])}
    closed = read_policy()["disabled"]
    stars = []
    for sector_id, (x, y) in sorted(_PLACES.items()):
        row = by_id.get(sector_id) or {}
        players = row.get("players") or 0
        outposts = ["K" if op.get("faction") == "Colonial" else "C"
                    for op in row.get("outpost_hp") or []]
        stars.append({
            "id": sector_id,
            "name": sector_name(sector_id),
            "x": round(x, 1), "y": round(y, 1),
            "players": players,
            "names": ", ".join(row.get("names") or []),
            "npcs": row.get("npcs") or 0,
            "outposts": outposts,
            "beacons": row.get("beacons") or 0,
            "closed": sector_id in closed,
            "radius": min(16, 6 + players * 2),
        })
    return page(request, "starmap.html", stars=stars,
                width=int(_WIDTH), height=int(_HEIGHT),
                live=live is not None)
