# github.com/Shran21

from __future__ import annotations

import json
import time
import logging
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 4.0


class Bridge:
    def __init__(self, url: str, token: str):
        self._url = url
        self._token = token

    @property
    def has_token(self) -> bool:
        return bool(self._token)

    def _request(self, path: str, payload: dict | None = None,
                 timeout: float = _TIMEOUT_SECONDS):
        if not self._token:
            return None
        request = urllib.request.Request(
            self._url + path,
            data=None if payload is None else json.dumps(payload).encode("utf-8"),
            headers={"X-Panel-Key": self._token, "Content-Type": "application/json"},
            method="GET" if payload is None else "POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as trouble:
            log.debug("panel door unreachable: %s", trouble)
            return None


    def status(self):
        return self._request("/status")

    def online_ids(self) -> set:
        status = self.status()
        if not status:
            return set()
        return {pilot.get("id") for pilot in status.get("online", [])}

    def save_now(self):
        return self._request("/save", {})

    def console(self, pilot_id: int, line: str):
        return self._request("/console", {"pilot": int(pilot_id), "line": str(line)},
                             timeout=10.0)

    def console_commands(self):
        return self._request("/console/commands")

    def sectors(self):
        return self._request("/sectors")

    def sector_event(self, sector_id: int):
        return self._request("/sector-event", {"sector": int(sector_id)})

    def sector_op(self, sector_id: int, faction: str, points: int):
        return self._request("/sector-op", {"sector": int(sector_id),
                                            "faction": str(faction),
                                            "points": int(points)})

    def sector_restart(self, sector_id: int):
        return self._request("/sector-restart", {"sector": int(sector_id)},
                             timeout=20.0)

    def policy_reload(self):
        return self._request("/policy-reload", {})

    def maintenance(self):
        return self._request("/maintenance")

    def set_maintenance(self, on: bool, message: str = ""):
        return self._request("/maintenance", {"on": bool(on),
                                              "message": str(message)})

    def rankings_recalc(self):
        return self._request("/rankings-recalc", {}, timeout=20.0)

    def log_state(self):
        return self._request("/log")

    def set_log(self, level: str, area: str | None = None):
        payload = {"level": str(level)}
        if area:
            payload["area"] = str(area)
        return self._request("/log", payload)


def uptime_seconds(status) -> int | None:
    try:
        return max(0, int(time.time() - float(status["started"])))
    except (KeyError, TypeError, ValueError):
        return None
