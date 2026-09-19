# github.com/Shran21

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse

from panel.app import app, database, page
from panel.db import RESOURCE_GUIDS


@app.get("/economy", response_class=HTMLResponse)
async def economy_page(request: Request):
    picture = database.economy()
    resources = [{"guid": guid, "key": key,
                  "total": picture["totals"].get(guid, 0),
                  "richest": picture["richest"].get(guid)}
                 for guid, key in RESOURCE_GUIDS]
    return page(request, "economy.html",
                resources=resources, pilots=picture["pilots"],
                guids=[guid for guid, _ in RESOURCE_GUIDS])
