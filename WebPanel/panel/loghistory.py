# github.com/Shran21

from __future__ import annotations

import re
from pathlib import Path

from panel.logfiles import CHANNELS

_DAY = re.compile(r"^---- (\d{4}-\d{2}-\d{2}) ")
_TICKET = re.compile(r"^(?:(\d{4}-\d{2}-\d{2}) )?(\d{2}:\d{2}:\d{2})\.\d+ .*ticket issued: "
                     r"pilot=(\d+) origin=(\S+)")


def logins_of(pilot_id: int, limit: int = 15) -> list:
    base = CHANNELS.get("login")
    if base is None:
        return []
    found = []
    for path in (Path(f"{base}.1"), base):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        day = ""
        for line in lines:
            header = _DAY.match(line)
            if header:
                day = header.group(1).replace("-", ".")
                continue
            ticket = _TICKET.match(line)
            if ticket and int(ticket.group(3)) == int(pilot_id):
                when = (ticket.group(1) or "").replace("-", ".") or day
                found.append({"day": when, "clock": ticket.group(2),
                              "origin": ticket.group(4)})
    return list(reversed(found))[:limit]
