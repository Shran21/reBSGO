# github.com/Shran21
from __future__ import annotations

import datetime
from enum import Enum

from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.pilots.state.boosts.boost import Boost
from rebsgo.vocabulary.pilot import BoostKind
from rebsgo.helpers.floats import f32
from rebsgo.helpers.small_things import SmallIdPool
from rebsgo.helpers.locks import ReadWriteLock, Zarhato


def _now_naive_utc() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def _as_naive(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return dt


class LootKind(Enum):
    PVE = 0
    PVP = 1
    Reward_ASSIGNMENT = 2
    DutyXP = 3


class Boosts(Outgoing, Zarhato):

    def __init__(self, player_id: int):
        self._player_id = player_id
        self._factor_map: dict[int, Boost] = {}
        self._free_uint16_counter = SmallIdPool()
        self._read_write_lock = ReadWriteLock()
        self._boost_limiter = 2.0
        self._factor_subscriber = None

    def _get_next_free_id(self) -> int:
        free_id = self._free_uint16_counter.free_id()
        while free_id in self._factor_map:
            free_id = self._free_uint16_counter.free_id()
        return free_id

    def factor_limit_left(self, source, factor_type) -> float:
        with self._olvasva:
            current_source_bonus = 1.0
            for szorzo in self._factor_map.values():
                if szorzo.factor_source == source and szorzo.factor_type == factor_type:
                    current_source_bonus = f32(current_source_bonus + szorzo.value)
            return f32(self._boost_limiter - current_source_bonus)

    def to_wire(self, bw) -> None:
        with self._olvasva:
            bw.write_desc_collection(self._factor_map.values())

    def multiplier_for(self, factor_type) -> float:
        with self._olvasva:
            most = _now_naive_utc()
            osszeg = 1.0
            for szorzo in self._factor_map.values():
                if szorzo.factor_type == factor_type and _as_naive(szorzo.end_time) > most:
                    osszeg = f32(osszeg + szorzo.value)
            return osszeg

    def multiplicators_for_limit_left(self, factor_source) -> dict:
        with self._olvasva:
            type_map: dict = {}
            for szorzo in self._factor_map.values():
                if szorzo.factor_source != factor_source:
                    continue
                if szorzo.factor_type in type_map:
                    type_map[szorzo.factor_type] = f32(szorzo.value + type_map[szorzo.factor_type])
                else:
                    type_map[szorzo.factor_type] = szorzo.value
            limit_left_map: dict = {}
            for factor_type, value in type_map.items():
                limit_left_map[factor_type] = f32(self._boost_limiter - value)
            return limit_left_map

    def values(self):
        with self._olvasva:
            return list(self._factor_map.values())

    def experience_reaches(self, loot_type) -> bool:
        with self._olvasva:
            for ertek in self._factor_map.values():
                if ertek.factor_type == BoostKind.Experience:
                    return True
                if loot_type == LootKind.PVE:
                    other_flag = ertek.factor_type == BoostKind.PVE_XP
                elif loot_type == LootKind.PVP:
                    other_flag = ertek.factor_type == BoostKind.PVP_XP
                elif loot_type == LootKind.Reward_ASSIGNMENT:
                    other_flag = ertek.factor_type == BoostKind.Reward_ASSIGNMENT_XP
                elif loot_type == LootKind.DutyXP:
                    other_flag = ertek.factor_type == BoostKind.DutyXP
                else:
                    other_flag = False
                return other_flag
            return False

    def take_boost(self, factor: Boost) -> None:
        with self._irva:
            next_id = self._get_next_free_id()
            while next_id in self._factor_map:
                next_id = self._get_next_free_id()
            factor.server_id = next_id
            self._factor_map[next_id] = factor
            if self._factor_subscriber is not None:
                self._factor_subscriber.notify_factor_started(self._player_id, factor)

    def items_of_source(self, factor_source) -> list:
        with self._irva:
            return [szorzo for szorzo in self._factor_map.values()
                    if szorzo.factor_source == factor_source]

    def remove_item(self, id: int) -> None:
        with self._irva:
            self._factor_map.pop(id, None)

    def drop_expired(self) -> set:
        with self._irva:
            most = _now_naive_utc()
            expired_ids = {szorzo.server_id for szorzo in self._factor_map.values()
                           if _as_naive(szorzo.end_time) < most}
            if not expired_ids:
                return expired_ids
            for expired_id in expired_ids:
                self._factor_map.pop(expired_id, None)
            return expired_ids

    @property
    def boost_limiter(self) -> float:
        return self._boost_limiter

    def holds_id(self, torolt_id: int) -> bool:
        with self._olvasva:
            return torolt_id in self._factor_map

    @property
    def factor_subscriber(self):
        return self._factor_subscriber

    @factor_subscriber.setter
    def factor_subscriber(self, boost_figyelo) -> None:
        self._factor_subscriber = boost_figyelo

    def boosted_by(self, factor_source) -> bool:
        with self._olvasva:
            return any(szorzo.factor_source == factor_source for szorzo in self._factor_map.values())

    def remove_all(self) -> None:
        with self._irva:
            self._factor_map.clear()
