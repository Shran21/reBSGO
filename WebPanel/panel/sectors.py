# github.com/Shran21

from __future__ import annotations

import json
import logging

from panel.settings import GAME_ROOT

log = logging.getLogger(__name__)

_CARDS = GAME_ROOT / "GameData" / "cards"


def _load_map() -> tuple:
    try:
        from rebsgo.gamedata.vfs import vfs
        store = vfs()
        world = store.read_text(_CARDS / "world" / "galaxymap.json")
        ui = store.read_text(_CARDS / "ui" / "gui.json")
        if world is None or ui is None:
            raise OSError("galaxy map or gui cards unavailable")
        stars = json.loads(world)[0]["stars"]
        names_by_guid = {card["cardGUID"]: card.get("name") or card.get("Name")
                         for card in json.loads(ui)
                         if isinstance(card, dict)}
        names = {int(star["Id"]): names_by_guid[star["SectorGUID"]]
                 for star in stars.values()
                 if names_by_guid.get(star.get("SectorGUID"))}
        outposts = {int(star["Id"]): (bool(star.get("CanColonialOutpost")),
                                      bool(star.get("CanCylonOutpost")))
                    for star in stars.values()}
        beacons = {int(star["Id"]): (bool(star.get("CanColonialJumpBeacon")),
                                     bool(star.get("CanCylonJumpBeacon")))
                   for star in stars.values()}
        positions = {int(star["Id"]): (float(star["Position"]["x"]),
                                       float(star["Position"]["y"]))
                     for star in stars.values() if star.get("Position")}
        return names, outposts, beacons, positions
    except (OSError, ValueError, KeyError, TypeError, ImportError) as trouble:
        log.warning("sector names unavailable: %s", trouble)
        return {}, {}, {}, {}


SECTOR_NAMES, SECTOR_OUTPOSTS, SECTOR_BEACONS, SECTOR_POSITIONS = _load_map()


def outpost_allowed(sector_id) -> tuple:
    try:
        return SECTOR_OUTPOSTS.get(int(sector_id), (False, False))
    except (TypeError, ValueError):
        return (False, False)


def beacon_allowed(sector_id) -> tuple:
    try:
        return SECTOR_BEACONS.get(int(sector_id), (False, False))
    except (TypeError, ValueError):
        return (False, False)


def sector_name(sector_id) -> str:
    try:
        sector_id = int(sector_id)
    except (TypeError, ValueError):
        return str(sector_id)
    return SECTOR_NAMES.get(sector_id) or f"#{sector_id}"
