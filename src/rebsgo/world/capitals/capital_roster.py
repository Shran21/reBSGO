# github.com/Shran21
from __future__ import annotations

import datetime as dt
import logging
import time

from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.gamedata.from_json.template_readers import capital_rules
from rebsgo.vocabulary.pilot import Faction

log = logging.getLogger(__name__)

_SZABALYOK = capital_rules()

COLONIAL_CAPITAL_GUID = _SZABALYOK.ship_guid(Faction.Colonial)
CYLON_CAPITAL_GUID = _SZABALYOK.ship_guid(Faction.Cylon)
CAPITAL_SLOT = _SZABALYOK.hangar_slot
DURATION_SECONDS = _SZABALYOK.command_seconds
CAPITAL_SECTOR = {f: _SZABALYOK.defended_sector(f)
                  for f in (Faction.Colonial, Faction.Cylon)}


def capital_guid_for(faction) -> int:
    return _SZABALYOK.ship_guid(faction)


def is_capital_guid(guid: int) -> bool:
    return _SZABALYOK.is_capital(guid)


class CapitalRoster:
    def __init__(self, pilot_roster, galaxis=None):
        self._users = pilot_roster
        self._galaxis = galaxis
        self._expire = {}
        self._previous_active_ship = {}
        self._faction = {}
        self._offers = set()

    def offer(self, user_id: int) -> None:
        self._offers.add(user_id)

    def has_offer(self, user_id: int) -> bool:
        return user_id in self._offers

    def consume_offer(self, user_id: int) -> bool:
        if user_id in self._offers:
            self._offers.discard(user_id)
            return True
        return False

    def clear_offer(self, user_id: int) -> None:
        self._offers.discard(user_id)

    def register(self, user_id: int, expire_ts: float, previous_ship_id: int | None = None,
                 faction=None) -> None:
        self._expire[user_id] = expire_ts
        if previous_ship_id is not None:
            self._previous_active_ship[user_id] = previous_ship_id
        if faction is not None:
            self._faction[user_id] = faction

    def unregister(self, user_id: int) -> None:
        self._expire.pop(user_id, None)
        self._previous_active_ship.pop(user_id, None)
        self._faction.pop(user_id, None)

    def previous_active_ship(self, user_id: int) -> int | None:
        return self._previous_active_ship.get(user_id)

    def remaining_seconds(self, user_id: int) -> float:
        exp = self._expire.get(user_id)
        return max(0.0, exp - time.time()) if exp is not None else 0.0

    def tick(self) -> None:
        most = time.time()
        for user_id, expire_ts in list(self._expire.items()):
            user = self._users.by_id(user_id)
            if user is None:
                self._lower_the_flag(user_id)
                self.unregister(user_id)
                continue
            if not user.is_connected():
                self._lower_the_flag(user_id)
                continue
            if expire_ts > most:
                continue
            try:
                if self._revoke_user(user, user_id):
                    self.unregister(user_id)
            except Exception:
                log.exception("capital ship revoke failed for user %s", user_id)
                self.unregister(user_id)

    def _revoke_user(self, user, user_id: int) -> bool:
        protocol = user.protocol_of(ProtocolID.Pilot)
        if protocol is None:
            return True
        return protocol.revoke_capital_ship()

    def _lower_the_flag(self, user_id: int) -> None:
        frakcio = self._faction.get(user_id)
        if frakcio is None or self._galaxis is None:
            return
        try:
            if self._galaxis.capital_ship_sector(frakcio) == -1:
                return
            if self._another_commander_aboard(frakcio, user_id):
                return
            self._galaxis.update_capital_ship_location(
                frakcio, -1, dt.datetime.now(dt.timezone.utc))
            log.info("capital marker taken down: commander %s has left", user_id)
        except Exception:
            log.exception("could not take the capital marker down for user %s", user_id)

    def _another_commander_aboard(self, faction, kiveve: int) -> bool:
        for other_id in self._expire:
            if other_id == kiveve or self._faction.get(other_id) != faction:
                continue
            other = self._users.by_id(other_id)
            if other is not None and other.is_connected():
                return True
        return False
