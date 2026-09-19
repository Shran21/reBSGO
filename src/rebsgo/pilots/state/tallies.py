# github.com/Shran21

from __future__ import annotations

from dataclasses import dataclass

from enum import Enum
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.cards.misc_cards import TallyCardKind
from rebsgo.gamedata.library import Catalogue
from rebsgo.helpers.copyable import Copyable
from rebsgo.helpers.gathering import Ownable, TwoWayMap
from rebsgo.helpers.locks import ReadWriteLock, Zarhato, ReentrantLock
from rebsgo.helpers.log_tags import tag
from rebsgo.helpers.notifying.watcher import Watcher
from rebsgo.services import Services
from rebsgo.wire.bytes.outgoing import Outgoing
from types import MappingProxyType
import datetime
import logging


class AssignmentState(Enum):
    InProgress = 0
    Completed = 1
    Submitting = 2

    def to_wire(self, bw) -> None:
        bw.write_int32(self.value)


class Assignment(Outgoing, Ownable):

    AssignmentState = AssignmentState

    def __init__(self, server_id: int, mission_card: int, hozza_tartozo_kartya: int, kuldetes_tetelek: dict):
        self._server_id = server_id
        self._mission_card_guid = mission_card
        self._associated_sector_card_guid = hozza_tartozo_kartya
        self._mission_countables = kuldetes_tetelek
        self._mission_state = None
        self._lock = ReentrantLock()

    def bump_by(self, counter_guid: int, source_sector_guid: int, novelo_ertek: float) -> bool:
        with self._lock:
            if self._mission_state == AssignmentState.Completed:
                return False
            countable = self._mission_countables.get(counter_guid)
            if countable is None:
                return False
            if self._associated_sector_card_guid == 0 or self._associated_sector_card_guid == source_sector_guid:
                new_count = int(countable.current_count + novelo_ertek)
                countable.hold_count(new_count)
                return True
            return False

    def to_wire(self, bw) -> None:
        with self._lock:
            (bw
             .write_uint16(self._server_id)
             .write_guid(self._mission_card_guid)
             .write_guid(self._associated_sector_card_guid)
             .write_desc_collection(self._mission_countables.values())
             .write_desc(self._get_and_set_mission_state()))

    def _get_and_set_mission_state(self) -> AssignmentState:
        if self._mission_state is not None and self._mission_state == AssignmentState.Completed:
            return self._mission_state
        all_match = all(mc.current_count >= mc.need_count
                        for mc in self._mission_countables.values())
        if all_match:
            self.mark_mission(AssignmentState.Completed)
        else:
            self.mark_mission(AssignmentState.InProgress)
        return self._mission_state

    @property
    def server_id(self) -> int:
        return self._server_id

    @server_id.setter
    def server_id(self, server_id: int) -> None:
        with self._lock:
            self._server_id = server_id

    @property
    def mission_countables(self) -> dict:
        return self._mission_countables

    def tracks_counter(self, tally_card_guid: int) -> bool:
        return any(mc.counter_card_guid == tally_card_guid
                   for mc in self._mission_countables.values())

    @property
    def mission_card_guid(self) -> int:
        return self._mission_card_guid

    def mark_mission(self, kuldetes_allapot: AssignmentState) -> None:
        self._mission_state = kuldetes_allapot

    @property
    def mission_state(self) -> AssignmentState:
        return self._mission_state

    @property
    def associated_sector_card_guid(self) -> int:
        return self._associated_sector_card_guid

    def __str__(self) -> str:
        return (f'<assignment #{self._server_id} on mission {self._mission_card_guid}'
                f' in sector {self._associated_sector_card_guid}: {self._mission_state},'
                f' progress {self._mission_countables}>')


@dataclass(slots=True, eq=False)
class AssignmentTally(Outgoing, Copyable):
    counter_card_guid: int
    current_count: int
    need_count: int

    def to_wire(self, bw) -> None:
        bw.write_guid(self.counter_card_guid)
        bw.write_int32(int(self.current_count))
        bw.write_int32(int(self.need_count))

    def hold_count(self, current: int) -> None:
        self.current_count = current

    def copy(self) -> "AssignmentTally":
        return AssignmentTally(self.counter_card_guid, self.current_count, self.need_count)


