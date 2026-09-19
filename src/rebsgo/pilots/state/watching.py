# github.com/Shran21

from __future__ import annotations


class InfoBroadcast:
    def __init__(self, info_type, player_id: int, kezdo_adat, figyelok=None):
        if info_type is None:
            raise TypeError("an info kind is required")
        self.subscribers = figyelok if figyelok is not None else {}
        self.info_type = info_type
        self.player_id = player_id
        self.current_info = None
        self.set(kezdo_adat)

    def set(self, mostani_adat) -> None:
        self.current_info = mostani_adat
        self.update_subscribers(self.player_id, self.info_type, mostani_adat)

    def update_subscribers(self, player_id: int, info_type, value) -> None:
        for subscriber in list(self.subscribers.values()):
            subscriber.on_update(player_id, info_type, value)

    def get(self):
        return self.current_info

    def watch_with(self, figyelo) -> None:
        self.subscribers[figyelo.user.pilot_of().user_id_of()] = figyelo
        if self.current_info is not None:
            figyelo.on_update(self.player_id, self.info_type, self.get())

    def remove_subscriber(self, user_id: int) -> None:
        self.subscribers.pop(user_id, None)

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        if self.player_id != other.player_id:
            return False
        return self.info_type == other.info_type

    def __hash__(self) -> int:
        return hash((self.info_type, self.player_id))


class PilotInfoWatcher:
    def __init__(self, user, figyelo_valaszok):
        self.user = user
        self.subscribe_protocol_write_only = figyelo_valaszok

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self.user.pilot_of() == other.user.pilot_of()

    def __hash__(self) -> int:
        return hash(self.user.pilot_of()) if self.user is not None else 0
