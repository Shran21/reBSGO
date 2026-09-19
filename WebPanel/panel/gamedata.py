# github.com/Shran21

from __future__ import annotations

import json
import logging
import threading

from panel.settings import GAME_ROOT

log = logging.getLogger(__name__)

CARDS_DIR = GAME_ROOT / "GameData" / "cards"

_lock = threading.Lock()
_index = None
_names = None


def _build():
    global _index, _names
    from rebsgo.gamedata.vfs import vfs
    store = vfs()
    rows = []
    names = {}
    for path in store.json_paths_under(CARDS_DIR):
        if "_unused" in path.parts:
            continue
        text = store.read_text(path)
        if text is None:
            continue
        try:
            data = json.loads(text)
        except ValueError:
            continue
        if not isinstance(data, list):
            continue
        where = path.relative_to(CARDS_DIR).as_posix()
        for card in data:
            if not isinstance(card, dict) or "cardGUID" not in card:
                continue
            guid = card.get("cardGUID")
            name = str(card.get("name") or card.get("Name") or "")
            key = str(card.get("key") or "")
            rows.append({"guid": guid, "name": name, "key": key,
                         "view": card.get("cardView"), "file": where})
            if name and guid not in names:
                names[guid] = name
    _index = rows
    _names = names
    log.info("gamedata index built: %s cards (%s)", len(rows),
             "pak" if store.pak_mod else "folder")


def _ready():
    with _lock:
        if _index is None:
            _build()


def name_of(guid) -> str:
    _ready()
    try:
        guid = int(guid)
    except (TypeError, ValueError):
        return str(guid)
    return _names.get(guid) or str(guid)


def search(query: str, limit: int = 50) -> list:
    _ready()
    query = str(query or "").strip()
    if not query:
        return []
    found = []
    as_number = int(query) if query.isdigit() else None
    needle = query.lower()
    for row in _index:
        if as_number is not None and row["guid"] == as_number:
            found.append(row)
        elif as_number is None and (needle in row["name"].lower()
                                    or needle in row["key"].lower()):
            found.append(row)
        if len(found) >= limit:
            break
    return found
