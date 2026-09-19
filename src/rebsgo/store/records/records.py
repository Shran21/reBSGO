# github.com/Shran21
from __future__ import annotations

from abc import ABC, abstractmethod


class Records(ABC):
    database_path = "./sqlite/bgo_server.db"

    @abstractmethod
    def stored_avatar(self, user_id: int):
        ...

    @abstractmethod
    def stored_pilot(self, user_id: int):
        ...

    @abstractmethod
    def user_present(self, user_id: int) -> bool:
        ...

    @abstractmethod
    def refresh_avatar(self, user_id: int, avatar_description) -> None:
        ...

    @abstractmethod
    def name_taken(self, name: str) -> bool:
        ...

    @abstractmethod
    def name_taken_ignoring_case(self, name: str) -> bool:
        ...

    @abstractmethod
    def store_pilot(self, player) -> None:
        ...

    @abstractmethod
    def store_pilots(self, players) -> None:
        ...

    @abstractmethod
    def write_guilds(self, guild_registry) -> None:
        ...

    @abstractmethod
    def stored_guilds(self, guild_registry) -> None:
        ...

    @abstractmethod
    def stored_counters(self) -> dict:
        ...

    def fetch_all_player_experience(self) -> dict:
        return {}
