# github.com/Shran21

from __future__ import annotations

import json

from panel.settings import GAME_ROOT

POLICY_PATH = GAME_ROOT / "GameData" / "templates" / "World" / "sector_policy.json"


class PolicySealed(RuntimeError):
    pass


def sealed() -> bool:
    try:
        from rebsgo.gamedata.vfs import vfs
        return vfs().pak_mod
    except ImportError:
        return False


def read_policy() -> dict:
    try:
        from rebsgo.gamedata.vfs import vfs
        text = vfs().read_text(POLICY_PATH)
        if text is None:
            raise OSError("sector policy unavailable")
        raw = json.loads(text)
        return {"disabled": {int(x) for x in raw.get("disabledSectors") or []},
                "limits": {int(k): int(v)
                           for k, v in (raw.get("playerLimits") or {}).items()
                           if int(v) > 0},
                "comment": raw.get("_comment", "")}
    except (OSError, ValueError, ImportError):
        return {"disabled": set(), "limits": {}, "comment": ""}


def write_policy(disabled, limits) -> None:
    if sealed():
        raise PolicySealed(str(POLICY_PATH))
    current = read_policy()
    body = {}
    if current["comment"]:
        body["_comment"] = current["comment"]
    body["disabledSectors"] = sorted(int(x) for x in disabled)
    body["playerLimits"] = {str(k): int(v) for k, v in sorted(limits.items())
                            if int(v) > 0}
    POLICY_PATH.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
