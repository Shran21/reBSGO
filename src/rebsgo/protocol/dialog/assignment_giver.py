# github.com/Shran21
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from rebsgo.services import Services
from rebsgo.pilots.state.tallies import Assignment, AssignmentTally
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.library import Catalogue
from rebsgo.gamedata.assignments import mission_templates

log = logging.getLogger(__name__)


class AssignmentGiver:
    def __init__(self, player, galaxy, dice):
        self._player = player
        self._galaxy = galaxy
        self._dice = dice
        self._catalogue = Services.get(Catalogue)
        self._lock = threading.Lock()

    def refresh_missions(self) -> bool:
        with self._lock:
            mission_book = self._player.tally_desk.mission_book
            now = datetime.now(timezone.utc)
            last_time = mission_book.last_time_missions_requested
            last_time_day_of_year = last_time.timetuple().tm_yday
            current_day_of_year = now.timetuple().tm_yday
            last_year = last_time.year
            now_year = now.year

            already_fetched_today = last_time_day_of_year == current_day_of_year
            log.info("Already fetched today %s last_time_day %s current_day %s",
                     already_fetched_today, last_time_day_of_year, current_day_of_year)
            if already_fetched_today and last_year == now_year:
                return False

            mission_templates = mission_templates(self._player.faction)
            required_mission_lst = [mission_template for mission_template in mission_templates.values()
                                    if mission_book.by_id(mission_template.id()) is None]

            for mission_template in required_mission_lst:
                guid = mission_template.mission_guid
                mission_card = self._catalogue.card_of(guid, CardView.Assignment)
                if mission_card is None:
                    log.warning('no mission card carries guid %s', guid)
                    continue
                is_level_requirements = mission_card.level_between(self._player.skill_book.get())
                if not is_level_requirements:
                    log.info("player does not have level requirements for mission current_lvl: %s",
                             self._player.skill_book.get())
                    continue
                sector_guid = self._get_sector_guid_based_on_id(self._get_sector_id_based_on_template(mission_template))
                mission_countable_map = {}

                for mission_count_entry in mission_template.mission_count_entries:
                    mission_countable = AssignmentTally(mission_count_entry.guid, 0, mission_count_entry.need_count)
                    mission_countable_map[mission_countable.counter_card_guid] = mission_countable

                mission = Assignment(
                    mission_template.id(),
                    guid,
                    sector_guid,
                    mission_countable_map)
                mission_book.add_item(mission)
            mission_book.note_mission_request(now)
            return True

    def _get_sector_guid_based_on_id(self, sector_id: int) -> int:
        if sector_id == 0:
            return 0
        map_card = self._galaxy.map_card
        kezdet = map_card.star(sector_id)
        return kezdet.sector_guid if kezdet is not None else 0

    def _get_sector_id_based_on_template(self, kuldetes_sablon) -> int:
        mission_layout = kuldetes_sablon.mission_layout
        if mission_layout.is_global:
            return 0

        if not mission_layout.use_random_sector or mission_layout.static_sector_id != 0:
            return mission_layout.static_sector_id

        map_card = self._galaxy.map_card
        sector_ids = map_card.stars.keys()

        filtered_blacklist = {sid for sid in sector_ids if not mission_layout.barred(sid)}

        filtered_whitelist = [sid for sid in filtered_blacklist if mission_layout.admitted(sid)]

        return filtered_whitelist[self._dice.whole(len(filtered_whitelist))]
