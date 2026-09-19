# github.com/Shran21
from __future__ import annotations

from contextlib import suppress

import datetime
import logging
import threading
import time

from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.protocol_book_replies import game_replies
from rebsgo.vocabulary.pilot import FactionGroup
from rebsgo.vocabulary.world import PlaceKind, DepartureCause
from rebsgo.schedule import TimedCall
from rebsgo.gamedata.reading import ObjectStat
from rebsgo.helpers.locks import ReentrantLock

log = logging.getLogger(__name__)


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class _DeathWatcher:
    def __init__(self, match: "ArenaMatch"):
        self._match = match

    def on_update(self, tavozas_leiras) -> None:
        try:
            self._match.on_object_left(tavozas_leiras)
        except Exception:
            log.exception("arena death-watch failed")


class ArenaMatch:
    def __init__(self, config: dict, sector_book, writer, pilot_roster):
        self._cfg = config
        self._sector_book = sector_book
        self._writer = writer
        self._users = pilot_roster
        self._lock = ReentrantLock()
        self._state = "starting"
        self._players: dict[int, object] = {}
        self._groups: dict[int, object] = {}
        self._origins: dict[int, tuple] = {}
        self._kills: dict[int, int] = {}
        self._arena_sector = None
        self._time_begin = None
        self._time_end = None
        self._watch_registered = False


    def start(self, pilotak) -> bool:
        sector = self._ensure_arena_sector()
        if sector is None:
            return False
        self._arena_sector = sector

        from rebsgo.vocabulary.pilot import Faction
        factions = [u.pilot_of().faction for u in pilotak]
        if len(pilotak) == 2 and factions[0] != factions[1]:
            assigned = [FactionGroup.Group0 if f == Faction.Colonial else FactionGroup.Group1
                        for f in factions]
        else:
            split = [FactionGroup.Group0, FactionGroup.Group1]
            assigned = [split[idx % 2] for idx in range(len(pilotak))]
        for idx, user in enumerate(pilotak):
            player = user.pilot_of()
            pid = player.user_id_of()
            self._players[pid] = user
            self._groups[pid] = assigned[idx]
            self._kills[pid] = 0
            loc = player.location
            self._origins[pid] = (loc.game_location, loc.sector_id, loc.sector_guid)

        for pid, user in self._players.items():
            self._send_into_arena(user, self._groups[pid])

        threading.Thread(target=self._await_spawn_then_init, name="ArenaMatchInit", daemon=True).start()
        return True

    @staticmethod
    def _schedule_delayed(seconds: float, callback, task_name: str) -> TimedCall:
        def _run():
            try:
                callback()
            except Exception:
                log.exception("arena: delayed task %s failed", task_name)

        future = TimedCall(seconds, _run)
        future.start()
        return future

    def _ensure_arena_sector(self):
        arena_id = self._cfg["arenaSectorId"]
        sector = self._sector_book.sector_by_id(arena_id)
        if sector is not None:
            return sector
        try:
            factory = self._sector_book.sector_source
            sector = factory.create_arena_sector(arena_id, self._cfg["arenaSceneBaseSectorId"])
            self._sector_book.register_sector(sector)
            log.info("arena: created dedicated arena sector %s (scene base %s)",
                     arena_id, self._cfg["arenaSceneBaseSectorId"])
            return sector
        except Exception:
            log.exception("arena: failed to create dedicated arena sector, aborting")
            return None

    def _send_into_arena(self, user, group) -> None:
        try:
            player = user.pilot_of()
            old_sector = self._sector_book.sector_by_id(player.sector_id)
            if old_sector is not None and old_sector.id != self._arena_sector.id:
                old_ship = old_sector.ctx.users().ship_of_pilot(player.user_id_of())
                if old_ship is not None and not old_ship.is_removed():
                    old_sector.departures_desk.note_removal_cause(
                        old_ship, DepartureCause.JumpOut)
            player._arena_match = self
            player._arena_faction_group = group
            group_flag = 1 if group == FactionGroup.Group1 else 0
            player.location.set_arena_location(
                self._arena_sector.id, self._arena_sector.sector_guid, group_flag)
            user.protocol_of(ProtocolID.Scene).push_scene_change()
        except Exception:
            log.exception("arena: failed sending player into arena")

    def _await_spawn_then_init(self) -> None:
        deadline = time.monotonic() + self._cfg["spawnWaitSeconds"]
        while time.monotonic() < deadline:
            time.sleep(0.5)
            if all(self._ship_of(pid) is not None for pid in self._players):
                break

        with self._lock:
            if self._state != "starting":
                return
            ships = {pid: self._ship_of(pid) for pid in self._players}
            if any(ship is None for ship in ships.values()):
                log.error("arena: not all duelists spawned within %ss, aborting match",
                          self._cfg["spawnWaitSeconds"])
                self._end_match(None)
                return

            self._register_watch()
            self._time_begin = _utc_now()
            self._time_end = self._time_begin + datetime.timedelta(seconds=self._cfg["duelDurationSeconds"])
            self._state = "running"

            pids = list(self._players)
            for pid in pids:
                opponent_pid = next(other for other in pids if other != pid)
                own_ship = ships[pid]
                opponent_ship = ships[opponent_pid]
                self._send(pid, self._writer.arena_init(
                    self._time_begin, self._time_end,
                    opponent_ship.id_in_space(), own_ship.id_in_space()))

            for pid in pids:
                self._send(pid, self._writer.arena_closed)
            log.info("arena: duel started in sector %s, players=%s, ends %s",
                     self._arena_sector.id, pids, self._time_end)

        self._broadcast_faction_groups()
        self._restore_ships()
        self._schedule_delayed(12.0, self._broadcast_faction_groups, "broadcast_faction_groups")
        self._schedule_delayed(12.0, self._restore_ships, "restore_ships")
        self._schedule_delayed(self._cfg["duelDurationSeconds"], self._safe_end_by_score, "end_by_score")

    def _restore_ships(self) -> None:
        try:
            with self._lock:
                if self._state != "running":
                    return
                for pid in self._players:
                    ship = self._ship_of(pid)
                    if ship is None:
                        continue
                    with suppress(Exception):
                        allapot = ship.world_state_of()
                        if allapot is not None and allapot.is_docking:
                            allapot.mark_docking(False)
                    mutatok = ship.space_subscribe_info()
                    max_hp = mutatok.stat(ObjectStat.MaxHullPoints)
                    max_pp = mutatok.stat(ObjectStat.MaxPowerPoints)
                    if max_hp:
                        mutatok.set_hull(max_hp)
                    if max_pp:
                        mutatok.set_power(max_pp)
        except Exception:
            log.exception("arena: restoring ship power failed")

    def _broadcast_faction_groups(self) -> None:
        try:
            with self._lock:
                if self._state != "running":
                    return
                pids = list(self._players)
                game_wo = game_replies()
                for ship_pid in pids:
                    ship = self._ship_of(ship_pid)
                    if ship is None:
                        continue
                    csoport = self._groups[ship_pid]
                    for recipient_pid in pids:
                        self._send(recipient_pid,
                                   game_wo.update_faction_group(ship.id_in_space(), csoport))
        except Exception:
            log.exception("arena: broadcast faction groups failed")


    def on_object_left(self, desc) -> None:
        with self._lock:
            if self._state != "running" or desc.removal_cause_of() != DepartureCause.Death:
                return
            removed = desc.departed_object
            if not removed.is_player():
                return
            dead_pid = removed.pilot_id()
            if dead_pid not in self._players:
                return

            survivors = [pid for pid in self._players if pid != dead_pid]
            winner_pid = survivors[0] if survivors else None
            if winner_pid is not None:
                self._kills[winner_pid] = self._kills.get(winner_pid, 0) + 1
            self._end_match(winner_pid)


    def _safe_end_by_score(self) -> None:
        try:
            with self._lock:
                if self._state != "running":
                    return
                pids = list(self._players)
                elso, second = pids[0], pids[1]
                if self._kills[elso] > self._kills[second]:
                    winner = elso
                elif self._kills[second] > self._kills[elso]:
                    winner = second
                else:
                    winner = None
                self._end_match(winner)
        except Exception:
            log.exception("arena: end-by-score failed")

    def on_player_disconnect(self, pid: int) -> None:
        with self._lock:
            if self._state == "ended" or pid not in self._players:
                return
            others = [other for other in self._players if other != pid]
            self._end_match(others[0] if others else None)

    def _end_match(self, winner_pid) -> None:
        with self._lock:
            if self._state == "ended":
                return
            self._state = "ended"
            for pid in list(self._players):
                try:
                    if pid == winner_pid:
                        self._send(pid, self._writer.arena_won(0, 0, 0, 0))
                    elif winner_pid is not None:
                        self._send(pid, self._writer.arena_lost(0, 0, 0))
                except Exception:
                    log.exception("arena: result send failed for %s", pid)
            log.info("arena: duel ended, winner=%s, kills=%s", winner_pid, self._kills)
            self._arena_pontok(winner_pid)
        self._schedule_delayed(self._cfg.get("returnDelaySeconds", 4), self._return_all, "return_all")

    def _arena_pontok(self, winner_pid) -> None:
        try:
            from rebsgo.gamedata.from_json.template_readers import ArenaPointsReader
            from rebsgo.gamedata.cards.misc_cards import TallyCardKind

            beallitas = ArenaPointsReader().fetch()
            if not beallitas:
                return
            kulcs = "arena_1x1" if len(self._players) <= 2 else "arena_3x3"
            szamlalok = beallitas.get(kulcs) or []
            if not szamlalok:
                return

            for pid, user in list(self._players.items()):
                pont = beallitas["winPoints"] if pid == winner_pid else beallitas["lossPoints"]
                if pont <= 0:
                    continue
                oszlop = self._hajo_oszlopa(pid, beallitas["role_columns"])
                guid = szamlalok[min(max(oszlop, 1), len(szamlalok)) - 1]
                asztal = user.pilot_of().tally_desk
                asztal.bump_counter(guid, 0, pont)
                asztal.bump_counter(TallyCardKind.arena, 0, pont)
        except Exception:
            log.exception("arena: the ladder would not take this match")

    def _hajo_oszlopa(self, pid: int, szerep_oszlopok: dict) -> int:
        try:
            hajo = self._players[pid].pilot_of().hangar_of().active_ship()
            szerep = hajo.ship_card_of().ship_role_deprecated
            return szerep_oszlopok.get(getattr(szerep, "name", str(szerep)), 1)
        except Exception:
            return 1

    def _return_all(self) -> None:
        for pid in list(self._players):
            with suppress(Exception):
                self._send(pid, self._writer.arena_closed)
            self._return_player(pid)

    def _return_player(self, pid: int) -> None:
        try:
            user = self._players.get(pid)
            if user is None:
                return
            player = user.pilot_of()
            player._arena_match = None
            player._arena_faction_group = None

            eredet = self._origins.get(pid)
            origin_sector_id = eredet[1] if eredet is not None else player.sector_id
            origin_guid = eredet[2] if eredet is not None else 0

            ship = self._ship_of(pid)
            if ship is not None and not ship.is_removed():
                game_protocol = user.protocol_of(ProtocolID.Game)
                game_protocol.jump_now(self._arena_sector.jump_book, origin_sector_id, 1, False)
            else:
                player.location.set_location(PlaceKind.Room, origin_sector_id, origin_guid)
                user.protocol_of(ProtocolID.Game).dock_now(True)
        except Exception:
            log.exception("arena: returning player %s home failed", pid)


    def _register_watch(self) -> None:
        if self._watch_registered:
            return
        self._arena_sector.departures_desk.watch_with(_DeathWatcher(self))
        self._watch_registered = True

    def _ship_of(self, pid: int):
        try:
            return self._arena_sector.ctx.users().ship_of_pilot(pid)
        except Exception:
            return None

    def _send(self, pid: int, bw) -> None:
        if (user := self._players.get(pid)) is not None:
            try:
                user.send(bw)
            except Exception:
                log.exception("arena: send to %s failed", pid)