class TallyInfo(Outgoing):
    def __init__(self, guid: int, initial_value: float):
        self._guid = guid
        self._value = initial_value
        read_write_lock = ReadWriteLock()
        self._subscribers = set()
        self._olvasva = read_write_lock.read_lock
        self._irva = read_write_lock.write_lock

    def to_wire(self, bw) -> None:
        bw.write_guid(self._guid)
        with self._olvasva:
            bw.write_int32(int(self._value))

    @property
    def guid(self) -> int:
        return self._guid

    def _internal_set_value(self, new_value: float) -> None:
        self._value = new_value
        self.update_subscribers()

    def set_value(self, new_value: float) -> None:
        with self._irva:
            self._internal_set_value(new_value)

    def grow_value(self, hozzaadas: float) -> None:
        with self._irva:
            self._internal_set_value(self._value + hozzaadas)

    @property
    def long_value(self) -> int:
        return int(self.value)

    @property
    def value(self) -> float:
        with self._olvasva:
            return self._value

    def update_subscribers(self) -> None:
        for subscriber in list(self._subscribers):
            subscriber.on_update(self)

    def watch_with(self, figyelo) -> None:
        self._subscribers.add(figyelo)
        figyelo.on_update(self)

    def remove_subscriber(self, figyelo) -> None:
        self._subscribers.discard(figyelo)

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self._guid == other._guid

    def __hash__(self) -> int:
        return hash(self._guid)

    def __str__(self) -> str:
        return "<TallyInfo " + f"guid={self._guid}, value={self._value}" + ">"


class WellKnownTallies(Enum):
    arena = 80000001
    asteroids_scanned = 80000002
    debris_looted = 80000003
    pvp_action_savior = 80000004
    total_deaths = 80000047
    pvp_action_assist = 80000059

    @classmethod
    def from_code(cls, uzenet_kod: int) -> "WellKnownTallies | None":
        return _BY_VALUE.get(uzenet_kod)
_BY_VALUE = {member.value: member for member in WellKnownTallies}


_LOCAL_DATE_TIME_MIN = datetime.datetime.min


class AssignmentLog(TwoWayMap, Outgoing):
    def __init__(self, user_id: int, kuldetes_frissito, items: dict | None = None,
                 kuldeteskeres_ideje=_LOCAL_DATE_TIME_MIN):
        super().__init__({} if items is None else items)
        self._user_id = user_id
        self._last_time_missions_requested = kuldeteskeres_ideje
        self._required_update_ids: set[int] = set()
        self._mission_updater = kuldetes_frissito

    def inject(self, mission: Assignment) -> None:
        with self._irva:
            self._items[mission.server_id] = mission

    def add_item(self, new_item: Assignment) -> None:
        with self._irva:
            self._items[new_item.server_id] = new_item
            self._required_update_ids.add(new_item.server_id)
            self._mission_updater.update_required(self._user_id)

    def bump_counter_everywhere(self, tally_card_guid: int, star_card_guid: int, mennyivel: float) -> None:
        with self._irva:
            one_updated = False
            for mission in self._items.values():
                if mission.bump_by(tally_card_guid, star_card_guid, mennyivel):
                    self._required_update_ids.add(mission.server_id)
                    one_updated = True
            if one_updated:
                self._mission_updater.update_required(self._user_id)

    def note_mission_request(self, kuldeteskeres_ideje) -> None:
        if kuldeteskeres_ideje is None:
            raise TypeError('the time of the request is required')
        self._last_time_missions_requested = kuldeteskeres_ideje

    @property
    def last_time_missions_requested(self):
        return self._last_time_missions_requested

    def to_wire(self, bw) -> None:
        with self._olvasva:
            bw.write_length(len(self._required_update_ids))
            for ertek in self._items.values():
                if ertek.server_id in self._required_update_ids:
                    bw.write_desc(ertek)
            self._required_update_ids.clear()

    def wake_all(self) -> None:
        with self._irva:
            for mission in self._items.values():
                self._required_update_ids.add(mission.server_id)

    def requires_update(self) -> bool:
        with self._olvasva:
            return len(self._required_update_ids) > 0

    def reset(self) -> None:
        with self._irva:
            self._items.clear()
            self._last_time_missions_requested = _LOCAL_DATE_TIME_MIN

    def clear_keeping_moment(self) -> None:
        with self._irva:
            self._items.clear()

    def __str__(self) -> str:
        return ("<AssignmentLog " + f"last_time_missions_requested={self._last_time_missions_requested},"
                f" required_update_ids={self._required_update_ids}, items={self._items}" + ">")


