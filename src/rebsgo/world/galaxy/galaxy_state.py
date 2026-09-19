# github.com/Shran21
from __future__ import annotations

import datetime as dt
import logging

from rebsgo.world.galaxy.map_changes import ConquestPlaceNotice, ConquestPriceNotice, GalaxyRcpNotice, SectorAssignmentNotice, SectorBeaconNotice, SectorMinerNotice, SectorOutpostPointsNotice, SectorOutpostPhaseNotice, SectorTransponderNotice, SectorSeatNotice, SectorPvpKillNotice
from rebsgo.world.carriers.carrier_mode import get_carrier_mode_config, is_carrier_space_object
from rebsgo.world.carriers.carrier_transponder_target import carrier_transponder_space_id
from rebsgo.protocol.starmap import StarmapReplies
from rebsgo.vocabulary.pilot import Faction
from rebsgo.vocabulary.world import ObjectKind
from rebsgo.geometry.maths.maths import Maths
from rebsgo.helpers.carrier_transponder_diagnostics import carrier_transponder_debug_enabled
from rebsgo.helpers.floats import f32
from rebsgo.helpers.locks import ReentrantLock

log = logging.getLogger(__name__)


def _format_transponder_desc(desc) -> str:
    return (
        "player={player},party={party},space={space},expires={expires}".format(
            player=getattr(desc, "_player_id", None),
            party=getattr(desc, "_party_id", None),
            space=getattr(desc, "_space_id", None),
            expires=getattr(desc, "_expires", None)))


def _format_transponder_descs(descs) -> str:
    return "[" + ";".join(_format_transponder_desc(desc) for desc in descs) + "]"


def _carrier_transponder_update_summary(updates) -> tuple[int, str]:
    if updates is None:
        return 0, "-"
    bojasok = [(u, getattr(u, "_jump_target_transponder_descs", None) or [])
               for u in updates if isinstance(u, SectorTransponderNotice)]
    bojasok = [(u, d) for u, d in bojasok if d]
    osszeg = sum(len(d) for _u, d in bojasok)
    sectors = [f'{getattr(u, "_sector_id", "?")}:{len(d)}' for u, d in bojasok]
    return osszeg, ",".join(sectors) if sectors else "-"


