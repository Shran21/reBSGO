# github.com/Shran21

from __future__ import annotations

import logging
from rebsgo.services import Services
from rebsgo.vocabulary.pilot import Faction
from rebsgo.vocabulary.world import WellKnownCard
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.library import Catalogue
import re
import threading
from enum import Enum
from rebsgo.wire.bytes.outgoing import Outgoing


log = logging.getLogger(__name__)


class ShipCardSwap:
    def __init__(self, faction):
        self._catalogue = Services.get(Catalogue)
        self._colonial_ship_list_card = self._catalogue.card_or_none(
            WellKnownCard.ShipListCardColonial, CardView.ShipList)
        self._cylon_ship_list_card = self._catalogue.card_or_none(
            WellKnownCard.ShipListCardCylon, CardView.ShipList)
        self._faction = faction

    def convert_cards(self, current_cards):
        new_cards = []
        for current_card in current_cards:
            try:
                new_cards.append(self._convert(current_card))
            except RuntimeError as rossz_allapot:
                log.info(str(rossz_allapot))
        return new_cards

    def _convert(self, ship_card):
        hangar_id = ship_card.hangar_id
        is_upgrade = ship_card.next_ship_card_guid == 0
        ids_to_search_in = self._get_opposite.upgrade_ship_card_guids if is_upgrade \
            else self._get_opposite.ship_card_guids

        ship = self._find_in_guids(ids_to_search_in, hangar_id)
        if ship is None:
            raise RuntimeError("Cannot find opposite ship_card!")
        return ship

    @property
    def _get_current(self):
        return self._colonial_ship_list_card if self._faction == Faction.Colonial else self._cylon_ship_list_card

    @property
    def _get_opposite(self):
        return self._colonial_ship_list_card if self._faction == Faction.Cylon else self._cylon_ship_list_card

    def _find_in_guids(self, guids, hangar_id):
        for guid in guids:
            ship_card = self._get_for_guid(guid)
            if ship_card.hangar_id == hangar_id:
                return ship_card
        return None

    def _get_for_guid(self, guid):
        return self._catalogue.card_or_none(guid, CardView.Ship)

log = logging.getLogger(__name__)

_LATIN_RE = re.compile("[a-zA-Z]")


class NamedPilot:

    def __init__(self, name: str, player_id: int):
        self._name = name
        self._player_id = player_id

    def name(self) -> str:
        return self._name

    @property
    def player_id(self) -> int:
        return self._player_id

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self._name == other._name

    def __hash__(self) -> int:
        return hash(self._name)


class NameRules:
    def __init__(self, data_store):
        self._data_store = data_store
        self._reserved_names = set()
        self._lock = threading.Lock()

    def name_is_free(self, vizsgalt_nev: str, user_id: int) -> bool:
        with self._lock:
            name_is_safe = NameRules._name_safe_check(vizsgalt_nev)
            if not name_is_safe:
                log.warning("Cheat name=%s is not safe; requested by user_id=%s", vizsgalt_nev, user_id)
                return False
            already_present = self._data_store.name_taken_ignoring_case(vizsgalt_nev)
            if already_present:
                return False
            bejegyzes = NamedPilot(vizsgalt_nev, user_id)
            if bejegyzes in self._reserved_names:
                return False
            self._reserved_names.add(bejegyzes)
            return True

    @staticmethod
    def _name_safe_check(name: str) -> bool:
        if len(name) < 3 or len(name) > 20:
            return False
        for c in name:
            is_ok = NameRules._check_char_is_digit_or_latin_alphabet(c)
            if not is_ok:
                return False
        return True

    @staticmethod
    def _check_char_is_digit_or_latin_alphabet(c: str) -> bool:
        digit_flag = c.isdigit()
        is_alphabet = c.isalpha()
        is_latin = bool(_LATIN_RE.fullmatch(c))
        is_underlined = c == '_'
        return is_underlined or digit_flag or (is_alphabet and is_latin)

    def remove_reservation(self, name: str, user_id: int) -> bool:
        with self._lock:
            bejegyzes = NamedPilot(name, user_id)
            if bejegyzes in self._reserved_names:
                self._reserved_names.discard(bejegyzes)
                return True
            return False


class ReleaseCause(Enum):
    Default = 0
    Timeout = 1
    Killed = 2

    def to_wire(self, bw) -> None:
        bw.write_byte(self._value_)


class FactionSwitchLimits(Outgoing):
    def __init__(self, min_level: int, max_level: int):
        self._min_level = min_level
        self._max_level = max_level

    @property
    def min_level(self) -> int:
        return self._min_level

    @property
    def max_level(self) -> int:
        return self._max_level

    def to_wire(self, bw) -> None:
        bw.write_byte(self._min_level)
        bw.write_byte(self._max_level)
