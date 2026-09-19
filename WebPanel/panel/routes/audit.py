# github.com/Shran21

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse

from panel.app import app, page
from panel.logfiles import tail


@app.get("/audit", response_class=HTMLResponse)
async def audit_page(request: Request, q: str = "", n: int = 200):
    game = tail("audit", query=q, limit=n)
    panel = tail("panel", query=q, limit=n)
    return page(request, "audit.html",
                game_lines=game["lines"], panel_lines=panel["lines"],
                q=q, n=int(n))
