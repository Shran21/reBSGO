# github.com/Shran21

from __future__ import annotations

from dataclasses import dataclass

from datetime import datetime, timedelta, timezone
from rebsgo.helpers import json_text
from rebsgo.helpers.locks import ReentrantLock
import logging


@dataclass(slots=True, eq=False)
class KillFeedEntry:
    killer_id: int
    killer_name: str
    killer_list: object

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, KillFeedEntry):
            return False
        return (self.killer_id == other.killer_id and self.killer_name == other.killer_name
                and self.killer_list == other.killer_list)

    def __hash__(self) -> int:
        return hash((self.killer_id, self.killer_name))

    def __repr__(self) -> str:
        return (f'<kill by {self.killer_name} ({self.killer_id}),'
                f' assists {self.killer_list}>')


class Slayer:
    def __init__(self, id_: int, name: str):
        self._id = id_
        self._name = name

    def id(self) -> int:
        return self._id

    def name(self) -> str:
        return self._name

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, Slayer):
            return False
        return self._id == other._id and self._name == other._name

    def __hash__(self) -> int:
        return hash((self._id, self._name))

    def __repr__(self) -> str:
        return f'<slayer {self._name} ({self._id})>'


class Victim:
    def __init__(self, player_id: int, name: str, idopont):
        self._player_id = player_id
        self._name = name
        self._local_date_time = idopont

    @property
    def player_id(self) -> int:
        return self._player_id

    def name(self) -> str:
        return self._name

    @property
    def local_date_time(self):
        return self._local_date_time

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, Victim):
            return False
        return (self._player_id == other._player_id and self._name == other._name
                and self._local_date_time == other._local_date_time)

    def __hash__(self) -> int:
        return hash((self._player_id, self._name, self._local_date_time))

    def __repr__(self) -> str:
        return f'<{self._name} ({self._player_id}) went down at {self._local_date_time}>'


log = logging.getLogger(__name__)


class PvpKillLog:
    def __init__(self):
        killer_map = {}
        lock = ReentrantLock()
        self._killer_map = killer_map
        self._lock = lock
        self._kill_log_lifetime = timedelta(minutes=30)
        self._kill_threshold = 5
        self._attack_map: dict[int, list] = {}
        self._rescue_window = timedelta(seconds=30)

    def note_pvp_kill(self, gyilkos_id: int, gyilkos_neve: str, aldozat_id: int, aldozat_neve: str,
                      kill_moment_utc=None) -> None:
        if kill_moment_utc is None:
            kill_moment_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        with self._lock:
            killer_object = Slayer(gyilkos_id, gyilkos_neve)

            killer_list = self._killer_map.get(killer_object)
            if killer_list is None:
                killer_list = []
            self._cleanup_old_kills(killer_list)
            killer_list.append(Victim(aldozat_id, aldozat_neve, kill_moment_utc))
            self._killer_map[killer_object] = killer_list

            if self._check_kill_threshold(killer_list):
                kill_report_json = json_text.szoveggé(KillFeedEntry(gyilkos_id, gyilkos_neve, killer_list))
                log.warning('suspected kill-boosting with %s', kill_report_json)

    def _check_kill_threshold(self, kills) -> bool:
        kill_counts = {}
        for kill in kills:
            kill_counts[kill.player_id] = kill_counts.get(kill.player_id, 0) + 1
            if kill_counts[kill.player_id] >= self._kill_threshold:
                return True
        return False

    def killed_objects_of_id(self, gyilkos_id: int):
        with self._lock:
            for slayer, kills in self._killer_map.items():
                if slayer.id() == gyilkos_id:
                    self._cleanup_old_kills(kills)
                    return list(kills)
        return []

    def damage_landed(self, sebzes_sor) -> None:
        tamado, celpont = sebzes_sor.from_, sebzes_sor.to
        if not (tamado.is_player() and celpont.is_player()):
            return
        try:
            tamado_id, celpont_id = tamado.pilot_id(), celpont.pilot_id()
        except Exception:
            return
        if tamado_id == celpont_id:
            return
        most = datetime.now(timezone.utc).replace(tzinfo=None)
        with self._lock:
            sor = self._attack_map.setdefault(tamado_id, [])
            self._cleanup_old_attacks(sor)
            sor.append((celpont_id, most))

    def attacked_lately(self, pilota_id: int) -> set:
        with self._lock:
            sor = self._attack_map.get(pilota_id)
            if not sor:
                return set()
            self._cleanup_old_attacks(sor)
            return {celpont for celpont, _ekkor in sor}

    def revenge_kill(self, gyilkos_id: int, aldozat_id: int) -> bool:
        return any(aldozat.player_id == gyilkos_id
                   for aldozat in self.killed_objects_of_id(aldozat_id))

    def _cleanup_old_attacks(self, tamadasok) -> None:
        most = datetime.now(timezone.utc).replace(tzinfo=None)
        tamadasok[:] = [t for t in tamadasok if (most - t[1]) <= self._rescue_window]

    def _cleanup_old_kills(self, kills) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        kills[:] = [kill for kill in kills if (now - kill.local_date_time) <= self._kill_log_lifetime]

    def _format_kills_to_json(self, kills) -> str:
        return str(kills)
