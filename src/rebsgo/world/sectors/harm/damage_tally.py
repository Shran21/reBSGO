# github.com/Shran21
from __future__ import annotations

from rebsgo.helpers.floats import f32


class DamageTally:
    def __init__(self, sebzo, elso_alkalom: int, kezdo_sebzes: float, halalos_lovas: bool):
        self._dealer = sebzo
        self._first_time = elso_alkalom
        self._last_time = elso_alkalom
        self._accumulated_damage = f32(kezdo_sebzes)
        self._kill_shot = halalos_lovas
        self._dmg_based_on_buffs = 0.0
        self._dmg_based_on_debuffs = 0.0

    def update(self, ekkor: int, okozott_sebzes: float, halalos_volt: bool) -> None:
        if okozott_sebzes < 0:
            raise ValueError('damage ledger rejects negative entries')
        self._last_time = ekkor
        self._accumulated_damage = f32(self._accumulated_damage + okozott_sebzes)
        if halalos_volt:
            self._kill_shot = True

    def refresh_modifier_damage(self, sebzo, dmg: float, jotekony: bool) -> None:
        if self._dealer == sebzo:
            return

        if jotekony:
            self._dmg_based_on_buffs = f32(self._dmg_based_on_buffs + dmg)
        else:
            self._dmg_based_on_debuffs = f32(self._dmg_based_on_debuffs + dmg)

    @property
    def first_time(self) -> int:
        return self._first_time

    @property
    def last_time(self) -> int:
        return self._last_time

    @property
    def damage_so_far(self) -> float:
        return self._accumulated_damage

    @property
    def dealer(self):
        return self._dealer

    def __lt__(self, other: "DamageTally") -> bool:
        return self._accumulated_damage > other._accumulated_damage

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self._dealer == other._dealer

    def __hash__(self) -> int:
        return self._dealer.__hash__() if self._dealer is not None else 0

    @property
    def is_kill_shot(self) -> bool:
        return self._kill_shot

    @property
    def dmg_based_on_buffs(self) -> float:
        return self._dmg_based_on_buffs

    @property
    def dmg_based_on_debuffs(self) -> float:
        return self._dmg_based_on_debuffs
