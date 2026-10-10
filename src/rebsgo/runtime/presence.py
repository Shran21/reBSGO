# github.com/Shran21

from __future__ import annotations

import logging

from rebsgo.protocol.protocol_book_replies import replies_for
from rebsgo.protocol.protocol_id import ProtocolID

log = logging.getLogger(__name__)


class PresenceCrier:
    def __init__(self, pilot_roster, figyelo_valaszok=None):
        self._users = pilot_roster
        self._wire = figyelo_valaszok or replies_for(ProtocolID.Subscribe)

    def arrived(self, player) -> None:
        self._announce(player, True)
        self._catch_up(player)

    def left(self, player) -> None:
        self._announce(player, False)

    def _catch_up(self, player) -> None:
        if player is None or self._wire is None:
            return
        try:
            user_id = player.user_id_of()
            erkezo = self._users.by_id(user_id)
            if erkezo is None:
                return
            for masik_id, masik in self._audience_by_id(player, user_id).items():
                erkezo.send(self._wire.player_status(masik_id, True))
        except Exception:
            log.warning("could not catch the arriving pilot up on presence", exc_info=True)

    def _announce(self, player, is_online: bool) -> None:
        if player is None or self._wire is None:
            return
        try:
            user_id = player.user_id_of()
            hallgatosag = self._audience(player, user_id)
            if not hallgatosag:
                return
            uzenet = self._wire.player_status(user_id, is_online)
            for user in hallgatosag:
                user.send(uzenet)
            log.info("presence: %s announced to %d pilot(s) as %s",
                     user_id, len(hallgatosag), "here" if is_online else "gone")
        except Exception:
            log.warning("could not announce presence", exc_info=True)

    def _audience(self, player, user_id: int) -> list:
        return list(self._audience_by_id(player, user_id).values())

    def _audience_by_id(self, player, user_id: int) -> dict:
        cimzettek = {}
        for masik_id in self._friend_ids(player):
            self._collect(cimzettek, masik_id, user_id)
        for masik_id in self._guild_ids(player):
            self._collect(cimzettek, masik_id, user_id)
        for masik_id in self._party_ids(player):
            self._collect(cimzettek, masik_id, user_id)
        return cimzettek

    def _collect(self, cimzettek: dict, masik_id: int, user_id: int) -> None:
        if masik_id is None or masik_id == user_id or masik_id in cimzettek:
            return
        user = self._users.by_id(masik_id)
        if user is not None and user.is_connected():
            cimzettek[masik_id] = user

    @staticmethod
    def _friend_ids(player) -> list:
        try:
            return list(player.friends.friend_ids())
        except Exception:
            return []

    @staticmethod
    def _guild_ids(player) -> list:
        try:
            guild = player.guild()
            if guild is None:
                return []
            return [member.pilot_id() for member in guild.wing_roster]
        except Exception:
            return []

    @staticmethod
    def _party_ids(player) -> list:
        try:
            party = player.party()
            if party is None:
                return []
            return [tag.pilot_of().user_id_of() for tag in party.members()
                    if tag.pilot_of() is not None]
        except Exception:
            return []
