# github.com/Shran21

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from panel import gamedata
from panel.app import app, database
from panel.sectors import SECTOR_NAMES


@app.get("/search")
async def search(request: Request, q: str = ""):
    needle = q.strip().lower()
    if not needle:
        return JSONResponse({"pilots": [], "sectors": [], "cards": []})
    pilots = [{"title": row["name"], "meta": f"#{row['id']}", "href": f"/users/{row['id']}"}
              for row in database.pilots() if needle in str(row["name"] or "").lower()][:8]
    sectors = [{"title": name, "meta": f"#{sid}", "href": f"/sectors#s{sid}"}
               for sid, name in sorted(SECTOR_NAMES.items(), key=lambda pair: pair[1])
               if needle in name.lower() or needle == str(sid)][:8]
    cards = [{"title": row["name"] or str(row["guid"]),
              "meta": f"{row['guid']} · {row['view']}",
              "href": f"/tools?q={row['guid']}"}
             for row in gamedata.search(q, limit=8)]
    return JSONResponse({"pilots": pilots, "sectors": sectors, "cards": cards})
