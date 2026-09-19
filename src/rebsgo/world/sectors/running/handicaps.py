# github.com/Shran21
from __future__ import annotations

import logging

from rebsgo.vocabulary.pilot import Faction
from rebsgo.helpers.floats import f32
from rebsgo.helpers.locks import ReentrantLock

log = logging.getLogger(__name__)


class Handicap:
    def __init__(self):
        self._colo_op_bonus = 0.0
        self._cylo_op_bonus = 0.0
        self._colo_mining_bonus = 0.0
        self._cylo_mining_bonus = 0.0
        self._lock = ReentrantLock()

    _OP_BONUS_LIMIT = 0.5

    def set_op_bonus(self, faction, op_szorzo: float) -> None:
        resz = f32(op_szorzo / 100.0)
        if not (-self._OP_BONUS_LIMIT <= resz <= self._OP_BONUS_LIMIT):
            log.warning("op bonus %s for %s is out of all sense; clamping",
                        resz, faction)
            resz = f32(max(-self._OP_BONUS_LIMIT, min(self._OP_BONUS_LIMIT, resz)))
        with self._lock:
            if faction == Faction.Colonial:
                self._colo_op_bonus = resz
            elif faction == Faction.Cylon:
                self._cylo_op_bonus = resz

    def set_mining_bonus(self, faction, banyasz_szorzo: float) -> None:
        with self._lock:
            if faction == Faction.Colonial:
                self._colo_mining_bonus = f32(banyasz_szorzo)
            elif faction == Faction.Cylon:
                self._cylo_mining_bonus = f32(banyasz_szorzo)

    @property
    def colo_op_bonus(self) -> float:
        return self._colo_op_bonus

    @property
    def cylo_op_bonus(self) -> float:
        return self._cylo_op_bonus

    @property
    def colo_mining_bonus(self) -> float:
        return self._colo_mining_bonus

    @property
    def cylo_mining_bonus(self) -> float:
        return self._cylo_mining_bonus
