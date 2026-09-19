# github.com/Shran21

from __future__ import annotations

import subprocess
import threading
import time

from panel.auditlog import record

_lock = threading.Lock()
_plan = None

_WARN_AT_MINUTES = (5, 1)


def status():
    with _lock:
        if _plan is None:
            return None
        return {"at": _plan["at"], "by": _plan["by"],
                "remaining": max(0, int(_plan["at"] - time.time()))}


def cancel(by: str, console) -> bool:
    global _plan
    with _lock:
        if _plan is None:
            return False
        _plan["cancel"].set()
        _plan = None
    record(by, "server.restart-plan", outcome="cancelled")
    console("notice.all \"Az ütemezett újraindítás LEFÚJVA — nyugodt repülést!\"")
    return True


def schedule(minutes: int, by: str, console) -> bool:
    global _plan
    minutes = max(1, min(60, int(minutes)))
    with _lock:
        if _plan is not None:
            return False
        plan = {"at": time.time() + minutes * 60, "by": by,
                "cancel": threading.Event()}
        _plan = plan
    record(by, "server.restart-plan", outcome=f"in {minutes} min")
    console(f'notice.all "FIGYELEM: a szerver {minutes} perc múlva újraindul!"')

    def _worker():
        global _plan
        told = set()
        while True:
            if plan["cancel"].wait(timeout=1.0):
                return
            remaining = plan["at"] - time.time()
            if remaining <= 0:
                break
            for warn_min in _WARN_AT_MINUTES:
                if warn_min not in told and remaining <= warn_min * 60 \
                        and minutes > warn_min:
                    told.add(warn_min)
                    console(f'notice.all "A szerver {warn_min} perc múlva újraindul!"')
        with _lock:
            _plan = None
        record(by, "server.restart-plan", outcome="executed")
        try:
            subprocess.Popen(["systemctl", "restart", "bsgo"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            record(by, "server.restart-plan", outcome="systemctl failed")

    threading.Thread(target=_worker, name="panel-restart-plan",
                     daemon=True).start()
    return True
