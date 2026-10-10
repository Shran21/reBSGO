# github.com/Shran21

from __future__ import annotations

import logging
import random
import time

from rebsgo import paths
from rebsgo.gamedata.from_json.game_data_loader import GameDataLoader
from rebsgo.gamedata.npc_minds import template_of_tier
from rebsgo.geometry.collider_shapes import AABB
from rebsgo.geometry.primitives.quaternion import Quaternion
from rebsgo.geometry.primitives.transform import Transform
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.world.sectors.npc_minds import PatrolGoal

log = logging.getLogger(__name__)


class HauntPlan:
    def __init__(self, obj: dict):
        self.enabled = bool(obj.get("enabled", False))
        self.ship_guid = int(obj.get("shipGuid", 0))
        self.max_haunted = int(obj.get("maxHaunted", 8))
        self.barred_sector_ids = set(obj.get("barredSectorIds") or [])
        self.gear_level = int(obj.get("gearLevel", 1))
        self.loot_id = int(obj.get("lootId", 0))
        self.life_seconds = int(obj.get("lifeTimeSeconds", 3600))
        self.respawn_delay_seconds = int(obj.get("respawnDelaySeconds", 600))
        self.patrol_radius = float(obj.get("patrolRadius", 2500.0))
        self.height_band = float(obj.get("heightBand", 400.0))
        self.sweep_seconds = float(obj.get("sweepSeconds", 60.0))
        if self.enabled and not self.ship_guid:
            log.warning("The revenant haunt is on but names no hull; holding it off")
            self.enabled = False


class HauntPlanReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Event")

    def fetch(self) -> HauntPlan:
        for utvonal in self.file_paths():
            if utvonal.name != "revenant_haunt.json":
                continue
            if (obj := self.read_json(utvonal)) is not None:
                terv = HauntPlan(obj)
                log.info("Loaded the revenant haunt plan (enabled=%s, cap=%s)",
                         terv.enabled, terv.max_haunted)
                return terv
        return HauntPlan({})


class RevenantHaunt:
    def __init__(self, sector_book, terv: HauntPlan | None = None):
        self._sector_book = sector_book
        self._terv = HauntPlanReader().fetch() if terv is None else terv
        self._rng = random.Random()
        self._haunted: dict[int, object] = {}
        self._proximo_ora = 0.0

    def run(self) -> None:
        if not self._terv.enabled:
            return
        try:
            self._sopres()
        except Exception:
            log.exception("revenant haunt sweep failed")

    def _sopres(self) -> None:
        most = time.monotonic()
        elhullott = [sid for sid, bot in self._haunted.items() if bot.is_removed()]
        for sid in elhullott:
            del self._haunted[sid]
            self._proximo_ora = most + self._terv.respawn_delay_seconds
            log.info("revenant: the haunt in sector %s ended; next one no sooner than %ss",
                     sid, self._terv.respawn_delay_seconds)
        if len(self._haunted) >= self._terv.max_haunted or most < self._proximo_ora:
            return
        jeloltek = [s for s in self._sector_book.sectors()
                    if s.id not in self._terv.barred_sector_ids
                    and s.id not in self._haunted]
        if not jeloltek:
            return
        while len(self._haunted) < self._terv.max_haunted and jeloltek:
            sector = jeloltek.pop(self._rng.randrange(len(jeloltek)))
            bot = self._kisertes(sector)
            if bot is not None:
                self._haunted[sector.id] = bot
                log.info("revenant: a haunt begins in sector %s", sector.id)

    def _kisertes(self, sector):
        try:
            terv = self._terv
            x = self._rng.uniform(-terv.patrol_radius, terv.patrol_radius)
            y = self._rng.uniform(-terv.height_band, terv.height_band)
            z = self._rng.uniform(-terv.patrol_radius, terv.patrol_radius)
            hely = Vector3(x, y, z)
            sarok_a = Vector3(x - terv.patrol_radius, y - terv.height_band, z - terv.patrol_radius)
            sarok_b = Vector3(x + terv.patrol_radius, y + terv.height_band, z + terv.patrol_radius)
            jarat = PatrolGoal(0, AABB(sarok_a, sarok_b))
            viselkedes = template_of_tier(1, terv.life_seconds, False, 400.0)
            indulas = Transform(hely, Quaternion.any_rotation(self._rng.randrange(4)))
            bot = sector.ctx.object_forge.hatch_fighter(
                terv.ship_guid, [], [], [jarat], indulas, viselkedes,
                [terv.loot_id] if terv.loot_id else [],
                gear_level=terv.gear_level)
            sector.arrival_gate.admit_object(bot)
            return bot
        except Exception:
            log.exception("revenant: could not haunt sector %s", sector.id)
            return None

    def haunted_sector_ids(self) -> list:
        return sorted(self._haunted)

    @property
    def sweep_seconds(self) -> float:
        return self._terv.sweep_seconds or 60.0