class Galaxy:
    def __init__(self, catalogue, sector_book, galaxis_szorzo):
        self._galaxy_map_card = catalogue.map_card
        self._galaxy_subscribers = {}
        self._sector_book = sector_book
        self._update_lst_colonial = None
        self._update_lst_cylon = None
        self._galaxy_bonus = galaxis_szorzo
        self._lock = ReentrantLock()
        self._universe_writer = StarmapReplies()
        self._transponder_log_counts: dict = {}
        empty_capital_expire = dt.datetime.now(dt.timezone.utc)
        self._capital_ship_locations = {
            Faction.Colonial: (-1, empty_capital_expire),
            Faction.Cylon: (-1, empty_capital_expire),
        }

        self._logged_missing_galaxy_card = False
        self._logged_missing_sectors = False
        self._logged_run_failure = False
        self._last_run_failure_key = None

        self._ever_event_sectors = set()

    @property
    def map_card(self):
        return self._galaxy_map_card

    def watch_with(self, galaxis_figyelo) -> None:
        with self._lock:
            self._galaxy_subscribers[galaxis_figyelo.id] = galaxis_figyelo
            update_lst = self._update_lst_colonial if galaxis_figyelo.faction == Faction.Colonial \
                else self._update_lst_cylon
            if carrier_transponder_debug_enabled():
                transponder_total, transponder_sectors = _carrier_transponder_update_summary(update_lst)
                log.info(
                    "CARRIER_TRANSPONDER_DIAG galaxy_add_subscriber subscriber=%s faction=%s "
                    "updates=%s transponder_descs=%s transponder_sectors=%s",
                    galaxis_figyelo.id, galaxis_figyelo.faction,
                    0 if update_lst is None else len(update_lst),
                    transponder_total, transponder_sectors)
            bw = self._universe_writer.updates(update_lst)
            galaxis_figyelo.map_changed(bw)

    def remove_subscriber(self, galaxis_figyelo) -> None:
        with self._lock:
            self._galaxy_subscribers.pop(galaxis_figyelo.id, None)

    def update_capital_ship_location(self, faction, sector_id: int, expire: dt.datetime) -> None:
        with self._lock:
            self._capital_ship_locations[faction] = (sector_id, expire)
            bw = self._universe_writer.update(ConquestPlaceNotice(faction, sector_id, expire))
            for subscriber in list(self._galaxy_subscribers.values()):
                subscriber.map_changed(bw)

    def capital_ship_sector(self, faction) -> int:
        with self._lock:
            return self._capital_ship_locations[faction][0]

    def _get_capital_ship_updates(self):
        now = dt.datetime.now(dt.timezone.utc)
        updates = []
        for frakcio in (Faction.Colonial, Faction.Cylon):
            sector_id, expire = self._capital_ship_locations[frakcio]
            if sector_id != -1 and expire <= now:
                sector_id = -1
                expire = now
                self._capital_ship_locations[frakcio] = (sector_id, expire)
            updates.append(ConquestPlaceNotice(frakcio, sector_id, expire))
        return updates

    def _full_map_refresh(self):
        forrasok = (
            self._get_capital_ship_updates,
            lambda: self._outpost_states_for(Faction.Colonial),
            lambda: self._outpost_states_for(Faction.Cylon),
            lambda: self._get_beacon_states(Faction.Colonial),
            lambda: self._get_beacon_states(Faction.Cylon),
            self._get_mining_ships_update,
            lambda: self._get_rcp_update(100, 1),
            self.kill_count,
            self._dynamic_mission_refresh,
        )
        return [frissites for forras in forrasok for frissites in forras()]

    def _visible_stars(self):
        from rebsgo.gamedata.from_json.template_readers import sector_policy
        stars = list(self._galaxy_map_card.stars.values())
        hidden = sector_policy().disabled
        if not hidden:
            return stars
        return [csillag for csillag in stars if csillag.id not in hidden]

    def _dynamic_mission_refresh(self):
        from rebsgo.world.sectors.clockwork import SectorEventTimer
        galaxy_map_updates = []
        if self._galaxy_map_card is None or self._galaxy_map_card.stars is None:
            return galaxy_map_updates
        mostani = set()
        for csillag in self._visible_stars():
            sector = self._sector_book.sector_by_id(csillag.id)
            if sector is None:
                continue
            try:
                ora = sector.timer_updater.timer_of_type(SectorEventTimer)
            except Exception:
                ora = None
            if ora is not None and ora.is_shown:
                mostani.add(csillag.id)
        self._ever_event_sectors |= mostani
        for sector_id in self._ever_event_sectors:
            darab = 1 if sector_id in mostani else 0
            galaxy_map_updates.append(SectorAssignmentNotice(Faction.Neutral, sector_id, darab))
        return galaxy_map_updates

    def _get_rcp_update(self, op_rcp: float, mining_rcp: float):
        galaxy_map_updates = []

        rcp_colo = 0.0
        rcp_cylo = 0.0

        for csillag in self._visible_stars():
            sector = self._sector_book.sector_by_id(csillag.id)
            if sector is None:
                continue

            mining_ships = sector.ctx.space_objects().space_objects_of_entity_type(ObjectKind.MiningShip)
            size_total_mining_ships = len(mining_ships)
            colonial_mining_ships = sum(1 for so in mining_ships if so.faction == Faction.Colonial)
            cylon_mining_ships = size_total_mining_ships - colonial_mining_ships

            rcp_colo = f32(rcp_colo + f32(mining_rcp * colonial_mining_ships))
            rcp_cylo = f32(rcp_cylo + f32(mining_rcp * cylon_mining_ships))

            colo_op_state = sector.colonial_op_state
            cylo_op_state = sector.cylon_op_state
            delta_colo = colo_op_state.delta()
            delta_cylo = cylo_op_state.delta()

            rcp_colo = f32(rcp_colo + (op_rcp if delta_colo == 1 else 0))
            rcp_cylo = f32(rcp_cylo + (op_rcp if delta_cylo == 1 else 0))

        rcp_colonial = GalaxyRcpNotice(Faction.Colonial, rcp_colo)
        rcp_cylon = GalaxyRcpNotice(Faction.Cylon, rcp_cylo)

        galaxy_map_updates.append(rcp_colonial)
        galaxy_map_updates.append(rcp_cylon)

        self.refresh_sector_bonus(rcp_colo, rcp_cylo)

        return galaxy_map_updates

    def kill_count(self):
        kill_updates = []
        for csillag in self._visible_stars():
            sector = self._sector_book.sector_by_id(csillag.id)
            if sector is None:
                continue
            colonial_killed_counter = sector.departures_desk.kill_counter_faction(Faction.Colonial)
            cylon_killed_counter = sector.departures_desk.kill_counter_faction(Faction.Cylon)
            colo_killed_counter_update = SectorPvpKillNotice(
                colonial_killed_counter.faction,
                sector.id,
                colonial_killed_counter.count())
            cylon_killed_counter_update = SectorPvpKillNotice(
                cylon_killed_counter.faction,
                sector.id,
                cylon_killed_counter.count())

            kill_updates.append(colo_killed_counter_update)
            kill_updates.append(cylon_killed_counter_update)

        return kill_updates

    def refresh_sector_bonus(self, colonial_hanyad: float, cylon_hanyad: float) -> None:
        mining_bonus_colo = self._mining_bonus_for(colonial_hanyad)
        mining_bonus_cylo = self._mining_bonus_for(cylon_hanyad)

        self._galaxy_bonus.set_mining_bonus(Faction.Colonial, mining_bonus_colo)
        self._galaxy_bonus.set_mining_bonus(Faction.Cylon, mining_bonus_cylo)

        self._galaxy_bonus.set_op_bonus(Faction.Colonial, self._op_handicap_for(colonial_hanyad, cylon_hanyad, True))
        self._galaxy_bonus.set_op_bonus(Faction.Cylon, self._op_handicap_for(colonial_hanyad, cylon_hanyad, False))

    def _op_handicap_for(self, colonial_resz: float, cylon_resz: float, colonial_e: bool):
        sajat, masik = (colonial_resz, cylon_resz) if colonial_e else (cylon_resz, colonial_resz)
        eltolodas = f32(sajat - masik)
        tavolsag = Maths.abs(eltolodas)
        fokozatok = self._galaxy_map_card.sector_scaling_multiplier
        szorzo = next((fokozatok[kuszob] for kuszob in sorted(fokozatok, reverse=True)
                       if tavolsag >= float(kuszob)), 0)
        szorzo *= int(self._galaxy_map_card.base_scaling_multiplier)
        return -szorzo if eltolodas > 0 else szorzo

    def _mining_bonus_for(self, rcp: float) -> float:
        tiers = self._galaxy_map_card.tiers
        if rcp < tiers[0]:
            return 0.0
        fok = next((i for i in range(1, len(tiers)) if tiers[i - 1] <= rcp < tiers[i]), None)
        if fok is not None:
            return 5.0 * fok / 100.0
        return (5.0 * len(tiers)) * 0.01

    def _map_updates_for(self, faction):
        galaxy_map_updates = []

        galaxy_map_updates.extend(self._conquest_map_updates(faction))
        galaxy_map_updates.extend(self._outpost_points_for(faction))
        galaxy_map_updates.extend(self._get_carrier_transponder_states(faction))

        for csillag in self._visible_stars():
            sector = self._sector_book.sector_by_id(csillag.id)
            if sector is None:
                continue
            slot_ud = SectorSeatNotice(faction, sector.id, sector.sector_slot_data)
            galaxy_map_updates.append(slot_ud)

        return galaxy_map_updates

    def _get_mining_ships_update(self):
        galaxy_map_updates = []

        for csillag in self._visible_stars():
            sector = self._sector_book.sector_by_id(csillag.id)
            if sector is None:
                continue
            mining_ships = sector.ctx.space_objects().space_objects_of_entity_type(ObjectKind.MiningShip)
            colo_size = sum(1 for x in mining_ships if x.faction == Faction.Colonial)
            cylo_size = len(mining_ships) - colo_size

            galaxy_map_updates.append(SectorMinerNotice(Faction.Colonial, csillag.id, colo_size))
            galaxy_map_updates.append(SectorMinerNotice(Faction.Cylon, csillag.id, cylo_size))

        return galaxy_map_updates

    def _outpost_states_for(self, faction):
        galaxy_map_updates = []

        for csillag in self._visible_stars():
            sector = self._sector_book.sector_by_id(csillag.id)
            if sector is None:
                log.warning("get_outpost_states: star %s has no sector, skipping", csillag.id)
                continue
            op_state = sector.colonial_op_state if faction == Faction.Colonial else sector.cylon_op_state
            galaxy_map_updates.append(SectorOutpostPhaseNotice(faction, sector.id, op_state.delta()))

        return galaxy_map_updates

    def _get_beacon_states(self, faction):
        galaxy_map_updates = []

        for csillag in self._visible_stars():
            if not self._star_allows_beacon(csillag, faction):
                continue
            allapot = 0.0
            if (sector := self._sector_book.sector_by_id(csillag.id)) is not None:
                beacons = sector.ctx.space_objects().space_objects_of_entity_type(
                    ObjectKind.JumpBeacon)
                if any(obj.faction == faction and not obj.is_removed() for obj in beacons):
                    allapot = 1.0
            galaxy_map_updates.append(SectorBeaconNotice(faction, csillag.id, allapot))

        return galaxy_map_updates

    def _get_carrier_transponder_states(self, faction):
        galaxy_map_updates = []
        party_only = get_carrier_mode_config().transponder_party_only()
        debug_enabled = carrier_transponder_debug_enabled()

        for csillag in self._visible_stars():
            sector = self._sector_book.sector_by_id(csillag.id)
            if sector is None:
                continue
            ctx = sector.ctx
            descs = []
            for obj in ctx.space_objects().space_objects_of_entity_type(ObjectKind.Pilot):
                if not is_carrier_space_object(obj):
                    continue
                is_removed = obj.is_removed()
                obj_faction = obj.faction
                is_fortified = obj.world_state_of().is_fortified
                if debug_enabled:
                    log.info(
                        "CARRIER_TRANSPONDER_DIAG carrier_candidate requested_faction=%s sector=%s "
                        "carrier_player=%s carrier_object=%s carrier_faction=%s removed=%s fortified=%s",
                        faction, csillag.id, obj.pilot_id(), obj.id_in_space(), obj_faction,
                        is_removed, is_fortified)
                if is_removed or obj_faction != faction or not is_fortified:
                    continue
                party_id = 0
                if party_only:
                    user = ctx.users().user(obj.pilot_id())
                    party = None if user is None else user.pilot_of().party()
                    if party is None:
                        if debug_enabled:
                            log.info(
                                "CARRIER_TRANSPONDER_DIAG carrier_skip_no_party requested_faction=%s "
                                "sector=%s carrier_player=%s carrier_object=%s",
                                faction, csillag.id, obj.pilot_id(), obj.id_in_space())
                        continue
                    party_id = party.party_id()
                try:
                    transponder_space_id = carrier_transponder_space_id(obj.pilot_id())
                except ValueError:
                    log.warning(
                        "Skipping carrier transponder with unsupported player id: sector=%s player=%s object=%s",
                        csillag.id, obj.pilot_id(), obj.id_in_space())
                    continue
                descs.append(SectorTransponderNotice.TransponderInfo(
                    obj.pilot_id(), party_id, transponder_space_id, 0))
            galaxy_map_updates.append(
                SectorTransponderNotice(faction, csillag.id, descs))
            if debug_enabled and len(descs) > 0:
                log.info(
                    "CARRIER_TRANSPONDER_DIAG carrier_publish faction=%s sector=%s party_only=%s descs=%s",
                    faction, csillag.id, party_only, _format_transponder_descs(descs))
            kulcs = (faction, csillag.id)
            if len(descs) != self._transponder_log_counts.get(kulcs, 0):
                self._transponder_log_counts[kulcs] = len(descs)
                log.info("Carrier transponders for %s in sector %s: %d",
                         faction, csillag.id, len(descs))
        return galaxy_map_updates

    @staticmethod
    def _star_allows_beacon(star, faction) -> bool:
        if faction == Faction.Colonial:
            return bool(star.can_colonial_jump_beacon)
        if faction == Faction.Cylon:
            return bool(star.can_cylon_jump_beacon)
        return False

    def _outpost_points_for(self, faction):
        galaxy_map_updates = []

        for csillag in self._visible_stars():
            sector = self._sector_book.sector_by_id(csillag.id)
            if sector is None:
                log.warning("get_outpost_points: star %s has no sector, skipping", csillag.id)
                continue
            op_state = sector.colonial_op_state if faction == Faction.Colonial else sector.cylon_op_state
            galaxy_map_updates.append(SectorOutpostPointsNotice(faction, sector.id, op_state.op_points))

        return galaxy_map_updates

    def _conquest_map_updates(self, faction):
        galaxy_map_updates = []

        if faction == Faction.Colonial:
            conquest_price = ConquestPriceNotice(Faction.Colonial, 9999)
            galaxy_map_updates.append(conquest_price)
        else:
            conquest_price = ConquestPriceNotice(Faction.Cylon, 9999)
            galaxy_map_updates.append(conquest_price)
        return galaxy_map_updates

    def run(self) -> None:
        try:
            if (self._galaxy_map_card is None or self._galaxy_map_card.stars is None
                or len(self._galaxy_map_card.stars) == 0):
                if not self._logged_missing_galaxy_card:
                    log.warning('galaxy refresh skipped - map card absent or starless')
                    self._logged_missing_galaxy_card = True
                return

            if len(self._sector_book.sectors()) == 0:
                if not self._logged_missing_sectors:
                    log.warning('galaxy refresh skipped - sector registry still empty')
                    self._logged_missing_sectors = True
                return

            self._logged_missing_galaxy_card = False
            self._logged_missing_sectors = False

            with self._lock:
                try:
                    all_updates = self._full_map_refresh()

                    self._update_lst_colonial = self._map_updates_for(Faction.Colonial)
                    self._update_lst_cylon = self._map_updates_for(Faction.Cylon)

                    self._update_lst_colonial.extend(all_updates)
                    self._update_lst_cylon.extend(all_updates)

                    bw_colonial = self._universe_writer.updates(self._update_lst_colonial)
                    bw_cylon = self._universe_writer.updates(self._update_lst_cylon)

                    for galaxy_subscriber in list(self._galaxy_subscribers.values()):
                        subscriber_faction = galaxy_subscriber.faction
                        subscriber_updates = self._update_lst_colonial if subscriber_faction == Faction.Colonial \
                            else self._update_lst_cylon
                        if carrier_transponder_debug_enabled():
                            transponder_total, transponder_sectors = _carrier_transponder_update_summary(
                                subscriber_updates)
                            log.info(
                                "CARRIER_TRANSPONDER_DIAG galaxy_send subscriber=%s faction=%s updates=%s "
                                "transponder_descs=%s transponder_sectors=%s",
                                galaxy_subscriber.id, subscriber_faction, len(subscriber_updates),
                                transponder_total, transponder_sectors)
                        bw = bw_colonial if subscriber_faction == Faction.Colonial else bw_cylon
                        galaxy_subscriber.map_changed(bw)

                    self._logged_run_failure = False
                    self._last_run_failure_key = None
                except BaseException as ex:
                    failure_key = type(ex).__name__ + ":" + str(ex)
                    if not self._logged_run_failure or failure_key != self._last_run_failure_key:
                        log.error('the galaxy round fell over', exc_info=ex)
                        self._logged_run_failure = True
                        self._last_run_failure_key = failure_key
        except BaseException:
            log.exception('galaxy loop died at the outer layer')
