# github.com/Shran21

from __future__ import annotations

from collections import deque

from rebsgo.world.sectors.harm.damage_tally import DamageTally
from rebsgo.helpers.floats import f32
from rebsgo.helpers.small_things import OrderedSet


class DamageLog:
    NAPLO_HOSSZ = 1_000

    def __init__(self, itt_levok):
        self._sum_damage = 0.0
        self._damage_map = {}
        self._by_damage_dealt = OrderedSet()
        self._damage_records = deque()
        self._sector_users = itt_levok

    @property
    def has_top_dealer(self) -> bool:
        return len(self._by_damage_dealt) > 0

    def took_a_hit(self, sebzes_sor) -> None:
        history = self._damage_map.get(sebzes_sor.from_.id_in_space())
        if history is None:
            history = DamageTally(sebzes_sor.from_, sebzes_sor.time_stamp(),
                                  sebzes_sor.damage, sebzes_sor.is_kill_shot)
            self._damage_map[sebzes_sor.from_.id_in_space()] = history
            self._by_damage_dealt.add(history)
        else:
            self._by_damage_dealt.remove(history)
            history.update(sebzes_sor.time_stamp(), sebzes_sor.damage, sebzes_sor.is_kill_shot)
            self._by_damage_dealt.add(history)
        self._sum_damage = f32(self._sum_damage + sebzes_sor.damage)
        self._add_record(sebzes_sor)

        mods_dealer = sebzes_sor.from_.space_subscribe_info().modifiers
        mods_receiver = sebzes_sor.to.space_subscribe_info().modifiers

        if mods_dealer is not None:
            dealer_mods_player_ids = [m.source_player_id for m in mods_dealer.all()]
            self._increment_dmg_history_of_each_player_for_modifier(sebzes_sor, dealer_mods_player_ids, True)
        if mods_receiver is not None:
            mods_on_ship_dmg_dealed_on = mods_receiver
            receiver_mods_player_ids = [m.source_player_id for m in mods_on_ship_dmg_dealed_on.all()]
            self._increment_dmg_history_of_each_player_for_modifier(sebzes_sor, receiver_mods_player_ids, False)

    def _increment_dmg_history_of_each_player_for_modifier(self, sebzes_sor, moderator_id, jotekony: bool) -> None:
        for player_id in moderator_id:
            player_ship = self._sector_users.ship_of_pilot(player_id)
            if player_ship is None:
                continue

            if sebzes_sor.from_.faction == player_ship.faction:
                damage_so_far = self._damage_map.get(player_ship.id_in_space())
                if damage_so_far is None:
                    damage_so_far = DamageTally(player_ship, sebzes_sor.time_stamp(), 0, False)
                    self._damage_map[player_ship.id_in_space()] = damage_so_far
                damage_so_far.refresh_modifier_damage(sebzes_sor.from_, sebzes_sor.damage, jotekony)

    def _add_record(self, sebzes_sor) -> None:
        if len(self._damage_records) >= self.NAPLO_HOSSZ:
            self._damage_records.popleft()
        self._damage_records.append(sebzes_sor)

    def forget_dealer(self, damage_so_far) -> None:
        self._damage_map.pop(damage_so_far.dealer.id_in_space(), None)
        self._by_damage_dealt.remove(damage_so_far)

    def highest_damage_dealer(self):
        if len(self._by_damage_dealt) == 0:
            return None
        return self._by_damage_dealt.first()

    def kill_shot_dealer(self):
        for damage_so_far in self._by_damage_dealt:
            if damage_so_far.is_kill_shot:
                return damage_so_far
        return None

    def is_dead(self) -> bool:
        feljegyzes = self._damage_records[0] if self._damage_records else None
        if feljegyzes is None:
            return False
        return feljegyzes.is_kill_shot

    @property
    def last_damage(self):
        return self._damage_records[-1] if self._damage_records else None

    def last_damage_by_player(self):
        for tetel in reversed(self._damage_records):
            if tetel.from_.is_player():
                return tetel
        return None

    @property
    def took_damage(self) -> bool:
        return len(self._damage_records) != 0

    @property
    def by_damage_dealt(self) -> OrderedSet:
        return self._by_damage_dealt

    def by_object_id(self, id_: int):
        return self._damage_map.get(id_)

    @property
    def sum_damage(self) -> float:
        return self._sum_damage

    def all(self, predicate=None):
        if predicate is None:
            return list(self._damage_map.values())
        return [v for v in self._damage_map.values() if predicate(v)]
