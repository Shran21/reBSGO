# github.com/Shran21
from __future__ import annotations

import logging

from rebsgo.store.assignments.assignment_row import AssignmentRow
from rebsgo.store.sqlite_util import format_local_date_time, read_moment
from rebsgo.pilots.state.tallies import Assignment, AssignmentTally
from rebsgo.gamedata.cards.card_view import CardView

log = logging.getLogger(__name__)


class SqliteAssignments:
    def __init__(self, data_source, catalogue):
        self._data_source = data_source
        self._catalogue = catalogue

    def store_missions(self, player, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            if owns_connection:
                conn.execute("BEGIN")
            self._write_mission_book(player, conn=conn)
            self._write_missions(player, conn=conn)
            if owns_connection:
                conn.commit()
        except Exception:
            if owns_connection:
                conn.rollback()
            log.exception("the assignments would not save")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()

    def _write_mission_book(self, player, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            last_time_missions_requested = player.tally_desk.mission_book.last_time_missions_requested
            last_time_str = format_local_date_time(last_time_missions_requested)
            conn.execute("REPLACE INTO mission_logs(player_id, last_time_missions_fetch_date) VALUES (?, ?)",
                         (player.user_id_of(), last_time_str))
            if owns_connection:
                conn.commit()
        except Exception:
            log.exception("the assignment log would not save")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()

    def _write_missions(self, player, conn=None) -> None:
        mission_book = player.tally_desk.mission_book
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            if owns_connection:
                conn.execute("BEGIN")
            conn.execute("DELETE FROM pilot_missions WHERE player_id=?", (player.user_id_of(),))
            sorok = []
            missions = mission_book.find_all(lambda mission: True)
            for mission in missions:
                for mission_countable in mission.mission_countables.values():
                    sorok.append((player.user_id_of(), mission.server_id, mission.mission_card_guid,
                                 mission.associated_sector_card_guid, mission_countable.counter_card_guid,
                                 mission_countable.current_count, mission_countable.need_count))
            conn.executemany(
                "REPLACE INTO pilot_missions(player_id, mission_id, mission_guid, associated_sector_guid, "
                "counter_guid, current_count, need_count) VALUES (?, ?, ?, ?, ?, ?, ?)", sorok)
            if owns_connection:
                conn.commit()
        except Exception:
            if owns_connection:
                conn.rollback()
            log.exception("the assignment rows would not save")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()

    def stored_missions(self, player, conn=None) -> None:
        mission_book = player.tally_desk.mission_book
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            query_result = conn.execute("SELECT * FROM mission_logs WHERE player_id=?",
                                        (player.user_id_of(),)).fetchone()
            if query_result is None:
                return

            raw_last_time_mission_fetched = query_result["last_time_missions_fetch_date"]
            last_time_mission_fetched = read_moment(raw_last_time_mission_fetched)
            mission_book.note_mission_request(last_time_mission_fetched)

            mission_fetch_results = self._fetch_mission_info(player.user_id_of(), conn=conn)
            result_grouped = {}
            for r in mission_fetch_results:
                result_grouped.setdefault(r.server_id, []).append(r)

            for entries_for_mission in result_grouped.values():
                mission_countables = {}
                first_entry = entries_for_mission[0]
                mission_card = self._catalogue.card_of(first_entry.mission_guid, CardView.Assignment)
                if mission_card is None:
                    log.warning('no mission stored under guid {}'.format(first_entry.mission_guid))
                    continue
                for mission_fetch_result in entries_for_mission:
                    mission_countables[mission_fetch_result.counter_card_guid] = AssignmentTally(
                        mission_fetch_result.counter_card_guid,
                        mission_fetch_result.current_count,
                        mission_fetch_result.need_count)

                mission = Assignment(
                    first_entry.server_id,
                    first_entry.mission_guid,
                    first_entry.associated_sector_card_guid,
                    mission_countables)
                mission_book.inject(mission)
        except Exception as e:
            log.error("SQL Error inside fetch_mission_book", exc_info=e)
        finally:
            if owns_connection:
                conn.close()

    def _fetch_mission_info(self, player_id: int, conn=None):
        mission_fetch_results = []
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            cursor = conn.execute("SELECT * FROM pilot_missions WHERE player_id=?", (player_id,))
            for sor in cursor:
                mission_id = sor["mission_id"]
                mission_guid = sor["mission_guid"]
                associated_sector_guid = sor["associated_sector_guid"]
                cleaned_associated_sector_guid = self._clean_mission_sector_guid(associated_sector_guid)
                counter_guid = sor["counter_guid"]
                current_count = sor["current_count"]
                need_count = sor["need_count"]
                mission_fetch_results.append(AssignmentRow(
                    mission_id, mission_guid, cleaned_associated_sector_guid,
                    counter_guid, current_count, need_count))
        finally:
            if owns_connection:
                conn.close()
        return mission_fetch_results

    def _clean_mission_sector_guid(self, home_star_guid: int) -> int:
        if home_star_guid == 0:
            return 0
        sector_guid = self._catalogue.card_of(home_star_guid, CardView.Sector)
        if sector_guid is None:
            return 0
        return home_star_guid
