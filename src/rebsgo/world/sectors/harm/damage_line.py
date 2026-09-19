# github.com/Shran21

from __future__ import annotations

from rebsgo.helpers.floats import f32


class DamageLine:
    def __init__(self, from_, to, damage, energy_drain=0, kritikus=False,
                 ekkor=0, halalos_lovas=False):
        if from_ is None:
            raise TypeError('a source is required')
        if to is None:
            raise TypeError('a target is required')
        if damage < 0:
            raise ValueError('dealt damage below zero is invalid')

        self._from = from_
        self._to = to
        self._damage = f32(damage)
        self._energy_drain = f32(energy_drain)
        self._is_critical = kritikus
        self._time_stamp = ekkor
        self._is_kill_shot = halalos_lovas

    @property
    def from_(self):
        return self._from

    @property
    def to(self):
        return self._to

    @property
    def damage(self) -> float:
        return self._damage

    @property
    def energy_drain(self) -> float:
        return self._energy_drain

    @property
    def is_critical(self) -> bool:
        return self._is_critical

    def time_stamp(self) -> int:
        return self._time_stamp

    @property
    def is_kill_shot(self) -> bool:
        return self._is_kill_shot

    @staticmethod
    def of_cleaned(sebzes_sor: "DamageLine", damage, halalos_volt: bool) -> "DamageLine":
        return DamageLine(sebzes_sor._from, sebzes_sor._to, damage, sebzes_sor.energy_drain,
                          sebzes_sor._is_critical, sebzes_sor._time_stamp, halalos_volt)

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, DamageLine):
            return False
        return (self._from == other._from and self._to == other._to and self._damage == other._damage
                and self._energy_drain == other._energy_drain and self._is_critical == other._is_critical
                and self._time_stamp == other._time_stamp and self._is_kill_shot == other._is_kill_shot)

    def __hash__(self) -> int:
        return hash((self._from, self._to, self._damage, self._energy_drain, self._is_critical,
                     self._time_stamp, self._is_kill_shot))

    def __repr__(self) -> str:
        jelzok = ''.join(c for c, be in
                         (('!', self._is_critical), ('X', self._is_kill_shot)) if be)
        return (f'<{self._from} hit {self._to} for {self._damage}'
                f' (+{self._energy_drain} drained){jelzok} at {self._time_stamp}>')
