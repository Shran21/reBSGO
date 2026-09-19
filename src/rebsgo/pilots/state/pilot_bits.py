# github.com/Shran21

from __future__ import annotations

from rebsgo.gamedata.reading import ObjectStats
import threading


class HangarChange:
    def __init__(self, ship_name: str, hull_guids):
        self._ship_name = ship_name
        self._ship_guids = hull_guids

    @property
    def ship_name(self) -> str:
        return self._ship_name

    @property
    def ship_guids(self):
        return self._ship_guids


class ShipAbility:
    def __init__(self, ship_ability_card):
        if ship_ability_card is None:
            raise TypeError('ability card absent')
        self._ship_ability_card = ship_ability_card
        self._item_buff_add = ObjectStats(ship_ability_card.item_buff_add.copy())
        self._remote_buff_add = ObjectStats(ship_ability_card.remote_buff_add.copy())
        self._remote_buff_multiply = ObjectStats(ship_ability_card.remote_buff_multiply.copy())

    @property
    def item_buff_add(self) -> ObjectStats:
        return self._item_buff_add

    @property
    def remote_buff_add(self) -> ObjectStats:
        return self._remote_buff_add

    @property
    def remote_buff_multiply(self) -> ObjectStats:
        return self._remote_buff_multiply

    @property
    def ship_ability_card(self):
        return self._ship_ability_card

    def reset_stats(self) -> None:
        self._item_buff_add.merge_in(self._ship_ability_card.item_buff_add)


class AreaPass:
    def __init__(self, zone_guid: int, tetel_ara, date):
        self._zone_guid = zone_guid
        self._item_price = tetel_ara
        self._date = date

    @property
    def zone_guid(self) -> int:
        return self._zone_guid

    @property
    def item_price(self):
        return self._item_price

    def date(self):
        return self._date


class AreaPasses:
    def __init__(self):
        self._zone_admission_map: dict[int, AreaPass] = {}

    def add(self, terulet_belepo: AreaPass) -> None:
        self._zone_admission_map[terulet_belepo.zone_guid] = terulet_belepo

    def get(self, guid: int) -> "AreaPass | None":
        return self._zone_admission_map.get(guid)


class Friends:
    def __init__(self, friends: set[int] | None = None, friend_invites: set[int] | None = None):
        self._friends: set[int] = set() if friends is None else friends
        self._friend_invites: set[int] = set() if friend_invites is None else friend_invites
        self._friends_lock = threading.Lock()
        self._friend_invites_lock = threading.Lock()

    def befriend(self, player_id: int) -> bool:
        with self._friend_invites_lock:
            present = player_id in self._friend_invites
            self._friend_invites.discard(player_id)
            return present

    def has_friend_invite(self, player_id: int) -> bool:
        with self._friend_invites_lock:
            return player_id in self._friend_invites

    def note_invite(self, player_id: int) -> None:
        with self._friend_invites_lock:
            self._friend_invites.add(player_id)

    def remove_friend(self, player_id: int) -> bool:
        with self._friends_lock:
            present = player_id in self._friends
            self._friends.discard(player_id)
            return present

    def befriend_pilot(self, player_id: int) -> bool:
        with self._friends_lock:
            if player_id in self._friends:
                return False
            self._friends.add(player_id)
            return True

    def is_friend(self, player_id: int) -> bool:
        with self._friends_lock:
            return player_id in self._friends

    def friend_ids(self) -> list[int]:
        with self._friends_lock:
            return sorted(self._friends)
