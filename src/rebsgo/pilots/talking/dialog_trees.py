# github.com/Shran21
from __future__ import annotations

import json
import logging
import os
import threading

log = logging.getLogger(__name__)

_NAME_TO_KEY = {
    "apollo": "npc_apollo",
    "adama": "npc_adama",
    "tyrol": "npc_tyrol",
    "galen": "npc_tyrol",
    "starbuck": "npc_starbuck",
    "kara": "npc_starbuck",
    "officer": "npc_humanoutpost",
    "leoben": "npc_no2",
    "cavil": "npc_no1",
    "no1": "npc_no1",
    "no2": "npc_no2",
    "no6": "npc_no6",
    "caprica": "npc_no6",
    "no8": "npc_no8",
    "sharon": "npc_no8",
    "boomer": "npc_no8",
    "athena": "npc_no8",
}


class DialogTrees:
    def __init__(self, game_data_root: str = "GameData"):
        self._trees = {}
        from rebsgo.gamedata.vfs import vfs
        path = os.path.join(game_data_root, "dialogs", "npc_dialogs.json")
        try:
            szoveg = vfs().read_text(path)
            if szoveg is None:
                log.warning("DialogTrees: %s not found; NPC dialog trees disabled", path)
            else:
                self._trees = json.loads(szoveg)
                log.info("DialogTrees loaded: %d NPC dialog trees", len(self._trees))
        except Exception:
            log.exception("DialogTrees: failed to load %s", path)

    @staticmethod
    def key_for_name(npc_name: str):
        if not npc_name:
            return None
        return _NAME_TO_KEY.get(npc_name.lower(), "npc_" + npc_name.lower())

    def get(self, npc_key: str):
        return self._trees.get(npc_key)

    def has(self, npc_key: str) -> bool:
        return npc_key in self._trees


class TalkState:
    def __init__(self):
        self._active = {}
        self._lock = threading.Lock()

    def start(self, user_id: int, npc_key: str) -> None:
        with self._lock:
            self._active[user_id] = npc_key

    def get(self, user_id: int):
        with self._lock:
            return self._active.get(user_id)

    def clear(self, user_id: int) -> None:
        with self._lock:
            self._active.pop(user_id, None)
