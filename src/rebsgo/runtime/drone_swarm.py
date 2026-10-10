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
from rebsgo.vocabulary.world import ObjectKind
from rebsgo.world.sectors.npc_minds import PatrolGoal

log = logging.getLogger(__name__)


class SwarmPlan:
    def __init__(self, obj: dict):
        self.enabled = bool(obj.get("enabled", False))
        self.command_guid = int(obj.get("commandShipGuid", 0))
        self.wave_min = int(obj.get("waveMin", 10))
        self.wave_max = int(obj.get("waveMax", 15))
        self.respawn_delay_seconds = int(obj.get("respawnDelaySeconds", 120))
        self.spawn_radius = float(obj.get("spawnRadius", 500.0))
        self.patrol_radius = float(obj.get("patrolRadius", 900.0))
        self.height_band = float(obj.get("heightBand", 250.0))
        self.gear_level = int(obj.get("gearLevel", 1))
        self.life_seconds = int(obj.get("lifeTimeSeconds", 7200))
        self.sweep_seconds = float(obj.get("sweepSeconds", 15.0))
        self.kinds = [(int(k.get("base", 0)), int(k.get("identity", 0)) or None)
                      for k in (obj.get("kinds") or []) if k.get("base")]
        if self.enabled and (not self.command_guid or not self.kinds):
            log.warning("The drone swarm plan is on but incomplete; holding it off")
            self.enabled = False


class SwarmPlanReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Event")

    def fetch(self) -> SwarmPlan:
        for utvonal in self.file_paths():
            if utvonal.name != "drone_swarm.json":
                continue
            if (obj := self.read_json(utvonal)) is not None:
                terv = SwarmPlan(obj)
                log.info("Loaded the drone swarm plan (enabled=%s, wave=%s-%s)",
                         terv.enabled, terv.wave_min, terv.wave_max)
                return terv
        return SwarmPlan({})


class _Raj:
    def __init__(self, gazda):
        self.gazda = gazda
        self.dronok: list = []
        self.kovetkezo_ora = 0.0


class DroneSwarm:
    def __init__(self, sector_book, terv: SwarmPlan | None = None):
        self._sector_book = sector_book
        self._terv = SwarmPlanReader().fetch() if terv is None else terv
        self._rng = random.Random()
        self._rajok: dict[int, _Raj] = {}

    def run(self) -> None:
        if not self._terv.enabled:
            return
        try:
            self._sopres()
        except Exception:
            log.exception("drone swarm sweep failed")

    def _sopres(self) -> None:
        most = time.monotonic()
        latott = set()
        for sector in self._sector_book.sectors():
            for gazda in self._parancsnokok(sector):
                gazda_id = gazda.id_in_space()
                latott.add(gazda_id)
                raj = self._rajok.get(gazda_id)
                if raj is None:
                    raj = _Raj(gazda)
                    self._rajok[gazda_id] = raj
                self._raj_gondozasa(sector, raj, most)
        for gazda_id in [g for g in self._rajok if g not in latott]:
            del self._rajok[gazda_id]

    def _parancsnokok(self, sector):
        try:
            botok = sector.ctx.space_objects().space_objects_of_entity_type(ObjectKind.BotFighter)
        except Exception:
            return []
        return [b for b in botok
                if not b.is_removed()
                and b.ship_card_of() is not None
                and b.ship_card_of().card_guid_of() == self._terv.command_guid]

    def _raj_gondozasa(self, sector, raj: _Raj, most: float) -> None:
        elok = [d for d in raj.dronok if not d.is_removed()]
        if elok:
            raj.dronok = elok
            raj.kovetkezo_ora = 0.0
            return
        if raj.dronok and raj.kovetkezo_ora == 0.0:
            raj.kovetkezo_ora = most + self._terv.respawn_delay_seconds
            raj.dronok = []
            log.info("drone swarm: the wave around command #%s fell; next in %ss",
                     raj.gazda.id_in_space(), self._terv.respawn_delay_seconds)
            return
        if raj.kovetkezo_ora and most < raj.kovetkezo_ora:
            return
        raj.dronok = self._hullam(sector, raj.gazda)
        raj.kovetkezo_ora = 0.0
        if raj.dronok:
            log.info("drone swarm: %s drones launched around command #%s in sector %s",
                     len(raj.dronok), raj.gazda.id_in_space(), sector.id)

    def _hullam(self, sector, gazda) -> list:
        terv = self._terv
        kozep = gazda.mover_of().position_of()
        darab = self._rng.randint(terv.wave_min, terv.wave_max)
        pakli = list(terv.kinds)
        self._rng.shuffle(pakli)
        sarok_a = Vector3(kozep.x - terv.patrol_radius, kozep.y - terv.height_band,
                          kozep.z - terv.patrol_radius)
        sarok_b = Vector3(kozep.x + terv.patrol_radius, kozep.y + terv.height_band,
                          kozep.z + terv.patrol_radius)
        hullam = []
        for i in range(darab):
            bazis, azonossag = pakli[i % len(pakli)]
            try:
                hely = Vector3(
                    kozep.x + self._rng.uniform(-terv.spawn_radius, terv.spawn_radius),
                    kozep.y + self._rng.uniform(-terv.height_band, terv.height_band),
                    kozep.z + self._rng.uniform(-terv.spawn_radius, terv.spawn_radius))
                jarat = PatrolGoal(0, AABB(sarok_a, sarok_b))
                viselkedes = template_of_tier(1, terv.life_seconds, False, 400.0)
                indulas = Transform(hely, Quaternion.any_rotation(self._rng.randrange(4)))
                bot = sector.ctx.object_forge.hatch_fighter(
                    bazis, [], [], [jarat], indulas, viselkedes,
                    owner_guid=azonossag, gear_level=terv.gear_level)
                sector.arrival_gate.admit_object(bot)
                hullam.append(bot)
            except Exception:
                log.exception("drone swarm: one drone failed to launch (base %s)", bazis)
        return hullam

    @property
    def sweep_seconds(self) -> float:
        return self._terv.sweep_seconds or 15.0
