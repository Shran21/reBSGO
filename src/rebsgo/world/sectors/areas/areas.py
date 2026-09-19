# github.com/Shran21

from __future__ import annotations

from rebsgo.world.sectors.running.coming_and_going import DepartureWatcher
from rebsgo.world.sectors.sector_parts import SectorStep
from rebsgo.vocabulary.world import DepartureCause
import struct
from rebsgo.protocol.zone import TournamentStanding


class SectorAreas(SectorStep, DepartureWatcher):
    def __init__(self, terulet_sablon):
        self._zone_template = terulet_sablon
        self._zone_leaderboard = AreaLeaderboard({}, {})

    def tournament_standings(self):
        return self._zone_leaderboard.tournament_standings()

    @property
    def zone_template(self):
        return self._zone_template

    @property
    def is_zone(self) -> bool:
        return self._zone_template is not None and self._zone_template.sector_guid != 0

    def run(self) -> None:
        if not self.is_zone:
            return

    def on_update(self, arg) -> None:
        if DepartureCause.Death != arg.removal_cause_of():
            return


def _float_compare(f1: float, f2: float) -> int:
    if f1 < f2:
        return -1
    if f1 > f2:
        return 1
    this_bits = struct.unpack("<i", struct.pack("<f", f1))[0]
    another_bits = struct.unpack("<i", struct.pack("<f", f2))[0]
    if this_bits == another_bits:
        return 0
    return -1 if this_bits < another_bits else 1


class AreaLeaderboard:
    def __init__(self, player_to_nemesis_kills, kill_death_cnt_map):
        self._player_to_nemesis_kills = player_to_nemesis_kills
        self._kill_death_cnt_map = kill_death_cnt_map

    def tournament_standings(self):
        tournament_standings = []
        for player_id, darab in self._kill_death_cnt_map.items():
            tournament_standings.append(
                TournamentStanding(
                    player_id,
                    0,
                    darab.score,
                    darab.kill_count(),
                    darab.death_count))
        return tournament_standings

    def leader_player_id(self):
        best_key = None
        best_cnt = None
        elso = True
        for kulcs, darab in self._kill_death_cnt_map.items():
            if elso:
                best_key, best_cnt = kulcs, darab
                elso = False
            elif not (_float_compare(best_cnt.score, darab.score) >= 0):
                best_key, best_cnt = kulcs, darab
        return best_key

    def add_nemesis(self, player_id: int, nemezis_id: int) -> None:
        existing_set = self._player_to_nemesis_kills.get(player_id)
        if existing_set is None:
            existing_set = set()
        existing_set.add(nemezis_id)
        self._player_to_nemesis_kills[player_id] = existing_set

    def nemesis_of(self, player_id: int, gyanus_nemezis_id: int) -> bool:
        nemesis_set = self._player_to_nemesis_kills.get(player_id)
        if nemesis_set is None:
            return False
        return gyanus_nemezis_id in nemesis_set