log = logging.getLogger(__name__)


class Tallies(Outgoing, Watcher, Zarhato):
    def __init__(self, szamlalo_tabla: dict, frissitendo_szamlalok: set, user_id: int):
        self._catalogue: Catalogue = Services.get(Catalogue)
        self._counter_map = szamlalo_tabla
        self._counters_required_to_update = frissitendo_szamlalok
        self._read_write_lock = ReadWriteLock()
        tag("userID", str(user_id))

    @staticmethod
    def create(user_id: int) -> "Tallies":
        tmp_counters = Tallies({}, set(), user_id)
        tmp_counters.seed_counters()
        return tmp_counters

    @property
    def internal_read_only(self):
        return MappingProxyType(self._counter_map)

    def seed_counters(self) -> None:
        with self._irva:
            counter_cards = self._catalogue.all_cards_of_view(CardView.Counter)
            for kartya in counter_cards:
                if kartya.card_guid_of() == 130920111:
                    log.error("Critical: counter init is inside setup_zero_counters_from_cards")
                desc = TallyInfo(kartya.card_guid_of(), 0)
                desc.watch_with(self)
                self._counter_map[kartya.card_guid_of()] = desc

    def restore_counters(self, guid: int, new_value: float) -> None:
        existing = self._counter_map.get(guid)
        if existing is not None:
            existing.set_value(new_value)
        else:
            counter = self._catalogue.card_of(guid, CardView.Counter)
            if counter is None:
                log.info("Counter card is zero, abort injecting! guid: %s new_val: %s", guid, new_value)
                return
            atmeneti = TallyInfo(guid, new_value)
            atmeneti.watch_with(self)
            self._counter_map[atmeneti.guid] = atmeneti

    def bump_tally(self, card_guid: int, novekmeny_osszeg: float) -> None:
        with self._irva:
            if (existing := self._counter_map.get(card_guid)) is not None:
                existing.grow_value(novekmeny_osszeg)

    def to_wire(self, bw) -> None:
        with self._olvasva:
            bw.write_desc_collection(list(self._counters_required_to_update))
            self._counters_required_to_update.clear()

    def on_update(self, arg) -> None:
        self._counters_required_to_update.add(arg)

    @property
    def require_update(self) -> bool:
        return len(self._counters_required_to_update) > 0

    def wake_all(self) -> None:
        with self._irva:
            self._counters_required_to_update.update(self._counter_map.values())

    def __str__(self) -> str:
        with self._olvasva:
            return "<Tallies " + f"counter_map={self._counter_map}" + ">"


class TallyDesk:
    def __init__(self, counters: Tallies, mission_book: AssignmentLog):
        self._counters = counters
        self._mission_book = mission_book

    def counters(self) -> Tallies:
        return self._counters

    @property
    def mission_book(self) -> AssignmentLog:
        return self._mission_book

    def bump_counter(self, tally, star_card_guid: int, mennyivel: float = 1) -> None:
        counter_card_guid = tally.card_guid if isinstance(tally, TallyCardKind) else tally
        self._counters.bump_tally(counter_card_guid, mennyivel)
        self._mission_book.bump_counter_everywhere(counter_card_guid, star_card_guid, mennyivel)

    def set_counter(self, tally_card_guid: int, value: int) -> None:
        self._counters.restore_counters(tally_card_guid, value)

    def wake_all(self) -> None:
        self._counters.wake_all()
        self._mission_book.wake_all()
