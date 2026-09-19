# github.com/Shran21
from __future__ import annotations

from contextlib import suppress

from rebsgo import paths
from rebsgo.gamedata.from_json.game_data_loader import GameDataLoader

import datetime as _dt
import json
import logging
from enum import Enum

from rebsgo.services import Services
from rebsgo.world.movement.maneuvers import PulseManeuver, TeleportManeuver
from rebsgo.pilots.state.holdings.storages import Mail
from rebsgo.pilots.state.boosts.boost import Boost
from rebsgo.pilots.state.options.option import Option
from rebsgo.pilots.state.options.kinds.option_kinds import OptionDecimal
from rebsgo.protocol.wire_base import BgoProtocol
from rebsgo.protocol.debug.debug_replies import DebugReplies
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.protocol_book_replies import replies_for, game_replies
from rebsgo.world.sectors.building.spawners import TendrilCluster
from rebsgo.world.sectors.powers.deeds import SurveyDeed
from rebsgo.world.sectors.harm.damage_line import DamageLine
from rebsgo.world.sectors.npc_minds import PatrolGoal
from rebsgo.world.sectors.sector_maths import clear_non_player, remove_colliding_asteroids
from rebsgo.vocabulary.pilot import ServerRoles, Faction, FactionGroup, BoostSource, BoostKind, ResourceKind, OldShipRole
from rebsgo.vocabulary.world import VisibilityCause, ArrivalCause, DepartureCause, ObjectKind
from rebsgo.vocabulary.client import JumpRefusal, JumpRefusalLevel
from rebsgo.geometry.primitives.euler3 import Euler3
from rebsgo.geometry.primitives.quaternion import Quaternion
from rebsgo.geometry.primitives.transform import Transform
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.geometry.collider_shapes import AABB
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.library import Catalogue
from rebsgo.gamedata.npc_minds import template_of_tier
from rebsgo.gamedata.object_templates import WeaponPlatformSpec
from rebsgo.gamedata.ship_setups import first_best_config_for_guid
from rebsgo.gamedata.ship_parts.parts import CountableItem, ItemType, ShipSystem
from rebsgo.gamedata.reading import ShipSlotType
from rebsgo.helpers.dice import Dice
from rebsgo.journal import hivasi_lanc
from rebsgo import journal


log = logging.getLogger(__name__)

_UTC = _dt.timezone.utc


def _parse_bool(raw) -> bool:
    return raw is not None and raw.strip().lower() == "true"


def _spawn_tipusok() -> dict:
    olvaso = GameDataLoader(paths.JATEKADAT / "templates" / "Dev")
    for ut in olvaso.file_paths():
        if ut.name == "spawn_types.json":
            if (adat := olvaso.read_json(ut)) is not None:
                return {k: v for k, v in adat.items() if isinstance(v, dict)}
    return {}


SPAWN_TIPUSOK = _spawn_tipusok()


class _ClientMessage(Enum):
    Command = 1
    Activity = 12
    ProcessState = 14
    UpgradeSystem = 17

    @staticmethod
    def from_code(value):
        return _CM_BY_VALUE.get(value)


_CM_BY_VALUE = {member.value: member for member in _ClientMessage}


class DebugProtocol(BgoProtocol):
    def __init__(self, ctx, pilot_roster, sector_book, nemitas, visszaterito):
        super().__init__(ProtocolID.Debug, ctx)
        self._application_bootstrap = None
        self._refund_processor = visszaterito
        self._catalogue = Services.get(Catalogue)
        self._sector_book = sector_book
        self._pilot_roster = pilot_roster
        self._writer = DebugReplies()
        self._chat_access_blocker = nemitas
        self._sys_prev_map = None

    @property
    def replies(self) -> DebugReplies:
        return self._writer


    def read_message(self, msg_type: int, br) -> None:
        client_message = _ClientMessage.from_code(msg_type)
        log.debug('dev console: %s', client_message)

        player = self.ctx.user().pilot_of()
        roles = player.bgo_admin_roles
        is_console = roles.wears_role(ServerRoles.Console)
        is_moderator = roles.wears_role(ServerRoles.Mod)
        if not is_console or is_moderator:
            typed_text = ""
            if client_message == _ClientMessage.Command:
                typed_text = br.read_string()
            journal.audit().warning('console command refused for want of rank: %s %s',
                                    self.ctx.user().user_log(), typed_text)
            return

        if client_message == _ClientMessage.Activity:
            log.error('the activity report went away in the client long ago; ignoring. %s',
                      self.ctx.user().user_log())
        elif client_message == _ClientMessage.ProcessState:
            self.ctx.user().send(self._writer.process_state('no state was set'))
        elif client_message == _ClientMessage.UpgradeSystem:
            self.tell_console('nothing implements this')
        elif client_message == _ClientMessage.Command:
            command = br.read_string()
            journal.audit().info('%s console command %s from %s', self.ctx.user().user_log(),
                                 command, player.name)

            command = operator_aliases().get(command, command)
            player_protocol = self.ctx.user().protocol_of(ProtocolID.Pilot)

            talalt = False
            if roles.wears_role(ServerRoles.Developer):
                talalt = self.read_dev_command(br, command)
            if self._parse_command(br, command, player, roles, player_protocol):
                talalt = True
            if not talalt:
                self.tell_console(f'unknown command: {command}')
        else:
            log.error('dev protocol has no branch for kind %s', client_message)


    DEV_PARANCSOK = {
        "sector.zones": "_cmd_sector_zones",
        "pilot.role": "_cmd_pilot_role",
        "pilot.role-for": "_cmd_pilot_role_for",
        "server.stop": "_cmd_server_stop",
        "boost.loot": "_cmd_boost_loot",
        "boost.di": "_cmd_boost_di",
        "pilot.multi-login": "_cmd_pilot_multi_login",
        "server.gear-level": "_cmd_server_gear_level",
        "server.gear-by-faction": "_cmd_server_gear_by_faction",
        "assignment.clear": "_cmd_assignment_clear",
        "assignment.clear-for": "_cmd_assignment_clear_for",
        "assignment.repair": "_cmd_assignment_repair",
        "server.hull-census": "_cmd_server_hull_census",
        "server.hull-keys": "_cmd_server_hull_keys",
        "tally.set": "_cmd_tally_set",
        "tally.add": "_cmd_tally_add",
    }

    def read_dev_command(self, br, command) -> bool:
        kezelo = self.DEV_PARANCSOK.get(command)
        if kezelo is None:
            return False
        getattr(self, kezelo)(br, command)
        return True

    def _cmd_assignment_clear(self, br, command) -> None:
        for usr in self._pilot_roster.values():
            usr_mission_book = usr.pilot_of().tally_desk.mission_book
            all_missions = [m.server_id for m in usr_mission_book.find_all(lambda mission: True)]
            usr_mission_book.reset()
            pilot_wire = replies_for(ProtocolID.Pilot)
            usr.send(pilot_wire.remove_missions(all_missions))

    def _cmd_assignment_clear_for(self, br, command) -> None:
        nev = br.read_string()
        usr = self._pilot_roster.by_name(nev)
        if usr is None:
            self.tell_console('no player by that name ' + nev)
            return
        usr_mission_book = usr.pilot_of().tally_desk.mission_book
        all_missions = [m.server_id for m in usr_mission_book.find_all(lambda mission: True)]
        usr_mission_book.reset()
        pilot_wire = replies_for(ProtocolID.Pilot)
        usr.send(pilot_wire.remove_missions(all_missions))

    def _cmd_assignment_repair(self, br, command) -> None:
        username = br.read_string()
        usr = self._pilot_roster.by_name(username)
        if usr is None:
            return
        ids_to_delete = set()
        ids_to_delete.add(1031)
        ids_to_delete.add(2031)
        usr.pilot_of().tally_desk.mission_book.remove_item(1031)
        usr.pilot_of().tally_desk.mission_book.remove_item(2031)
        from rebsgo.protocol.pilot.pilot_replies import PilotReplies
        pilot_wire = PilotReplies()
        usr.send(pilot_wire.remove_missions(ids_to_delete))

    def _cmd_boost_di(self, br, command) -> None:
        roles = self.ctx.user().pilot_of().bgo_admin_roles
        if (roles.wears_role(ServerRoles.Console) and self.ctx.user().pilot_of().user_id_of() == 1) \
                or self.ctx.user().pilot_of().user_id_of() == 2:
            try:
                augment_guid = ResourceKind.DivineInspiration.guid
                raw_player_name = br.read_string()
                times = int(self.read_number(br))
                custom_time_hours = int(self.read_number(br))

                user = self._pilot_roster.by_name(raw_player_name)
                if user is None:
                    log.warning('that username does not pass: {}'.format(raw_player_name))
                    return

                for _i in range(times):
                    user_for_di = user
                    player_protocol = user_for_di.protocol_of(ProtocolID.Pilot)
                    player_protocol.light_augment(augment_guid, custom_time_hours)
            except Exception as exception:
                self.tell_console(str(exception))

    def _cmd_boost_loot(self, br, command) -> None:
        try:
            raw_player_name = br.read_string()
            times = int(self.read_number(br))
            custom_time_hours = int(self.read_number(br))

            user = self._pilot_roster.by_name(raw_player_name)
            if user is None:
                log.warning('that username does not pass: {}'.format(raw_player_name))
                return

            user_for_di = user
            factors = user_for_di.pilot_of().factors
            now = _dt.datetime.now(_UTC)

            for _i in range(times):
                factors.take_boost(Boost.starting_at(
                    BoostKind.Loot, BoostSource.Marketing, 1, now, custom_time_hours))
        except Exception as exception:
            self.tell_console(str(exception))

    def _cmd_pilot_multi_login(self, br, command) -> None:
        ip_addresses = set()
        parts = ['shared-address check:', "\n"]
        for usr in self._pilot_roster.values():
            if usr.is_connected():
                contained = usr in ip_addresses
                if not contained:
                    ip_addresses.add(usr)
                if contained:
                    parts.append('same address: ')
                    parts.append(str(usr.pilot_of()))
                    parts.append("\n")
        self.tell_console("".join(parts))

    def _cmd_pilot_role(self, br, command) -> None:
        roles = self.ctx.user().pilot_of().bgo_admin_roles
        if (roles.wears_role(ServerRoles.Console) and self.ctx.user().pilot_of().user_id_of() == 1) \
                or self.ctx.user().pilot_of().user_id_of() == 2:
            try:
                raw_player_id = br.read_string()
                raw_role_bit = br.read_string()

                player_id = int(raw_player_id)
                role_bits = int(raw_role_bit)
                user_for_permissions = self._pilot_roster.by_id(player_id)
                if user_for_permissions is None:
                    return
                user_for_permissions.pilot_of().bgo_admin_roles.set_or(role_bits)
                journal.audit().warning('%s granted roles %s to pilot %s',
                                        self.ctx.user().user_log(), role_bits, player_id)
                user_for_permissions.send(self._writer.update_roles(role_bits))
            except ValueError as nem_szam:
                self.tell_console(str(nem_szam))

    def _cmd_pilot_role_for(self, br, command) -> None:
        roles = self.ctx.user().pilot_of().bgo_admin_roles
        if (roles.wears_role(ServerRoles.Console) and self.ctx.user().pilot_of().user_id_of() == 1) \
                or self.ctx.user().pilot_of().user_id_of() == 2:
            try:
                raw_player_name = br.read_string()
                raw_role_bit = br.read_string()

                role_bits = int(raw_role_bit)
                user_for_permissions = self._pilot_roster.by_name(raw_player_name)
                if user_for_permissions is None:
                    log.error('role update names a role we do not have %s', raw_player_name)
                    return
                user_for_permissions.pilot_of().bgo_admin_roles.set_or(role_bits)
                journal.audit().warning('%s granted roles %s to %s',
                                        self.ctx.user().user_log(), role_bits, raw_player_name)
                user_for_permissions.send(self._writer.update_roles(role_bits))
            except ValueError as nem_szam:
                self.tell_console(str(nem_szam))

    def _cmd_sector_zones(self, br, command) -> None:
        try:
            from rebsgo.protocol.zone import AreaInfo
            zone_protocol = self.ctx.user().protocol_of(ProtocolID.Zone)
            bw = zone_protocol.replies.active_zones([AreaInfo.endless_zone(463726137)])
            self.ctx.user().send([bw])
        except Exception as e:
            log.error('show_zones fell over: {}'.format(hivasi_lanc(e)))

    def _cmd_server_gear_by_faction(self, br, command) -> None:
        grouped = {}
        for ertek in self._pilot_roster.values():
            if not ertek.is_connected():
                continue
            hangar = ertek.pilot_of().hangar_of()
            active_ship = hangar.active_ship()
            szintek = []
            for rekesz in active_ship.ship_slots.values():
                if rekesz.ship_system is None or rekesz.ship_system.card_guid_of() == 0:
                    continue
                if rekesz.ship_system.ship_system_card.ship_slot_type == ShipSlotType.avionics:
                    continue
                szintek.append(rekesz.ship_system.ship_system_card.level)
            avg = (sum(szintek) / len(szintek)) if len(szintek) != 0 else 1
            grouped.setdefault(ertek.pilot_of().faction, []).append(avg)
        parts = []
        for frakcio, avg_list in grouped.items():
            faction_avg = sum(avg_list) / len(avg_list)
            parts.append('faction ')
            parts.append(str(frakcio))
            parts.append(" avg ")
            parts.append(str(faction_avg))
            parts.append("\n")
        self.tell_console("".join(parts))

    def _cmd_server_gear_level(self, br, command) -> None:
        parts = []
        for ertek in self._pilot_roster.values():
            if not ertek.is_connected():
                continue
            try:
                active_ship = ertek.pilot_of().hangar_of().active_ship()
                szintek = []
                for ship_slot in active_ship.ship_slots.values():
                    if ship_slot.ship_system is None:
                        continue
                    if ship_slot.ship_system.ship_system_card is None:
                        continue
                    if ship_slot.ship_system.ship_system_card.ship_slot_type == ShipSlotType.avionics:
                        continue
                    szintek.append(ship_slot.ship_system.ship_system_card.level)
                if len(szintek) == 0:
                    continue
                avg_double_level = sum(szintek) / len(szintek)
                parts.append('pilot ')
                parts.append(ertek.pilot_of().name)
                parts.append(" level: ")
                parts.append("%.2f" % avg_double_level)
                parts.append("\n")
            except Exception:
                pass
        self.tell_console("".join(parts))

    def _cmd_server_hull_census(self, br, command) -> None:
        is_testing_mode = self.ctx.server_config.starter_params.testing_mode
        eredmeny = {}
        for usr in self._pilot_roster.values():
            if not (is_testing_mode or not usr.pilot_of().bgo_admin_roles.holds_any_role(ServerRoles.Developer)):
                continue
            if not (is_testing_mode or not usr.pilot_of().bgo_admin_roles.holds_any_role(ServerRoles.CommunityManager)):
                continue
            if not usr.is_connected():
                continue
            kulcs = usr.pilot_of().hangar_of().active_ship().ship_card_of().ship_object_key
            eredmeny[kulcs] = eredmeny.get(kulcs, 0) + 1
        parts = []
        for kulcs, ertek in eredmeny.items():
            if ertek is None or ertek == 0:
                continue
            parts.append('object key ')
            parts.append(str(kulcs))
            parts.append(" ")
            parts.append(str(ertek))
            parts.append("\n")
        self.tell_console("".join(parts))

    def _cmd_server_hull_keys(self, br, command) -> None:
        try:
            is_testing_mode = self.ctx.server_config.starter_params.testing_mode
            full_obj_key_map = {}
            for usr in self._pilot_roster.values():
                if not (is_testing_mode or not usr.pilot_of().bgo_admin_roles.holds_any_role(ServerRoles.Developer)):
                    continue
                if not (is_testing_mode or not usr.pilot_of().bgo_admin_roles.holds_any_role(ServerRoles.CommunityManager)):
                    continue
                if not usr.is_connected():
                    continue
                if not usr.pilot_of().hangar_of().flying_something():
                    continue
                kulcs = usr.pilot_of().hangar_of().active_ship().ship_card_of().ship_object_key
                full_obj_key_map[kulcs] = full_obj_key_map.get(kulcs, 0) + 1
            parts = [
                "gungnir/nidhogg: ",
                str(full_obj_key_map.get(10000157, 0) + full_obj_key_map.get(10000073, 0)),
                "\n",
                "aesir/fenrir: ",
                str(full_obj_key_map.get(10000156, 0) + full_obj_key_map.get(10000009, 0)),
                "\n",
                "jotunn/jormung: ",
                str(full_obj_key_map.get(10000188, 0) + full_obj_key_map.get(10000089, 0)),
                "\n",
                "vanir/hel: ",
                str(full_obj_key_map.get(10000186, 0) + full_obj_key_map.get(10000043, 0)),
            ]
            self.tell_console("".join(parts))
        except Exception as exception:
            self.tell_console("ERROR:" + str(exception))

    def _cmd_server_stop(self, br, command) -> None:
        self._on_shutdown()

    def _cmd_tally_add(self, br, command) -> None:
        nev = br.read_string()
        try:
            counter_guid, star_card_guid, mennyivel = (
                int(br.read_string()) for _ in range(3))

            usr = self._pilot_roster.by_name(nev)
            if usr is None:
                self.tell_console('no pilot named ' + nev + ' is here')
                return
            usr.pilot_of().tally_desk.bump_counter(counter_guid, star_card_guid, mennyivel)
        except Exception as ex:
            self.tell_console(str(ex))

    def _cmd_tally_set(self, br, command) -> None:
        try:
            nev = br.read_string()
            counter_guid = self.read_number(br)
            new_value = self.read_number(br)

            usr = self._pilot_roster.by_name(nev)
            if usr is None:
                self.tell_console('no pilot named ' + nev + ' is here')
                return
            usr.pilot_of().tally_desk.set_counter(counter_guid, new_value)
        except Exception as ex:
            self.tell_console(str(ex))


    PARANCSOK = {
        "consumable": "_cmd_ammo_give",
        "experience": "_cmd_pilot_xp",
        "god_mode": "_cmd_ship_invulnerable",
        "kill_target": "_cmd_target_kill",
        "loot_target": "_cmd_target_loot",
        "resource": "_cmd_pilot_resource",
        "room": "_cmd_pilot_station",
        "sector": "_cmd_sector_jump",
        "sector_events_start_all": "_cmd_sector_event",
        "sector_op": "_cmd_outpost_points",
        "self_buff": "_cmd_ship_buff",
        "skill_learn": "_cmd_pilot_train",
        "skill_unlearn": "_cmd_pilot_untrain",
        "spawn_comet": "_cmd_comet_spawn",
        "stats_debug_dump": "_cmd_server_report",
        "system": "_cmd_object_report",

        "kill_em_all": "_cmd_devpanel_kill_em_all",
        "reset_mobs": "_cmd_devpanel_reset_mobs",
        "loot_target_x10": "_cmd_devpanel_loot_target_x10",
        "change_faction": "_cmd_devpanel_change_faction",
        "static_debug": "_cmd_devpanel_static_debug",
        "uber": "_cmd_devpanel_uber",
        "spawn_mine": "_cmd_devpanel_spawn_mine",
        "complete_story": "_cmd_devpanel_not_wired",
        "start_story": "_cmd_devpanel_not_wired",
        "story_wave_beta_colonial": "_cmd_devpanel_not_wired",
        "story_wave_gamma_colonial": "_cmd_devpanel_not_wired",
        "story_wave_delta_colonial": "_cmd_devpanel_not_wired",
        "to_zone": "_cmd_devpanel_not_wired",
        "detach": "_cmd_devpanel_not_wired",
        "short_circuit": "_cmd_devpanel_not_wired",
        "spawn_flare": "_cmd_devpanel_not_wired",
        "spawn_missile": "_cmd_devpanel_not_wired",
        "save_and_crash_player": "_cmd_devpanel_refused",
        "reset_player": "_cmd_devpanel_refused",
        "print_payment_counters": "_cmd_devpanel_not_wired",
        "set_last_payment": "_cmd_devpanel_not_wired",
        "add_offer_package_booking": "_cmd_devpanel_not_wired",
        "reset_offer_package_bookings": "_cmd_devpanel_not_wired",
        "clear_counter": "_cmd_devpanel_not_wired",
        "update_counter": "_cmd_devpanel_not_wired",
        "death": "_cmd_devpanel_death",
        "jumped": "_cmd_devpanel_not_wired",
        "dispell": "_cmd_devpanel_dispell",
        "restart": "_cmd_devpanel_use_the_panel",
        "restart_sector": "_cmd_devpanel_use_the_panel",

        "pilot.address": "_cmd_pilot_address",
        "pilot.rename": "_cmd_pilot_rename",
        "paint.drop-all": "_cmd_paint_drop_all",
        "pilot.faction": "_cmd_pilot_faction",
        "pilot.kick": "_cmd_pilot_kick",
        "pilot.mute": "_cmd_pilot_mute",
        "pilot.kick-for": "_cmd_pilot_kick_for",
        "object.mark": "_cmd_object_mark",
        "mail.send": "_cmd_mail_send",
        "mail.send-to": "_cmd_mail_send_to",
        "notice.me": "_cmd_notice_me",
        "target.report": "_cmd_target_report",
        "ship.buff": "_cmd_ship_buff",
        "ship.invulnerable": "_cmd_ship_invulnerable",
        "outpost.points-max": "_cmd_outpost_points_max",
        "outpost.points": "_cmd_outpost_points",
        "sector.event": "_cmd_sector_event",
        "server.online": "_cmd_server_online",
        "sector.census": "_cmd_sector_census",
        "pilot.list": "_cmd_pilot_list",
        "pilot.xp": "_cmd_pilot_xp",
        "pilot.xp-for": "_cmd_pilot_xp_for",
        "pilot.xp-set": "_cmd_pilot_xp_set",
        "ship.visibility": "_cmd_ship_visibility",
        "target.scan-all": "_cmd_target_scan_all",
        "boost.clear": "_cmd_boost_clear",
        "notice.banner": "_cmd_notice_banner",
        "boost.report": "_cmd_boost_report",
        "assignment.report": "_cmd_assignment_report",
        "target.scan-all-for": "_cmd_target_scan_all_for",
        "pilot.resource": "_cmd_pilot_resource",
        "pilot.resource-for": "_cmd_pilot_resource_for",
        "augment.try": "_cmd_augment_try",
        "pilot.settings": "_cmd_pilot_settings",
        "pilot.station": "_cmd_pilot_station",
        "ship.teleport-centre": "_cmd_ship_teleport_centre",
        "target.kill": "_cmd_target_kill",
        "pilot.train": "_cmd_pilot_train",
        "pilot.untrain": "_cmd_pilot_untrain",
        "ship.speed": "_cmd_ship_speed",
        "server.stop-now": "_cmd_server_stop_now",
        "sector.jump-notice": "_cmd_sector_jump_notice",
        "server.report": "_cmd_server_report",
        "sector.clear": "_cmd_sector_clear",
        "pilot.squad-refresh": "_cmd_pilot_squad_refresh",
        "asteroid.tendril": "_cmd_asteroid_tendril",
        "asteroid.ring": "_cmd_asteroid_ring",
        "sector.fill": "_cmd_sector_fill",
        "asteroid.unstick": "_cmd_asteroid_unstick",
        "target.loot": "_cmd_target_loot",
        "asteroid.clear-water": "_cmd_asteroid_clear_water",
        "asteroid.clear": "_cmd_asteroid_clear",
        "asteroid.ore-report": "_cmd_asteroid_ore_report",
        "planet.mining-rig": "_cmd_planet_mining_rig",
        "sector.template": "_cmd_sector_template",
        "sector.jump": "_cmd_sector_jump",
        "ship.fly": "_cmd_ship_fly",
        "ship.fly-for": "_cmd_ship_fly_for",
        "comet.spawn": "_cmd_comet_spawn",
        "nebula.spawn": "_cmd_nebula_spawn",
        "cargo.spawn": "_cmd_cargo_spawn",
        "debris.spawn": "_cmd_debris_spawn",
        "planet.spawn": "_cmd_planet_spawn",
        "comet.spawn-guid": "_cmd_comet_spawn_guid",
        "npc.spawn": "_cmd_npc_spawn",
        "platform.ring": "_cmd_platform_ring",
        "platform.spawn": "_cmd_platform_spawn",
        "drone.spawn": "_cmd_drone_spawn",
        "debris.clear": "_cmd_debris_clear",
        "planet.clear": "_cmd_planet_clear",
        "reward.try": "_cmd_reward_try",
        "notice.restart": "_cmd_notice_restart",
        "notice.all": "_cmd_notice_all",
        "object.report-guid": "_cmd_object_report_guid",
        "object.report": "_cmd_object_report",
        "ship.max-gear": "_cmd_ship_max_gear",
        "ship.teleport": "_cmd_ship_teleport",
        "pilot.save": "_cmd_pilot_save",
        "ammo.give": "_cmd_ammo_give",
        "ammo.weapons": "_cmd_ammo_weapons",
        "ammo.hull": "_cmd_ammo_hull",
        "ammo.computer": "_cmd_ammo_computer",
        "ammo.engine": "_cmd_ammo_engine",
        "ammo.all": "_cmd_ammo_all",
        "refund.all": "_cmd_refund_all",
    }

    def _apply_ability_multiplier(self, player, stats, multiplier: float) -> None:
        from rebsgo.helpers.floats import f32
        sector = self._sector_book.sector_by_id(player.sector_id)
        if sector is None:
            return
        ship = sector.ctx.users().ship_of_pilot(player.user_id_of())
        if ship is None:
            return
        rekeszek = ship.space_subscribe_info().ship_slots
        if rekeszek is None:
            return
        for rekesz in rekeszek.values():
            kepesseg = rekesz.ship_ability()
            if kepesseg is None or kepesseg.ship_ability_card is None:
                continue
            buff = kepesseg.item_buff_add
            card_buff = kepesseg.ship_ability_card.item_buff_add
            for stat in stats:
                if card_buff.holds_stat(stat):
                    buff.set_stat(stat, f32(card_buff.stat(stat) * multiplier))

    def _apply_dmg_buff(self, player, multiplier: float) -> None:
        from rebsgo.gamedata.reading import ObjectStat
        self._apply_ability_multiplier(
            player, (ObjectStat.DamageLow, ObjectStat.DamageHigh), multiplier)

    def _celzott_objektum(self, player):
        sector = self._sector_book.sector_by_id(player.sector_id)
        if sector is None:
            return None, None, None
        ship = sector.ctx.users().ship_of_pilot(player.user_id_of())
        if ship is None:
            return sector, None, None
        cel_id = ship.space_subscribe_info().target_object_id
        celpont = None if cel_id is None else sector.ctx.space_objects().get(cel_id.get())
        return sector, ship, celpont

    def _cmd_ammo_all(self, br, command, player, roles, player_protocol) -> None:
        self._handle_refill_command(br, "all_ammo", None)

    def _cmd_ammo_computer(self, br, command, player, roles, player_protocol) -> None:
        self._handle_refill_command(br, "computer_ammo", {ShipSlotType.computer})

    def _cmd_ammo_engine(self, br, command, player, roles, player_protocol) -> None:
        self._handle_refill_command(br, "engine_ammo", {ShipSlotType.engine})

    def _cmd_ammo_give(self, br, command, player, roles, player_protocol) -> None:
        try:
            player_name = br.read_string()
            item_guid = self.read_number(br)
            darab = self.read_number(br)
            user = self._pilot_roster.by_name(player_name)
            if user is None:
                log.warning('no player found %s', player_name)
                return
            atmeneti = user
            countable = CountableItem.from_guid(item_guid, darab)
            hold = atmeneti.pilot_of().hold
            from rebsgo.pilots.state.holdings.walks.hold_walk import HoldWalk
            hold_walker = HoldWalk(atmeneti, self.ctx.rng)
            hold_walker.add_ship_item(countable, hold)
        except Exception as ex:
            self.tell_console(str(ex))

    def _cmd_ammo_hull(self, br, command, player, roles, player_protocol) -> None:
        self._handle_refill_command(br, "hull_ammo", {ShipSlotType.hull})

    def _cmd_ammo_weapons(self, br, command, player, roles, player_protocol) -> None:
        self._handle_refill_command(br, "weapon_ammo",
                                    {ShipSlotType.weapon, ShipSlotType.gun, ShipSlotType.defensive_weapon,
                                     ShipSlotType.special_weapon, ShipSlotType.launcher})

    def _cmd_assignment_report(self, br, command, player, roles, player_protocol) -> None:
        story_protocol_write_only = replies_for(ProtocolID.Story)
        self.ctx.user().send(story_protocol_write_only.mission_log("testtext"))

    def _cmd_asteroid_clear(self, br, command, player, roles, player_protocol) -> None:
        sector = self._sector_book.sector_by_id(player.sector_id)
        if sector is None:
            return
        ship = sector.ctx.users().ship_of_pilot(player.user_id_of())
        if ship is None:
            return
        asteroids = sector.ctx.space_objects().space_objects_of_entity_type(ObjectKind.Asteroid)
        for asteroid in asteroids:
            if (zsakmany := sector.loot_ownership.get(asteroid)) is None:
                continue
            sector.damage_book.hurt(
                DamageLine(ship, asteroid, 999_999, kritikus=False,
                           ekkor=sector.ctx.tick().time_stamp()))

    def _cmd_asteroid_clear_water(self, br, command, player, roles, player_protocol) -> None:
        sector = self._sector_book.sector_by_id(player.sector_id)
        if sector is None:
            return
        ship = sector.ctx.users().ship_of_pilot(player.user_id_of())
        if ship is None:
            return
        asteroids = sector.ctx.space_objects().space_objects_of_entity_type(ObjectKind.Asteroid)
        for asteroid in asteroids:
            zsakmany = sector.loot_ownership.get(asteroid)
            if zsakmany is None:
                continue
            asteroid_loot = zsakmany
            if asteroid_loot.ressource.card_guid_of() == ResourceKind.Water.guid:
                sector.damage_book.hurt(
                    DamageLine(ship, asteroid, 999_999, kritikus=False,
                           ekkor=sector.ctx.tick().time_stamp()))

    def _cmd_asteroid_ore_report(self, br, command, player, roles, player_protocol) -> None:
        sector = self._sector_book.sector_by_id(player.sector_id)
        if sector is None:
            return
        ship = sector.ctx.users().ship_of_pilot(player.user_id_of())
        if ship is None:
            return
        spawn_runner = sector.spawn_runner
        current_distribution = spawn_runner.asteroid_distribution()
        formated_str = "resource_dump[%d] %s" % (sector.id, current_distribution)
        log.info(formated_str)
        self.tell_console(formated_str)

    def _cmd_asteroid_ring(self, br, command, player, roles, player_protocol) -> None:
        try:
            (seed, spread_from_centre, asteroid_count, belso, kulso,
             szog) = (int(br.read_string()) for _ in range(6))
            min_distance, max_distance, angle_shift = float(belso), float(kulso), float(szog)

            sector = self._sector_book.sector_by_id(player.sector_id)
            if sector is None:
                return
            generation_utils = self._sector_book.sector_random_generation_utils
            generation_utils.scatter_ring(sector, Dice(seed),
                                          spread_from_centre, asteroid_count,
                                          min_distance, max_distance, angle_shift)
        except Exception as ex:
            log.error('random ring misbehaved', exc_info=ex)

    def _cmd_asteroid_tendril(self, br, command, player, roles, player_protocol) -> None:
        (seed, spread_from_centre, asteroid_count, tentacle_count,
         szog) = (int(br.read_string()) for _ in range(5))
        angle_shift = float(szog)

        sector = self._sector_book.sector_by_id(player.sector_id)
        if sector is None:
            return
        generation_utils = self._sector_book.sector_random_generation_utils
        tentacle_cluster = TendrilCluster(sector, asteroid_count, tentacle_count, angle_shift, Dice(seed), spread_from_centre)
        generation_utils.scatter_one(sector, tentacle_cluster)

    def _cmd_asteroid_unstick(self, br, command, player, roles, player_protocol) -> None:
        sector = self._sector_book.sector_by_id(player.sector_id)
        if sector is None:
            return
        remove_colliding_asteroids(sector)

    def _cmd_augment_try(self, br, command, player, roles, player_protocol) -> None:
        augment_items = []
        d = CountableItem.from_guid(ResourceKind.Cubits.guid, 10000)
        s = ShipSystem.from_guid(20001922)
        augment_items.append(d)
        augment_items.append(s)
        notification_protocol = self.ctx.user().protocol_of(ProtocolID.Notification)
        notification_protocol.hand_out_augments(augment_items)

    def _cmd_boost_clear(self, br, command, player, roles, player_protocol) -> None:
        self.ctx.user().pilot_of().factors.remove_all()
        pilot_wire = replies_for(ProtocolID.Pilot)
        self.ctx.user().send(pilot_wire.factors(self.ctx.user().pilot_of().factors))
        self.tell_console('factor map wiped')

    def _cmd_boost_report(self, br, command, player, roles, player_protocol) -> None:
        factors = self.ctx.user().pilot_of().factors
        self.tell_console("factors " + str(len(factors.values())))
        for szorzo in factors.values():
            self.tell_console(str(szorzo))

    def _cmd_cargo_spawn(self, br, command, player, roles, player_protocol) -> None:
        try:
            cargo_guid = self.read_number(br)
        except Exception:
            cargo_guid = 50000113
        if not cargo_guid:
            cargo_guid = 50000113
        sector = self._sector_book.sector_by_id(player.sector_id)
        if sector is None:
            return
        ps = sector.ctx.users().ship_of_pilot(player.user_id_of())
        if ps is None:
            self.tell_console("spawn_cargo: no player ship in sector")
            return
        pos = ps.mover_of().position_of()
        spawn_pos = Vector3(pos.x + 200, pos.y, pos.z + 200)
        try:
            cargo = sector.ctx.object_forge.create_cargo(
                cargo_guid, Transform(spawn_pos, Euler3(0, 0, 0).quaternion))
            sector.arrival_gate.admit_object(cargo)
            self.tell_console("spawned cargo container id=" + str(cargo.id_in_space())
                             + " guid=" + str(cargo_guid))
        except Exception as ex:
            self.tell_console("spawn_cargo failed: " + str(ex))

    def _cmd_comet_spawn(self, br, command, player, roles, player_protocol) -> None:
        if not roles.wears_role(ServerRoles.Developer):
            return
        sector = self._sector_book.sector_by_id(self.ctx.user().pilot_of().sector_id)
        if sector is None:
            return
        comet = sector.ctx.object_forge.hatch_comet(23)
        sector.arrival_gate.admit_object(comet)

    def _cmd_comet_spawn_guid(self, br, command, player, roles, player_protocol) -> None:
        try:
            guid = int(br.read_string())
            sector = self._sector_book.sector_by_id(self.ctx.user().pilot_of().sector_id)
            if sector is None:
                return
            debris = sector.ctx.object_forge.hatch_comet(guid, Transform.identity())
            sector.arrival_gate.admit_object(debris)
        except Exception as ex:
            self.tell_console(str(ex))

    def _cmd_debris_clear(self, br, command, player, roles, player_protocol) -> None:
        sector = self._sector_book.sector_by_id(self.ctx.user().pilot_of().sector_id)
        if sector is None:
            return
        for debris in sector.ctx.space_objects().space_objects_of_entity_type(ObjectKind.Debris):
            sector.departures_desk.note_removal_cause(debris, DepartureCause.Death)

    def _cmd_debris_spawn(self, br, command, player, roles, player_protocol) -> None:
        try:
            guid = self.read_number(br)
            y_axis = self.read_number(br)
            sector = self._sector_book.sector_by_id(self.ctx.user().pilot_of().sector_id)
            if sector is None:
                return
            pos = Vector3(0, y_axis, 0)
            rot = Euler3(0, 0, 0).quaternion
            debris = sector.ctx.object_forge.hatch_debris(guid, Transform(pos, rot))
            sector.arrival_gate.admit_object(debris)
        except Exception as ex:
            self.tell_console(str(ex))

    def _cmd_devpanel_change_faction(self, br, command, player, roles, player_protocol) -> None:
        oldal = br.read_string().strip().lower()
        if oldal not in ("colonial", "cylon"):
            self.tell_console('change_faction wants colonial or cylon')
            return

        class _Szavak:
            def __init__(self, szavak):
                self._szavak = list(szavak)

            def read_string(self):
                return self._szavak.pop(0)

        self._cmd_pilot_faction(_Szavak([player.name, "false", "0"]),
                                command, player, roles, player_protocol)

    def _cmd_devpanel_death(self, br, command, player, roles, player_protocol) -> None:
        sector = self._sector_book.sector_by_id(player.sector_id)
        if sector is None:
            return
        ship = sector.ctx.users().ship_of_pilot(player.user_id_of())
        if ship is None or ship.is_removed():
            self.tell_console('death: no live ship to sink')
            return
        sector.departures_desk.note_removal_cause(ship, DepartureCause.Death)
        self.tell_console('death: down you go')

    def _cmd_devpanel_dispell(self, br, command, player, roles, player_protocol) -> None:
        self.self_buff("dispell", player)

    def _cmd_devpanel_kill_em_all(self, br, command, player, roles, player_protocol) -> None:
        sector = self._sector_book.sector_by_id(player.sector_id)
        if sector is None:
            return
        darab = 0
        for kind in (ObjectKind.BotFighter, ObjectKind.Cruiser):
            for bot in list(sector.ctx.space_objects().objects_of_kind(kind)):
                if not bot.is_removed():
                    sector.departures_desk.note_removal_cause(bot, DepartureCause.Death)
                    darab += 1
        self.tell_console(f'kill_em_all: {darab} NPC down')

    def _cmd_devpanel_loot_target_x10(self, br, command, player, roles, player_protocol) -> None:
        for _ in range(10):
            self._cmd_target_loot(br, command, player, roles, player_protocol)

    def _cmd_devpanel_not_wired(self, br, command, player, roles, player_protocol) -> None:
        self.tell_console(f'{command}: the old shop/story debug path;'
                          ' not wired on this server')

    def _cmd_devpanel_refused(self, br, command, player, roles, player_protocol) -> None:
        self.tell_console(f'{command}: refused on purpose - it would damage the account')

    def _cmd_devpanel_reset_mobs(self, br, command, player, roles, player_protocol) -> None:
        sector = self._sector_book.sector_by_id(player.sector_id)
        if sector is None:
            return
        darab = 0
        for kind in (ObjectKind.BotFighter, ObjectKind.Cruiser):
            for bot in list(sector.ctx.space_objects().objects_of_kind(kind)):
                if not bot.is_removed():
                    sector.departures_desk.note_removal_cause(bot, DepartureCause.JustRemoved)
                    darab += 1
        self.tell_console(f'reset_mobs: {darab} NPC cleared; spawners will refill')

    def _cmd_devpanel_spawn_mine(self, br, command, player, roles, player_protocol) -> None:
        from rebsgo.gamedata.from_json.template_readers import mine_tuning
        from rebsgo.gamedata.reading import ObjectStat
        sector = self._sector_book.sector_by_id(player.sector_id)
        if sector is None:
            return
        ship = sector.ctx.users().ship_of_pilot(player.user_id_of())
        if ship is None:
            self.tell_console('spawn_mine: your ship could not be resolved')
            return
        most = sector.ctx.tick().time_stamp()
        hangolas = mine_tuning()
        try:
            mine = sector.ctx.object_forge.create_mine(
                ship, hangolas.guid_for("he", 1), 1, most, most + 3000)
        except ValueError as baj:
            self.tell_console('spawn_mine: ' + str(baj))
            return
        mine_stats = mine.space_subscribe_info().stats_of
        for stat, ertek in ((ObjectStat.MaxHullPoints, 500.0),
                            (ObjectStat.DamageHigh, 1500.0),
                            (ObjectStat.DamageLow, 1200.0),
                            (ObjectStat.AoeOuterRadius, hangolas.blast_radius),
                            (ObjectStat.LifeTime, hangolas.fallback_life_seconds),
                            (ObjectStat.MaxPowerPoints, 0.0)):
            mine_stats.set_stat(stat, ertek)
        mine.space_subscribe_info().set_hull(mine_stats.stat(ObjectStat.MaxHullPoints))
        mine.space_subscribe_info().cap_hull_and_power()
        sector.arrival_gate.admit_object(mine)
        self.tell_console('spawn_mine: HE mine laid, arms in 3s')

    def _cmd_devpanel_static_debug(self, br, command, player, roles, player_protocol) -> None:
        self.tell_console(f'pilot {player.name} #{player.user_id_of()}'
                          f' faction={player.faction}'
                          f' sector={player.sector_id}'
                          f' roles={roles.role_bits}')

    def _cmd_devpanel_uber(self, br, command, player, roles, player_protocol) -> None:
        roles.set_or(ServerRoles.GodMode.value)
        self.ctx.user().send(self._writer.update_roles(roles.role_bits))
        self.self_buff("heal", player)
        self._start_dmg_buff(player, duration_seconds=180.0)
        journal.audit().warning('%s pressed U.B.E.R.', self.ctx.user().user_log())
        self.tell_console('uber: god mode + heal + damage buff (180s)')

    def _cmd_devpanel_use_the_panel(self, br, command, player, roles, player_protocol) -> None:
        self.tell_console(f'{command}: use the WebPanel; it warns, kicks and'
                          ' restarts in the right order')

    def _cmd_drone_spawn(self, br, command, player, roles, player_protocol) -> None:
        self._spawn_drone(br, player)

    def _cmd_mail_send(self, br, command, player, roles, player_protocol) -> None:
        try:
            nev = br.read_string()
            user = self._pilot_roster.by_name(nev)
            if user is None:
                log.error('mail undeliverable - recipient unknown %s', nev)
                return
            other = user
            mail_items = [
                CountableItem.from_guid(ResourceKind.Cubits.guid, 1_000_000),
                CountableItem.from_guid(ResourceKind.Tylium.guid, 1_000_000),
                CountableItem.from_guid(ResourceKind.Titanium.guid, 1_000_000),
                CountableItem.from_guid(ResourceKind.Token.guid, 1_000_000),
            ]
            mail = Mail(6, mail_items, other.pilot_of().user_id_of())
            mail_box = other.pilot_of().mail_box
            mail_box.add_item(mail)
            pp = other.protocol_of(ProtocolID.Pilot)
            other.send(pp.replies.mail_box(mail_box))
        except Exception as ex:
            log.error('while posting mail', exc_info=ex)

    def _cmd_mail_send_to(self, br, command, player, roles, player_protocol) -> None:
        try:
            nev = br.read_string()
            raw_cubits = br.read_string()
            raw_tylium = br.read_string()
            raw_titanium = br.read_string()
            raw_token = br.read_string()

            cubits = int(raw_cubits)
            tylium = int(raw_tylium)
            titanium = int(raw_titanium)
            token = int(raw_token)

            user = self._pilot_roster.by_name(nev)
            if user is None:
                log.error('no such player here %s', nev)
                return
            other = user
            mail_items = [
                CountableItem.from_guid(ResourceKind.Cubits.guid, cubits),
                CountableItem.from_guid(ResourceKind.Tylium.guid, tylium),
                CountableItem.from_guid(ResourceKind.Titanium.guid, titanium),
                CountableItem.from_guid(ResourceKind.Token.guid, token),
            ]
            mail = Mail(6, mail_items, other.pilot_of().user_id_of())
            mail_box = other.pilot_of().mail_box
            mail_box.add_item(mail)
            pp = other.protocol_of(ProtocolID.Pilot)
            other.send(pp.replies.mail_box(mail_box))
        except Exception as ex:
            log.error('delivering one specific mail', exc_info=ex)

    def _cmd_nebula_spawn(self, br, command, player, roles, player_protocol) -> None:
        sector = self._sector_book.sector_by_id(self.ctx.user().pilot_of().sector_id)
        if sector is None:
            return
        debris_pile = sector.ctx.object_forge.hatch_debris(16)
        sector.arrival_gate.admit_object(debris_pile)

    def _cmd_notice_all(self, br, command, player, roles, player_protocol) -> None:
        msg = br.read_string()
        server_restart_bw = self._writer.message(msg)
        for usr in self._pilot_roster.user_list():
            usr.send(server_restart_bw)

    def _cmd_notice_banner(self, br, command, player, roles, player_protocol) -> None:
        story_protocol_write_only = replies_for(ProtocolID.Story)
        self.ctx.user().send(story_protocol_write_only.banner_box(230))

    def _cmd_notice_me(self, br, command, player, roles, player_protocol) -> None:
        sector = self._sector_book.sector_by_id(player.sector_id)
        if sector is None:
            return
        da = sector.ctx.users().ship_of_pilot(player.user_id_of())
        if da is not None:
            self.tell_console('object id ' + str(da.id_in_space()))

    def _cmd_notice_restart(self, br, command, player, roles, player_protocol) -> None:
        server_restart_bw = self._writer.message('Restart incoming - the server goes down in a few minutes.')
        for usr in self._pilot_roster.user_list():
            usr.send(server_restart_bw)

    def _cmd_npc_spawn(self, br, command, player, roles, player_protocol) -> None:
        self._spawn_npc(br, player)

    def _cmd_object_mark(self, br, command, player, roles, player_protocol) -> None:
        try:
            raw_is_highlighted = br.read_string()
            is_highlighted = raw_is_highlighted == "1"
            current_sector = self._sector_book.sector_by_id(player.sector_id)
            if current_sector is None:
                return
            users = current_sector.ctx.users()
            player_ship = users.ship_of_pilot(self.ctx.user().pilot_of().user_id_of())
            if player_ship is None:
                return
            celpont = player_ship.space_subscribe_info().target_object_id
            if celpont is not None:
                target_id = celpont
                story_protocol = self.ctx.user().protocol_of(ProtocolID.Story)
                highlight_bw = story_protocol.replies.highlight_object(target_id.get(), is_highlighted)
                current_sector.ctx.sender().push_to_everyone(highlight_bw)
            if celpont is None:
                self.tell_console('that target is not around')
        except Exception as ex:
            log.error('while highlighting an object', exc_info=ex)

    def _cmd_object_report(self, br, command, player, roles, player_protocol) -> None:
        try:
            player_name = br.read_string()
            item_guid = self.read_number(br)
            item_level = self.read_number(br)
            user = self._pilot_roster.by_name(player_name)
            if user is None:
                log.warning('no player found %s', player_name)
                return
            atmeneti = user
            all_system_cards = self._catalogue.system_cards(item_guid)
            to_fetch_item = all_system_cards.get(item_level)
            if to_fetch_item is None:
                self.tell_console('no item by that id')
                return
            ship_system = ShipSystem.from_guid(to_fetch_item.card_guid_of())
            hold = atmeneti.pilot_of().hold
            from rebsgo.pilots.state.holdings.walks.hold_walk import HoldWalk
            hold_walker = HoldWalk(atmeneti, self.ctx.rng)
            hold_walker.add_ship_item(ship_system, hold)
        except Exception as ex:
            self.tell_console(str(ex))

    def _cmd_object_report_guid(self, br, command, player, roles, player_protocol) -> None:
        try:
            player_name = br.read_string()
            item_guid = self.read_number(br)
            user = self._pilot_roster.by_name(player_name)
            if user is None:
                log.warning('no player found %s', player_name)
                return
            atmeneti = user
            ship_system = ShipSystem.from_guid(item_guid)
            hold = atmeneti.pilot_of().hold
            from rebsgo.pilots.state.holdings.walks.hold_walk import HoldWalk
            hold_walker = HoldWalk(atmeneti, self.ctx.rng)
            hold_walker.add_ship_item(ship_system, hold)
        except Exception as ex:
            self.tell_console(str(ex))

    def _cmd_outpost_points(self, br, command, player, roles, player_protocol) -> None:
        raw_faction = br.read_string()
        raw_pts = br.read_string()
        try:
            frakcio = Faction.Colonial if raw_faction == "colonial" else Faction.Cylon
            pts = int(raw_pts)
            current_sector = self._sector_book.sector_by_id(player.sector_id)
            if current_sector is None:
                return
            current_state = current_sector.colonial_op_state if frakcio == Faction.Colonial \
                else current_sector.cylon_op_state
            if pts > 0:
                if current_state.is_blocked():
                    current_state.op_down(0)
                current_state.gain_points(pts)
            elif pts < 0:
                current_state.lose_points(abs(pts))
            else:
                log.error('dev command: outpost step of zero does nothing')

            colonial_delta = current_sector.colonial_op_state.delta()
            cylon_delta = current_sector.cylon_op_state.delta()
            current_sector.ctx.sender().push_to_everyone(
                game_replies().outpost_state_broadcast(
                    current_sector.colonial_op_state.op_points, colonial_delta,
                    current_sector.cylon_op_state.op_points, cylon_delta))
        except Exception as ex:
            log.error("sectorop", exc_info=ex)

    def _cmd_outpost_points_max(self, br, command, player, roles, player_protocol) -> None:
        for sector in self._sector_book.sectors():
            sector.cylon_op_state.op_down(0)
            sector.cylon_op_state.gain_points(3000)

            sector.colonial_op_state.op_down(0)
            sector.colonial_op_state.gain_points(3000)

            colonial_delta = sector.colonial_op_state.delta()
            cylon_delta = sector.cylon_op_state.delta()
            sector.ctx.sender().push_to_everyone(
                game_replies().outpost_state_broadcast(
                    sector.colonial_op_state.op_points, colonial_delta,
                    sector.cylon_op_state.op_points, cylon_delta))

    def _cmd_paint_drop_all(self, br, command, player, roles, player_protocol) -> None:
        player_name = br.read_string()
        user_to_remove_paint_from = self._pilot_roster.by_name(player_name)
        if user_to_remove_paint_from is None:
            self.tell_console('no such player name')
            return
        hold = user_to_remove_paint_from.pilot_of().hold
        paint_ids = []
        for tetel in hold.all_ship_items:
            if tetel.item_type != ItemType.System:
                continue
            if tetel.ship_system_card.ship_slot_type != ShipSlotType.ship_paint:
                continue
            paint_ids.append(tetel.server_id)
        for pid in paint_ids:
            hold.take_item(pid)
        for to_remove_id in paint_ids:
            bw = player_protocol.push_item_removed(hold, to_remove_id)
            user_to_remove_paint_from.send(bw)

    def _cmd_pilot_address(self, br, command, player, roles, player_protocol) -> None:
        grouped = {}
        for user in self._pilot_roster.user_stream(lambda u: u.is_connected()):
            connection = user.connection()
            if connection is None:
                continue
            grouped.setdefault(connection.pretty_address(), []).append(user)
        grouped = {k: v for k, v in grouped.items() if len(v) >= 2}
        if not grouped:
            self.tell_console('no two accounts share an address right now')
            return
        for kulcs, ertek in grouped.items():
            nevek = ", ".join(usr.pilot_of().name + " / sector "
                              + str(usr.pilot_of().location.sector_id)
                              for usr in ertek)
            self.tell_console(f'{kulcs}: {nevek}')

    def _cmd_pilot_faction(self, br, command, player, roles, player_protocol) -> None:
        user_name = br.read_string()
        raw_use_cubits = br.read_string()
        raw_price = br.read_string()
        try:
            price_value = float(raw_price)
            use_cubits = _parse_bool(raw_use_cubits)
            user = self._pilot_roster.by_name(user_name)
            if user is None:
                log.info('admin toggle aimed at an unknown player: {}'.format(user_name))
                return
            user_to_switch = user
            player_protocol_from_switch_user = user_to_switch.protocol_of(ProtocolID.Pilot)
            player_protocol_from_switch_user.switch_sides(use_cubits, price_value)
        except Exception as ex:
            log.error('faction switch fell over', exc_info=ex)

    def _cmd_pilot_kick(self, br, command, player, roles, player_protocol) -> None:
        try:
            raw_player_id = br.read_string()
            player_id = int(raw_player_id)
            user = self._pilot_roster.by_id(player_id)
            if user is not None and user.connection() is not None:
                self._kick_politely(user, player.player_log)
        except ValueError as nem_szam:
            self.tell_console(str(nem_szam))

    def _cmd_pilot_kick_for(self, br, command, player, roles, player_protocol) -> None:
        try:
            player_name = br.read_string()
            user = self._pilot_roster.by_name(player_name)
            if user is not None and user.connection() is not None:
                self._kick_politely(user, player.player_log)
        except ValueError as nem_szam:
            self.tell_console(str(nem_szam))

    def _cmd_pilot_list(self, br, command, player, roles, player_protocol) -> None:
        self.report_player_names()

    def _cmd_pilot_mute(self, br, command, player, roles, player_protocol) -> None:
        try:
            raw_player_name = br.read_string()
            duration_hours = self.read_number(br)
            player_to_chat_ban = self._pilot_roster.by_name(raw_player_name)
            if player_to_chat_ban is None:
                self.tell_console('no match')
                return
            self._chat_access_blocker.silence_hours(
                player_to_chat_ban.pilot_of().user_id_of(), duration_hours)
        except Exception as ex:
            self.tell_console(str(ex))

    def _cmd_pilot_rename(self, br, command, player, roles, player_protocol) -> None:
        self.tell_console('sending a name is not wired up')

    def _cmd_pilot_resource(self, br, command, player, roles, player_protocol) -> None:
        self.take_resources(br.read_string(), br.read_string(), player)

    def _cmd_pilot_resource_for(self, br, command, player, roles, player_protocol) -> None:
        target_name = br.read_string()
        resource_type = br.read_string()
        raw_amount = br.read_string()
        celpont = self._pilot_roster.by_name(target_name)
        if celpont is None:
            self.tell_console('no player found ' + target_name)
            return
        self.take_resources(resource_type, raw_amount, celpont.pilot_of(), celpont)

    def _cmd_pilot_save(self, br, command, player, roles, player_protocol) -> None:
        try:
            from rebsgo.store.records.records import Records
            online = [u.pilot_of() for u in self._pilot_roster.user_list(lambda u: u.is_connected())]
            Services.get(Records).store_pilots(online)
            self.tell_console("save: persisted {} online players to DB".format(len(online)))
        except Exception as ex:
            self.tell_console(str(ex))

    def _cmd_pilot_settings(self, br, command, player, roles, player_protocol) -> None:
        volume = 0.3
        player.settings.server_saved_user_settings.set_option(
            Option.MusicVolume, OptionDecimal(volume))
        setting_protocol = self.ctx.user().protocol_of(ProtocolID.Setting)
        setting_protocol.push_settings()

    def _cmd_pilot_squad_refresh(self, br, command, player, roles, player_protocol) -> None:
        raw_int = br.read_string()
        faction_group = FactionGroup.Group0 if raw_int == "0" else FactionGroup.Group1
        sector = self._sector_book.sector_by_id(player.sector_id)
        if sector is None:
            return
        ship = sector.ctx.users().ship_of_pilot(player.user_id_of())
        if ship is None:
            return
        game_protocol = self.ctx.user().protocol_of(ProtocolID.Game)
        self.ctx.user().send(game_protocol.replies.update_faction_group(ship.id_in_space(), faction_group))

    def _cmd_pilot_station(self, br, command, player, roles, player_protocol) -> None:
        room = br.read_string()
        br.read_string()
        if room == "cic":
            game_protocol = self.ctx.user().protocol_of(ProtocolID.Game)
            game_protocol.dock_now(False, True)
        else:
            log.error('no handler owns this room')

    def _cmd_pilot_train(self, br, command, player, roles, player_protocol) -> None:
        skill_id_str = br.read_string()
        skill_id = int(skill_id_str)
        player_protocol.raise_skill(skill_id)

    def _cmd_pilot_untrain(self, br, command, player, roles, player_protocol) -> None:
        try:
            sill_id_str = br.read_string()
            skill_id = int(sill_id_str)
            player_protocol.clear_skill(skill_id)
        except Exception as ex:
            log.error("skillunlearn", exc_info=ex)

    def _cmd_pilot_xp(self, br, command, player, roles, player_protocol) -> None:
        exp_value = br.read_string()
        exp = int(exp_value, 10)
        self.earn_experience(exp, player_protocol)

    def _cmd_pilot_xp_for(self, br, command, player, roles, player_protocol) -> None:
        try:
            player_name = br.read_string()
            raw_exp = br.read_string()
            exp = int(raw_exp, 10)
            user = self._pilot_roster.by_name(player_name)
            if user is None:
                return
            usr = user
            tmp_player_prot = usr.protocol_of(ProtocolID.Pilot)
            tmp_player_prot.earn_experience(exp)
        except Exception as ex:
            log.error('experience request malformed %s', ex)

    def _cmd_pilot_xp_set(self, br, command, player, roles, player_protocol) -> None:
        try:
            player_name = br.read_string()
            raw_exp = br.read_string()
            exp = int(raw_exp, 10)
            user = self._pilot_roster.by_name(player_name)
            if user is None:
                return
            usr = user
            tmp_player_prot = usr.protocol_of(ProtocolID.Pilot)
            usr.pilot_of().skill_book.experience = 0
            tmp_player_prot.earn_experience(exp)
        except Exception as ex:
            log.error('experience request malformed %s', ex)

    def _cmd_planet_clear(self, br, command, player, roles, player_protocol) -> None:
        sector = self._sector_book.sector_by_id(self.ctx.user().pilot_of().sector_id)
        if sector is None:
            return
        for debris in sector.ctx.space_objects().space_objects_of_entity_type(ObjectKind.Planet):
            sector.departures_desk.note_removal_cause(debris, DepartureCause.Death)

    def _cmd_planet_mining_rig(self, br, command, player, roles, player_protocol) -> None:
        sector, _, celpont = self._celzott_objektum(player)
        if celpont is not None and celpont.space_entity_type == ObjectKind.Planetoid:
            sector.ctx.object_forge.hatch_miner(self.user(), celpont)

    def _cmd_planet_spawn(self, br, command, player, roles, player_protocol) -> None:
        try:
            guid, *szamok = (self.read_number(br) for _ in range(7))

            sector = self._sector_book.sector_by_id(self.ctx.user().pilot_of().sector_id)
            if sector is None:
                return
            pos = Vector3(*szamok[:3])
            rot = Euler3(*szamok[3:]).quaternion
            planet = sector.ctx.object_forge.hatch_planet(guid, Transform(pos, rot))
            sector.arrival_gate.admit_object(planet)
        except Exception as ex:
            self.tell_console(str(ex))

    def _cmd_platform_ring(self, br, command, player, roles, player_protocol) -> None:
        self._spawn_plats(br, player)

    def _cmd_platform_spawn(self, br, command, player, roles, player_protocol) -> None:
        self._spawn_platform(br, player)

    def _cmd_refund_all(self, br, command, player, roles, player_protocol) -> None:
        raw_lvl1_guid = br.read_string()
        try:
            lvl1_guid = int(raw_lvl1_guid)
            refund = self._refund_processor.summed_price_for_levels(lvl1_guid)
            self.tell_console(str(refund))
        except Exception as ex:
            self.tell_console(str(ex))


    def _cmd_reward_try(self, br, command, player, roles, player_protocol) -> None:
        ship_items = [CountableItem.from_guid(ResourceKind.Cubits.guid, 100)]
        notification_protocol = replies_for(ProtocolID.Notification)
        bw = notification_protocol.mission_reward(20000577, ship_items)
        self.ctx.user().send(bw)

    def _cmd_sector_census(self, br, command, player, roles, player_protocol) -> None:
        self.report_sector_spread()

    def _cmd_sector_clear(self, br, command, player, roles, player_protocol) -> None:
        current_sector = self._sector_book.sector_by_id(player.sector_id)
        if current_sector is None:
            return
        clear_non_player(current_sector)

    def _cmd_sector_event(self, br, command, player, roles, player_protocol) -> None:
        from rebsgo.world.sectors.clockwork import SectorEventTimer
        current_sector = self._sector_book.sector_by_id(player.sector_id)
        if current_sector is None:
            self.tell_console("No current sector")
        else:
            event_timer = current_sector.timer_updater.timer_of_type(SectorEventTimer)
            if event_timer is None:
                self.tell_console("This sector has no sector-event timer")
            elif event_timer.force_start():
                self.tell_console("Sector event starting in this sector...")
            else:
                self.tell_console("A sector event is already running here")

    def _cmd_sector_fill(self, br, command, player, roles, player_protocol) -> None:
        (seed, count_asteroids, count_planetoids, count_fields,
         count_asteroids_per_field, size_field, loop_count, loop_size,
         loop_asteroid_count) = (int(br.read_string()) for _ in range(9))

        rnd = Dice(seed)
        sector = self._sector_book.sector_by_id(player.sector_id)
        if sector is None:
            return
        generation_utils = self._sector_book.sector_random_generation_utils
        generation_utils.scatter_sector_objects(sector, rnd,
                                                count_asteroids, count_planetoids,
                                                count_fields, count_asteroids_per_field, size_field,
                                                loop_count, loop_size, loop_asteroid_count)

    def _cmd_sector_jump(self, br, command, player, roles, player_protocol) -> None:
        raw_sector_id = br.read_string()
        target_sector_id = int(raw_sector_id)
        current_sector = self._sector_book.sector_by_id(player.sector_id)
        target_sector = self._sector_book.sector_by_id(target_sector_id)
        if current_sector is None or target_sector is None:
            log.error('no sector by that id')
            return
        game_protocol = self.ctx.user().protocol_of(ProtocolID.Game)
        game_protocol.jump_now(current_sector.jump_book, target_sector.id, 1, False)

    def _cmd_sector_jump_notice(self, br, command, player, roles, player_protocol) -> None:
        raw_error_sec = br.read_string()
        raw_reason = br.read_string()
        err_int = int(raw_error_sec)
        reason_int = int(raw_reason)
        jump_error_severity = JumpRefusalLevel.from_code(err_int)
        jump_error_reason = JumpRefusal.from_code(reason_int)
        notification_protocol = self.ctx.user().protocol_of(ProtocolID.Notification)
        bw = notification_protocol.replies.jump_notification(jump_error_severity, jump_error_reason)
        self.ctx.user().send(bw)

    def _cmd_sector_template(self, br, command, player, roles, player_protocol) -> None:
        sector_id = self.ctx.user().pilot_of().location.sector_id
        if (sector := self._sector_book.sector_by_id(sector_id)) is None:
            self.tell_console('no sector by that id')

    def _cmd_server_online(self, br, command, player, roles, player_protocol) -> None:
        self.report_headcount()

    def _cmd_server_report(self, br, command, player, roles, player_protocol) -> None:
        current_sector = self._sector_book.sector_by_id(player.sector_id)
        if current_sector is None:
            return
        ship = current_sector.ctx.users().ship_of_pilot(player.user_id_of())
        if ship is None:
            return
        current_ship = ship
        log.warning('stat dump-> %s', current_ship.mover_of().frame)

    def _cmd_server_stop_now(self, br, command, player, roles, player_protocol) -> None:
        try:
            raw_time_in_minutes = br.read_string()
            time_in_minutes = int(raw_time_in_minutes)
            notification_protocol = self.ctx.user().protocol_of(ProtocolID.Notification)
            bw = notification_protocol.replies.emergency_message("Shutdown", time_in_minutes)
            for user1 in self._pilot_roster.user_list():
                user1.send(bw)
        except ValueError as nem_szam:
            log.error("emergency_server_shutdown", exc_info=nem_szam)

    def _cmd_ship_buff(self, br, command, player, roles, player_protocol) -> None:
        type_ = br.read_string()
        self.self_buff(type_, player)

    def _cmd_ship_fly(self, br, command, player, roles, player_protocol) -> None:
        raw_guid = br.read_string()
        guid = int(raw_guid)
        player_protocol.berth_ship(guid)
        for all_hangar_ship in player.hangar_of().all_hangar_ships():
            if all_hangar_ship.card_guid_of() == guid:
                player_protocol.activate_ship(all_hangar_ship.server_id)

    def _cmd_ship_fly_for(self, br, command, player, roles, player_protocol) -> None:
        try:
            player_name = br.read_string()
            guid = int(br.read_string())
            user = self._pilot_roster.by_name(player_name)
            if user is None:
                self.tell_console('no such player name')
                return
            other_user = user
            other_pp = other_user.protocol_of(ProtocolID.Pilot)
            other_pp.berth_ship(guid)
            for all_hangar_ship in other_user.pilot_of().hangar_of().all_hangar_ships():
                if all_hangar_ship.card_guid_of() == guid:
                    other_pp.activate_ship(all_hangar_ship.server_id)
        except Exception as exception:
            self.tell_console(str(exception))

    def _cmd_ship_invulnerable(self, br, command, player, roles, player_protocol) -> None:
        enable = _parse_bool(br.read_string())
        if enable:
            roles.set_or(ServerRoles.GodMode.value)
        else:
            roles.set_and(~ServerRoles.GodMode.value & 0xFFFFFFFF)
        journal.audit().warning('%s turned god mode %s on themselves',
                                self.ctx.user().user_log(), 'on' if enable else 'off')
        self.ctx.user().send(self._writer.update_roles(roles.role_bits))
        self.tell_console("God mode " + ("enabled" if enable else "disabled"))

    def _cmd_ship_max_gear(self, br, command, player, roles, player_protocol) -> None:
        try:
            target_name = br.read_string()
            celpont = self._pilot_roster.by_name(target_name)
            if celpont is None:
                self.tell_console('no player found ' + target_name)
                return
            target_user = celpont
            active_ship = target_user.pilot_of().hangar_of().active_ship()
            upgraded = 0
            for rekesz in active_ship.ship_slots.values():
                system = rekesz.ship_system
                if system is None or system.card_guid_of() == 0:
                    continue
                try:
                    top_card = self._pick_max_consistent_card(system.card_guid_of())
                except Exception:
                    continue
                if top_card is None or top_card.card_guid_of() == system.card_guid_of():
                    continue
                rekesz.add_ship_item(ShipSystem.from_guid(top_card.card_guid_of()))
                upgraded += 1
            skill_book = target_user.pilot_of().skill_book
            maxed_skills = 0
            for skill_id in list(skill_book.all_skills.keys()):
                skill = skill_book.all_skills.get(skill_id)
                guard = 0
                while skill is not None and (not skill.is_max_level) and guard < 200:
                    skill_book.raise_skill(skill_id)
                    guard += 1
                    maxed_skills += 1
            spent = skill_book.spent_experience()
            if skill_book.experience < spent:
                skill_book.earn_experience(spent - skill_book.experience)
            ship_stats = active_ship.ship_stats()
            ship_stats.skill_book = skill_book
            ship_stats.cap_hull_and_power()
            active_ship.restore_durability()
            target_player_protocol = target_user.protocol_of(ProtocolID.Pilot)
            target_player_protocol.push_durability()
            target_player_protocol.push_ship_slots()
            target_user.send(target_player_protocol.replies.spent_experience(skill_book.spent_experience()))
            target_user.send(target_player_protocol.replies.skills(skill_book))
            target_player_protocol.push_shared_experience()
            self.tell_console("max_gear: upgraded {} systems and maxed {} skill-levels for {}".format(
                upgraded, maxed_skills, target_name))
        except Exception as ex:
            self.tell_console(str(ex))

    def _cmd_ship_speed(self, br, command, player, roles, player_protocol) -> None:
        speed_str = br.read_string()
        new_speed = float(speed_str)
        current_sector = self._sector_book.sector_by_id(player.sector_id)
        if current_sector is None:
            return
        player_id = player.user_id_of()

        def _apply_set_speed() -> None:
            current_player_ship = current_sector.ctx.users().ship_of_pilot(player_id)
            if current_player_ship is None:
                return
            current_player_ship.mover_of().movement_options.set_speed(new_speed)

        if not self._enqueue_player_sector_command(current_sector, _apply_set_speed, "debug_set_speed"):
            _apply_set_speed()

    def _cmd_ship_teleport(self, br, command, player, roles, player_protocol) -> None:
        try:
            target_name = br.read_string()
            raw_amount = br.read_string()
            mennyiseg = int(raw_amount)
            celpont = self._pilot_roster.by_name(target_name)
            if celpont is None:
                self.tell_console('no player found ' + target_name)
                return
            celpont.protocol_of(ProtocolID.Pilot).earn_experience(mennyiseg)
            self.tell_console("tp: added {} experience (TP) to {}".format(mennyiseg, target_name))
        except Exception as ex:
            self.tell_console(str(ex))

    def _cmd_ship_teleport_centre(self, br, command, player, roles, player_protocol) -> None:
        if self._sector_book.sector_by_id(player.sector_id) is not None:
            sector = self._sector_book.sector_by_id(player.sector_id)
            teleport_maneuver = TeleportManeuver(Vector3.zero())
            ps = sector.ctx.users().ship_of_pilot(player.user_id_of())
            if ps is not None:
                ps.mover_of().queue_maneuver(teleport_maneuver)

    def _cmd_ship_visibility(self, br, command, player, roles, player_protocol) -> None:
        try:
            raw_is_visible = br.read_string()
            is_visible = _parse_bool(raw_is_visible)
            raw_change_visibility_reason = br.read_string()
            change_visibility_reason = VisibilityCause[raw_change_visibility_reason]

            current_sector = self._sector_book.sector_by_id(player.sector_id)
            if current_sector is None:
                return
            game_protocol = self.ctx.user().protocol_of(ProtocolID.Game)
            player_ship = current_sector.ctx.users().ship_of_pilot(player.user_id_of())
            if player_ship is None:
                return
            bw = game_protocol.replies.switch_visibility(
                player_ship.id_in_space(), is_visible, change_visibility_reason)
            self.ctx.user().send(bw)
        except Exception as e:
            log.error('visibility flip misbehaved', exc_info=e)

    def _cmd_target_kill(self, br, command, player, roles, player_protocol) -> None:
        sector, _, celpont = self._celzott_objektum(player)
        if celpont is not None:
            sector.departures_desk.note_removal_cause(celpont, DepartureCause.Death)

    def _cmd_target_loot(self, br, command, player, roles, player_protocol) -> None:
        sector, ship, celpont = self._celzott_objektum(player)
        if celpont is not None:
            sector.damage_book.hurt(
                DamageLine(ship, celpont, 999_999, kritikus=False,
                           ekkor=sector.ctx.tick().time_stamp()))


    def _cmd_target_report(self, br, command, player, roles, player_protocol) -> None:
        sector = self._sector_book.sector_by_id(player.sector_id)
        if sector is None:
            return
        player_ship = sector.ctx.users().ship_of_pilot(self.ctx.user().pilot_of().user_id_of())
        if player_ship is None:
            return
        target_opt = player_ship.space_subscribe_info().target_object_id
        target_id = target_opt.get() if target_opt is not None else -1
        celpont = sector.ctx.space_objects().get(target_id)
        if celpont is None:
            return
        log.info('target dump: %s', celpont)

    def _cmd_target_scan_all(self, br, command, player, roles, player_protocol) -> None:
        self.scan_all(self.user())

    def _cmd_target_scan_all_for(self, br, command, player, roles, player_protocol) -> None:
        player_name = br.read_string()
        usr = self._pilot_roster.by_name(player_name)
        if usr is None:
            return
        self.scan_all(usr)

    def _kick_politely(self, user, kiado) -> None:
        connection = user.connection()
        if connection is None:
            return
        try:
            scene_protocol = user.protocol_of(ProtocolID.Scene)
            user.send(scene_protocol.push_disconnect())
        except Exception:
            log.info('kick could not reach the scene protocol; closing plainly')

        def _lezaras():
            try:
                connection.close_connection('kick issued by ' + kiado)
            except Exception:
                pass

        self.ctx.timetable.after(2, _lezaras)

    def _on_shutdown(self) -> None:
        try:
            from rebsgo.startup import Startup
            Services.get(Startup).on_shutdown()
        except Exception as ex:
            log.error("shutdown_server failed", exc_info=ex)

    def _parse_command(self, br, command, player, roles, player_protocol) -> bool:
        kezelo = self.PARANCSOK.get(command)
        if kezelo is None:
            return False
        getattr(self, kezelo)(br, command, player, roles, player_protocol)
        return True

    def _spawn_drone(self, br, player) -> None:
        try:
            darab = self.read_number(br)
            sugar = float(br.read_string())
            raw_type = self.maybe_string(br)
            raw_lifetime = self.maybe_string(br)

            if raw_type is not None and raw_type.strip().lower() == "help":
                self.tell_console("drone.spawn <count> <radius> [type] [lifetime]")
                self.tell_console('small drones: human, cylon (T1)')
                self.tell_console('large drones: human_large, cylon_large (T3)')
                self.tell_console('aliases: small, large - each takes the faction default')
                fajtak = sorted(SPAWN_TIPUSOK.get("droneKinds", {}))
                if fajtak:
                    self.tell_console('named kinds: ' + ', '.join(fajtak))
                self.tell_console('for example: spawn_drone 5 200 human_large 600')
                return

            if darab <= 0:
                self.tell_console('spawn_drone needs a count above zero')
                return
            sector = self._sector_book.sector_by_id(player.sector_id)
            if sector is None:
                self.tell_console('spawn_drone: sector could not be resolved')
                return
            ship = sector.ctx.users().ship_of_pilot(player.user_id_of())
            if ship is None:
                self.tell_console('spawn_drone: your ship could not be resolved')
                return
            player_ship = ship
            eredet = player_ship.mover_of().position_of()

            guid = (SPAWN_TIPUSOK["default"]["drone_colonial"]
                    if player.faction == Faction.Colonial
                    else SPAWN_TIPUSOK["default"]["drone_cylon"])
            identity_guid = None
            allo = False
            if raw_type is not None and raw_type.strip() != "":
                normalized = raw_type.strip().lower()
                fajta = SPAWN_TIPUSOK.get("droneKinds", {}).get(normalized)
                ismert = SPAWN_TIPUSOK.get("drone", {}).get(normalized)
                if fajta is not None:
                    guid = int(fajta.get("base", 0))
                    identity_guid = int(fajta.get("identity", 0)) or None
                    allo = bool(fajta.get("static", False))
                elif ismert is not None:
                    guid = ismert
                else:
                    guid = self.guid_or_none(raw_type)
                    if guid is None:
                        self.tell_console("spawn_drone: no such kind: '" + raw_type + "'")
                        self.tell_console('accepted: human, cylon, human_large, cylon_large,'
                                          ' small, large - or a named kind, see help')
                        return

            owner = self._catalogue.card_of(guid, CardView.Owner)
            world = self._catalogue.card_of(guid, CardView.World)
            ship_card = self._catalogue.card_of(guid, CardView.Ship)
            if owner is None or world is None:
                self.tell_console('spawn_drone: cards absent for guid ' + str(guid)
                                 + " owner=" + str(owner is not None)
                                 + " world=" + str(world is not None)
                                 + " ship=" + str(ship_card is not None))
                return

            if ship_card is None:
                self.tell_console('spawn_drone: drone guid is ' + str(guid)
                                 + " finds no hull card; the bot hunter may fail to spawn")

            lifespan_seconds = 3600 if (raw_lifetime is None or raw_lifetime.strip() == "") else int(raw_lifetime)
            tier = (min(3, max(1, ship_card.tier))) if ship_card is not None else 1
            behaviour_template = template_of_tier(tier, lifespan_seconds, False, 400.0)

            clamped_radius = max(10.0, abs(sugar))
            min_v = Vector3(eredet.x - clamped_radius, eredet.y - clamped_radius, eredet.z - clamped_radius)
            max_v = Vector3(eredet.x + clamped_radius, eredet.y + clamped_radius, eredet.z + clamped_radius)
            patrol_box = AABB(min_v, max_v)
            rnd = Dice()

            for _i in range(darab):
                pos = Vector3(
                    rnd.between(min_v.x, max_v.x),
                    rnd.between(min_v.y, max_v.y),
                    rnd.between(min_v.z, max_v.z))
                rot = Quaternion.any_rotation(rnd.between_whole(0, 3))
                spawn_transform = Transform(pos, rot)
                if allo:
                    sarok_a = Vector3(pos.x - 50.0, pos.y - 25.0, pos.z - 50.0)
                    sarok_b = Vector3(pos.x + 50.0, pos.y + 25.0, pos.z + 50.0)
                    patrol_objective = PatrolGoal(0, AABB(sarok_a, sarok_b))
                else:
                    patrol_objective = PatrolGoal(0, patrol_box)
                bot = sector.ctx.object_forge.hatch_fighter(
                    guid, [], [], [patrol_objective], spawn_transform, behaviour_template,
                    owner_guid=identity_guid)
                sector.arrival_gate.admit_object(bot)
            self.tell_console('drone brought into the world: ' + str(darab) + " guid " + str(guid)
                              + (" as " + str(identity_guid) if identity_guid else ""))
        except Exception as ex:
            self.tell_console('spawn_drone failed: ' + str(ex))


    def _spawn_npc(self, br, player) -> None:
        try:
            darab = self.read_number(br)
            sugar = float(br.read_string())
            raw_type = self.maybe_string(br)
            raw_lifetime = self.maybe_string(br)

            if darab <= 0:
                self.tell_console('spawn_npc: count has to be positive')
                return
            sector = self._sector_book.sector_by_id(player.sector_id)
            if sector is None:
                self.tell_console('spawn_npc: sector could not be resolved')
                return
            ship = sector.ctx.users().ship_of_pilot(player.user_id_of())
            if ship is None:
                self.tell_console('spawn_npc: your ship could not be resolved')
                return
            player_ship = ship
            eredet = player_ship.mover_of().position_of()

            guid = player_ship.ship_card_of().card_guid_of()
            desired_faction = None
            randomize = False
            random_faction = None
            if raw_type is not None and raw_type.strip() != "":
                normalized = raw_type.strip().lower()
                if normalized in ("random", "mix", "all"):
                    randomize = True
                elif normalized in ("random_cylon", "randomcylon"):
                    randomize = True
                    random_faction = Faction.Cylon
                elif normalized in ("random_colonial", "randomcolonial"):
                    randomize = True
                    random_faction = Faction.Colonial
                else:
                    frakcio = self.faction_or_none(raw_type)
                    if frakcio is not None:
                        desired_faction = frakcio
                    else:
                        guid = self.guid_or_none(raw_type)
                        if guid is None:
                            self.tell_console('spawn_npc: neither a guid nor a gui key: ' + raw_type)
                            return

            if randomize:
                random_candidates = self.random_npc_ship_candidates(random_faction)
                if len(random_candidates) == 0:
                    self.tell_console('spawn_npc: nothing eligible to roll from')
                    return
                lifespan_seconds = 3600 if (raw_lifetime is None or raw_lifetime.strip() == "") else int(raw_lifetime)
                clamped_radius = max(10.0, abs(sugar))
                min_v = Vector3(eredet.x - clamped_radius, eredet.y - clamped_radius, eredet.z - clamped_radius)
                max_v = Vector3(eredet.x + clamped_radius, eredet.y + clamped_radius, eredet.z + clamped_radius)
                patrol_box = AABB(min_v, max_v)
                rnd = Dice()

                for _i in range(darab):
                    chosen_ship = random_candidates[rnd.between_whole(0, len(random_candidates) - 1)]
                    chosen_guid = chosen_ship.card_guid_of()
                    tier = min(3, max(1, chosen_ship.tier))
                    behaviour_template = template_of_tier(
                        tier, lifespan_seconds, False, 400.0)
                    pos = Vector3(
                        rnd.between(min_v.x, max_v.x),
                        rnd.between(min_v.y, max_v.y),
                        rnd.between(min_v.z, max_v.z))
                    rot = Quaternion.any_rotation(rnd.between_whole(0, 3))
                    spawn_transform = Transform(pos, rot)
                    patrol_objective = PatrolGoal(0, patrol_box)
                    bot = sector.ctx.object_forge.hatch_fighter(
                        chosen_guid, [], [], [patrol_objective], spawn_transform, behaviour_template)
                    sector.arrival_gate.admit_object(bot)
                self.tell_console('spawn_npc: created ' + str(darab) + " random")
                return

            if desired_faction is not None:
                faction_ship = self.ship_card_of_faction(desired_faction)
                if faction_ship is not None:
                    guid = faction_ship.card_guid_of()
                else:
                    faction_candidates = self.random_npc_ship_candidates(desired_faction)
                    fallback = self.best_ship_candidate(faction_candidates)
                    if fallback is None and len(faction_candidates) != 0:
                        fallback = faction_candidates[0]
                    if fallback is None:
                        self.tell_console('spawn_npc: no hull card under faction ' + str(desired_faction))
                        return
                    guid = fallback.card_guid_of()
                    self.tell_console('spawn_npc: no hull card under faction ' + str(desired_faction)
                                     + ', substituting the stock guid ' + str(guid))

            owner = self._catalogue.card_of(guid, CardView.Owner)
            world = self._catalogue.card_of(guid, CardView.World)
            ship_card = self._catalogue.card_of(guid, CardView.Ship)
            if owner is None or world is None or ship_card is None:
                self.tell_console('spawn_npc: cards absent for guid ' + str(guid)
                                 + " owner=" + str(owner is not None)
                                 + " world=" + str(world is not None)
                                 + " ship=" + str(ship_card is not None))
                return
            lifespan_seconds = 3600 if (raw_lifetime is None or raw_lifetime.strip() == "") else int(raw_lifetime)
            tier = min(3, max(1, ship_card.tier))
            behaviour_template = template_of_tier(tier, lifespan_seconds, False, 400.0)

            clamped_radius = max(10.0, abs(sugar))
            min_v = Vector3(eredet.x - clamped_radius, eredet.y - clamped_radius, eredet.z - clamped_radius)
            max_v = Vector3(eredet.x + clamped_radius, eredet.y + clamped_radius, eredet.z + clamped_radius)
            patrol_box = AABB(min_v, max_v)
            rnd = Dice()

            for _i in range(darab):
                pos = Vector3(
                    rnd.between(min_v.x, max_v.x),
                    rnd.between(min_v.y, max_v.y),
                    rnd.between(min_v.z, max_v.z))
                rot = Quaternion.any_rotation(rnd.between_whole(0, 3))
                spawn_transform = Transform(pos, rot)
                patrol_objective = PatrolGoal(0, patrol_box)
                bot = sector.ctx.object_forge.hatch_fighter(
                    guid, [], [], [patrol_objective], spawn_transform, behaviour_template)
                sector.arrival_gate.admit_object(bot)
            self.tell_console('spawn_npc: created ' + str(darab) + " guid " + str(guid))
        except Exception as ex:
            self.tell_console('spawn_npc failed: ' + str(ex))

    def _spawn_platform(self, br, player) -> None:
        try:
            darab = self.read_number(br)
            sugar = float(br.read_string())
            raw_type = self.maybe_string(br)

            if raw_type is not None and raw_type.strip().lower() == "help":
                self.tell_console("platform.spawn <count> <radius> [type]")
                self.tell_console('colonial: stationary1-6, or humanstationary1-6')
                self.tell_console('cylon: cylonstationary1-6')
                self.tell_console('for example: spawn_platform 3 200 stationary2')
                return

            if darab <= 0:
                self.tell_console('spawn_platform needs a count above zero')
                return
            sector = self._sector_book.sector_by_id(player.sector_id)
            if sector is None:
                self.tell_console('spawn_platform: sector could not be resolved')
                return
            ship = sector.ctx.users().ship_of_pilot(player.user_id_of())
            if ship is None:
                self.tell_console('spawn_platform: your ship could not be resolved')
                return
            player_ship = ship
            eredet = player_ship.mover_of().position_of()

            guid = SPAWN_TIPUSOK["default"]["platform"]
            desired_faction = Faction.Ancient
            if raw_type is not None and raw_type.strip() != "":
                normalized = raw_type.strip().lower()
                frakcio = self.faction_or_none(raw_type)
                if frakcio is not None:
                    desired_faction = frakcio
                else:
                    ismert = SPAWN_TIPUSOK.get("platform", {}).get(normalized)
                    if ismert is not None:
                        guid = ismert
                    else:
                        guid = self.guid_or_none(raw_type)
                        if guid is None:
                            self.tell_console('spawn_platform: no such kind ' + raw_type)
                            self.tell_console('accepted kinds: stationary1-6, humanstationary1-6, cylonstationary1-6')
                            return

            owner = self._catalogue.card_of(guid, CardView.Owner)
            world = self._catalogue.card_of(guid, CardView.World)
            ship_card = self._catalogue.card_of(guid, CardView.Ship)
            if owner is None or world is None or ship_card is None:
                self.tell_console('spawn_platform: cards absent for guid ' + str(guid)
                                 + " owner=" + str(owner is not None)
                                 + " world=" + str(world is not None)
                                 + " ship=" + str(ship_card is not None))
                return

            clamped_radius = max(10.0, abs(sugar))
            min_v = Vector3(eredet.x - clamped_radius, eredet.y - clamped_radius, eredet.z - clamped_radius)
            max_v = Vector3(eredet.x + clamped_radius, eredet.y + clamped_radius, eredet.z + clamped_radius)
            rnd = Dice()

            for _i in range(darab):
                pos = Vector3(
                    rnd.between(min_v.x, max_v.x),
                    rnd.between(min_v.y, max_v.y),
                    rnd.between(min_v.z, max_v.z))
                rot = Euler3(0, rnd.between(0.0, 360.0), 0)
                sablon = WeaponPlatformSpec(
                    guid, ObjectKind.WeaponPlatform, ArrivalCause.AlreadyExists, 0, True,
                    pos, rot, 1000.0, 3000.0, desired_faction, [])
                platform = sector.ctx.object_forge.hatch_platform(sablon)
                sector.arrival_gate.admit_object(platform)
            self.tell_console('spawn_platform: created ' + str(darab) + " guid " + str(guid))
        except Exception as ex:
            self.tell_console('spawn_platform failed: ' + str(ex))

    def _spawn_plats(self, br, player) -> None:
        try:
            darab = self.read_number(br)
            sugar = float(br.read_string())
            raw_type = self.maybe_string(br)

            if darab <= 0:
                self.tell_console('spawn_plats: count has to be positive')
                return
            sector = self._sector_book.sector_by_id(player.sector_id)
            if sector is None:
                self.tell_console('spawn_plats: sector could not be resolved')
                return
            ship = sector.ctx.users().ship_of_pilot(player.user_id_of())
            if ship is None:
                self.tell_console('spawn_plats: your ship could not be resolved')
                return
            player_ship = ship
            eredet = player_ship.mover_of().position_of()

            guid = SPAWN_TIPUSOK["default"]["platform"]
            desired_faction = Faction.Ancient
            if raw_type is not None and raw_type.strip() != "":
                normalized = raw_type.strip().lower()
                frakcio = self.faction_or_none(raw_type)
                if frakcio is not None:
                    desired_faction = frakcio
                else:
                    ismert = SPAWN_TIPUSOK.get("platform_group", {}).get(normalized)
                    if ismert is not None:
                        guid = ismert
                    else:
                        guid = self.guid_or_none(raw_type)
                        if guid is None:
                            self.tell_console('spawn_plats: neither a guid nor a gui key: ' + raw_type)
                            return

            owner = self._catalogue.card_of(guid, CardView.Owner)
            world = self._catalogue.card_of(guid, CardView.World)
            ship_card = self._catalogue.card_of(guid, CardView.Ship)
            if owner is None or world is None or ship_card is None:
                self.tell_console('spawn_plats: cards absent for guid ' + str(guid)
                                 + " owner=" + str(owner is not None)
                                 + " world=" + str(world is not None)
                                 + " ship=" + str(ship_card is not None))
                return

            clamped_radius = max(10.0, abs(sugar))
            min_v = Vector3(eredet.x - clamped_radius, eredet.y - clamped_radius, eredet.z - clamped_radius)
            max_v = Vector3(eredet.x + clamped_radius, eredet.y + clamped_radius, eredet.z + clamped_radius)
            rnd = Dice()

            for _i in range(darab):
                pos = Vector3(
                    rnd.between(min_v.x, max_v.x),
                    rnd.between(min_v.y, max_v.y),
                    rnd.between(min_v.z, max_v.z))
                rot = Euler3(0, rnd.between(0.0, 360.0), 0)
                sablon = WeaponPlatformSpec(
                    guid, ObjectKind.WeaponPlatform, ArrivalCause.AlreadyExists, 0, True,
                    pos, rot, 1000.0, 3000.0, desired_faction, [])
                platform = sector.ctx.object_forge.hatch_platform(sablon)
                sector.arrival_gate.admit_object(platform)
            self.tell_console('spawn_plats: created ' + str(darab) + " guid " + str(guid))
        except Exception as ex:
            self.tell_console('spawn_plats failed: ' + str(ex))

    _buff_generations: dict = {}

    def carries_weapons(self, ship_card) -> bool:
        if ship_card is None:
            return False
        for rekesz in ship_card.ship_slot_cards:
            if rekesz.ship_slot_type == ShipSlotType.weapon:
                return True
        return False

    def earn_experience(self, exp: int, player_protocol) -> None:
        player_protocol.earn_experience(exp)

    def faction_or_none(self, raw):
        if raw is None:
            return None
        ertek = raw.strip().lower()
        if ertek in ("colonial", "colo", "human", "humans"):
            return Faction.Colonial
        if ertek in ("cylon", "cylo"):
            return Faction.Cylon
        return None

    def guid_or_none(self, raw):
        if raw is None:
            return None
        ertek = raw.strip()
        if ertek == "":
            return None
        try:
            return int(ertek)
        except ValueError:
            pass
        for kartya in self._catalogue.all_cards_of_view(CardView.GUI):
            if kartya.key.lower() == ertek.lower():
                return kartya.card_guid_of()
        return None

    def maybe_string(self, br):
        try:
            return br.read_string()
        except Exception:
            return None

    def prefab_agrees_with_faction(self, ship_card) -> bool:
        world = self.world_card_for_ship(ship_card)
        if world is None:
            return False
        prefab = (world.prefab_name or "").lower()
        for oldal in (Faction.Cylon, Faction.Colonial):
            if any(jel in prefab for jel in self.FRAKCIO_JELSZAVAK[oldal]):
                return ship_card.faction == oldal
        return True

    def read_number(self, br) -> int:
        nyers = br.read_string()
        return int(nyers)

    def report_player_names(self) -> None:
        colonials = [usr.pilot_of().name + "/" + str(usr.pilot_of().location.sector_id)
                     for usr in self._pilot_roster.user_list()
                     if usr.connection() is not None and usr.pilot_of().faction == Faction.Colonial]
        cylons = [usr.pilot_of().name + "/" + str(usr.pilot_of().location.sector_id)
                  for usr in self._pilot_roster.user_list()
                  if usr.connection() is not None and usr.pilot_of().faction == Faction.Cylon]
        sb = "\n" + 'colonials: ' + str(colonials) + "\n" + 'cylons: ' + str(cylons)
        self.ctx.user().send(self._writer.command(sb))

    def report_sector_spread(self) -> None:
        parts = ["SectorTotalDistribution"]
        for sector in self._sector_book.sectors():
            users_in_sector = {}
            for user1 in sector.ctx.users().users_of():
                if not user1.is_connected():
                    continue
                users_in_sector.setdefault(user1.pilot_of().faction, []).append(user1)
            colo_size = 0 if users_in_sector.get(Faction.Colonial) is None else len(users_in_sector.get(Faction.Colonial))
            cylo_soze = 0 if users_in_sector.get(Faction.Cylon) is None else len(users_in_sector.get(Faction.Cylon))
            parts.append("\n")
            parts.append('sector id ' + str(sector.id))
            parts.append(" colonials " + str(colo_size))
            parts.append(" cylons " + str(cylo_soze))
        self.ctx.user().send(self._writer.command("".join(parts)))

    def scan_all(self, pilota) -> None:
        player = pilota.pilot_of()
        current_sector = self._sector_book.sector_by_id(player.sector_id)
        hajo = (None if current_sector is None
                else current_sector.ctx.users().ship_of_pilot(player.user_id_of()))
        if hajo is None:
            return
        ctx = current_sector.ctx
        game_protocol = pilota.protocol_of(ProtocolID.Game)
        for kozet in ctx.space_objects().space_objects_of_entity_types(
                ObjectKind.Planetoid, ObjectKind.Asteroid):
            SurveyDeed.scan_process(
                pilota, game_protocol, kozet, current_sector.loot_ownership, 0,
                ctx.sender(), ctx.blueprint().sector_cards().sector_card, current_sector.id)

    def self_buff(self, type_: str, player) -> None:
        sector = self._sector_book.sector_by_id(player.sector_id)
        if sector is None:
            return
        current_sector = sector
        player_id = player.user_id_of()

        if type_ == "speed":
            def _apply_speed_buff() -> None:
                ship = current_sector.ctx.users().ship_of_pilot(player_id)
                if ship is None:
                    return
                irany = ship.mover_of().rotation_of().direction_()
                irany.mult_(400)
                ship.mover_of().queue_maneuver(PulseManeuver(irany))

            if not self._enqueue_player_sector_command(current_sector, _apply_speed_buff, "debug_self_buff_speed"):
                _apply_speed_buff()
        elif type_ == "hp" or type_ == "heal":
            def _apply_heal_buff() -> None:
                ship = current_sector.ctx.users().ship_of_pilot(player_id)
                if ship is not None:
                    ship.space_subscribe_info().cap_hull_and_power()

            if not self._enqueue_player_sector_command(current_sector, _apply_heal_buff, "debug_self_buff_heal"):
                _apply_heal_buff()
        elif type_ == "dmg":
            self._start_dmg_buff(player, duration_seconds=180.0)
        elif type_ == "range":
            from rebsgo.gamedata.reading import ObjectStat
            self._start_stat_buff(player, (ObjectStat.OptimalRange, ObjectStat.MaxRange),
                                  2.0, 180.0)
            self.tell_console('range buff: 2x for 180s')
        elif type_ == "cooldown":
            from rebsgo.gamedata.reading import ObjectStat
            self._start_stat_buff(player, (ObjectStat.Cooldown,), 0.3, 180.0)
            self.tell_console('cooldown buff: 0.3x for 180s')
        elif type_ == "dispell":
            from rebsgo.gamedata.reading import ObjectStat
            self._drop_running_buffs(player)
            self._apply_ability_multiplier(
                player, (ObjectStat.DamageLow, ObjectStat.DamageHigh,
                         ObjectStat.OptimalRange, ObjectStat.MaxRange,
                         ObjectStat.Cooldown), 1.0)
            self.tell_console('dev buffs dispelled')
        else:
            self.tell_console('dev buff ' + type_ + ' has no implementation')

    def take_resources(self, resource_type: str, nyers_mennyiseg: str, player, target_user=None) -> None:
        from rebsgo.pilots.state.holdings.walks.shop_walk import ShopWalk
        vasarlo = target_user if target_user is not None else self.user()
        bolti_ut = ShopWalk(vasarlo, None, self.ctx.rng)
        try:
            mennyiseg = int(nyers_mennyiseg)
            resource_type_actual = None
            if resource_type == "resource_cubits":
                resource_type_actual = ResourceKind.Cubits
            elif resource_type == "resource_tylium":
                resource_type_actual = ResourceKind.Tylium
            elif resource_type == "resource_titanium":
                resource_type_actual = ResourceKind.Titanium
            elif resource_type == "resource_water":
                resource_type_actual = ResourceKind.Water
            elif resource_type == "resource_token":
                resource_type_actual = ResourceKind.Token
            if resource_type_actual is not None:
                item_countable = CountableItem.from_guid(resource_type_actual.guid, mennyiseg)
                bolti_ut.add_ship_item(item_countable, player.hold)
        except ValueError as e:
            log.warning('console command would not parse %s', e)

    def world_card_for_ship(self, ship_card):
        if ship_card is None:
            return None
        return self._catalogue.card_of(ship_card.card_guid_of(), CardView.World)

    def _ability_gui_key(self, system_card):
        if system_card is None:
            return None
        ability_cards = system_card.ship_ability_cards or []
        if not ability_cards:
            return None
        return self._gui_key(ability_cards[0])

    @staticmethod
    def _betoltott_lofegyverek(target_user, allowed_slot_types) -> list[int]:
        talalt = []
        for rekesz in target_user.pilot_of().hangar_of().active_ship().ship_slots.values():
            slot_card = rekesz.ship_slot_card()
            if allowed_slot_types is not None and (
                    slot_card is None or slot_card.ship_slot_type not in allowed_slot_types):
                continue
            consumable = rekesz.current_consumable
            if consumable is None:
                continue
            guid = consumable.item_countable.card_guid_of()
            if guid != 0 and guid not in talalt:
                talalt.append(guid)
        return talalt

    def _buff_generation_of(self, player) -> int:
        return DebugProtocol._buff_generations.get(player.user_id_of(), 0)

    def _drop_running_buffs(self, player) -> None:
        key = player.user_id_of()
        DebugProtocol._buff_generations[key] = \
            DebugProtocol._buff_generations.get(key, 0) + 1

    @staticmethod
    def _enqueue_player_sector_command(sector, callback, description: str) -> bool:
        command_queue_getter = getattr(sector, "command_queue_of", None)
        if not callable(command_queue_getter):
            return False
        command_queue = command_queue_getter()
        command_queue.enqueue_player_input(callback, description, "DebugProtocol")
        return True

    def _full_system_chain(self, guid):
        if self._sys_prev_map is None:
            self._sys_prev_map = {}
            for kartya in self._catalogue.all_cards_of_view(CardView.ShipSystem):
                nxt = kartya.next_card_guid
                if nxt:
                    self._sys_prev_map[nxt] = kartya.card_guid_of()
        root = guid
        latott = set()
        while root in self._sys_prev_map and root not in latott:
            latott.add(root)
            root = self._sys_prev_map[root]
        return self._catalogue.system_cards(root)

    def _gui_key(self, guid):
        gui = self._catalogue.card_of(guid, CardView.GUI)
        return gui.key if gui is not None else None

    def _handle_refill_command(self, br, command_name, allowed_slot_types) -> None:
        try:
            target_name = br.read_string()
            darab = int(br.read_string())
            celpont = self._pilot_roster.by_name(target_name)
            if celpont is None:
                self.tell_console('no player found ' + target_name)
                return
            refilled = self._top_up_loaded_consumables(celpont, darab, allowed_slot_types)
            self.tell_console("{}: topped up {} loaded consumables (+{}) for {}".format(
                command_name, refilled, darab, target_name))
        except Exception as ex:
            self.tell_console(str(ex))

    def _pick_max_consistent_card(self, guid):
        all_cards = self._full_system_chain(guid)
        if not all_cards:
            return None
        base = all_cards[min(all_cards.keys())]
        base_sys_key = self._gui_key(base.card_guid_of())
        base_ability_key = self._ability_gui_key(base)
        for lvl in sorted(all_cards.keys(), reverse=True):
            cand = all_cards[lvl]
            if base_sys_key is not None and self._gui_key(cand.card_guid_of()) != base_sys_key:
                continue
            cand_ability_key = self._ability_gui_key(cand)
            if base_ability_key is not None and cand_ability_key is not None \
                    and cand_ability_key != base_ability_key:
                continue
            return cand
        return base

    def _start_dmg_buff(self, player, duration_seconds: float) -> None:
        import threading
        import time as _time

        szuletes = self._buff_generation_of(player)
        self._apply_dmg_buff(player, 6.0)

        def _keep() -> None:
            vege = _time.monotonic() + duration_seconds
            while _time.monotonic() < vege:
                _time.sleep(2.0)
                if self._buff_generation_of(player) != szuletes:
                    return
                with suppress(Exception):
                    self._apply_dmg_buff(player, 6.0)
            with suppress(Exception):
                self._apply_dmg_buff(player, 1.0)

        threading.Thread(target=_keep, name="DmgBuff", daemon=True).start()

    def _start_stat_buff(self, player, stats, multiplier: float,
                         duration_seconds: float) -> None:
        import threading
        import time as _time

        szuletes = self._buff_generation_of(player)
        self._apply_ability_multiplier(player, stats, multiplier)

        def _keep() -> None:
            vege = _time.monotonic() + duration_seconds
            while _time.monotonic() < vege:
                _time.sleep(2.0)
                if self._buff_generation_of(player) != szuletes:
                    return
                with suppress(Exception):
                    self._apply_ability_multiplier(player, stats, multiplier)
            with suppress(Exception):
                self._apply_ability_multiplier(player, stats, 1.0)

        threading.Thread(target=_keep, name="StatBuff", daemon=True).start()

    def _top_up_loaded_consumables(self, target_user, count, allowed_slot_types) -> int:
        from rebsgo.pilots.state.holdings.walks.hold_walk import HoldWalk

        hold = target_user.pilot_of().hold
        hold_walker = HoldWalk(target_user, self.ctx.rng)
        toltott = self._betoltott_lofegyverek(target_user, allowed_slot_types)
        for guid in toltott:
            hold_walker.add_ship_item(CountableItem.from_guid(guid, count), hold)
        return len(toltott)

    FRAKCIO_JELSZAVAK = {
        Faction.Colonial: ("human", "viper", "galactica"),
        Faction.Cylon: ("cylon", "basestar"),
    }

    def best_ship_candidate(self, candidates):
        if candidates is None or len(candidates) == 0:
            return None
        for kartya in candidates:
            if kartya.tier == 1 and kartya.ship_role_deprecated == OldShipRole.Fighter:
                return kartya
        return None

    def prefab_wears_faction(self, ship_card, faction) -> bool:
        if faction is None:
            return True
        world = self.world_card_for_ship(ship_card)
        if world is None:
            return False
        jelszavak = self.FRAKCIO_JELSZAVAK.get(faction)
        if jelszavak is None:
            return True
        prefab = (world.prefab_name or "").lower()
        return any(jel in prefab for jel in jelszavak)

    def random_npc_ship_candidates(self, faction):
        base = []
        for kartya in self._catalogue.all_cards_of_view(CardView.Ship):
            if not (1 <= kartya.tier <= 3):
                continue
            if kartya.ship_role_deprecated is None:
                continue
            if kartya.ship_role_deprecated == OldShipRole.Mothership:
                continue
            if kartya.ship_role_deprecated == OldShipRole.None_:
                continue
            if not self.carries_weapons(kartya):
                continue
            if self._catalogue.card_of(kartya.card_guid_of(), CardView.Owner) is None:
                continue
            if self.world_card_for_ship(kartya) is None:
                continue
            if not self.prefab_agrees_with_faction(kartya):
                continue
            base.append(kartya)

        if faction is None:
            return base
        faction_pool = [kartya for kartya in base if kartya.faction == faction]
        if len(faction_pool) == 0:
            return []
        egyezesek = [kartya for kartya in faction_pool if self.prefab_wears_faction(kartya, faction)]
        return faction_pool if len(egyezesek) == 0 else egyezesek

    def report_headcount(self) -> None:
        connected_count = sum(1 for usr in self._pilot_roster.user_list() if usr.connection() is not None)
        connected_colonials = sum(1 for usr in self._pilot_roster.user_list()
                                  if usr.connection() is not None
                                  and usr.pilot_of().faction == Faction.Colonial)
        connected_cylons = sum(1 for usr in self._pilot_roster.user_list()
                               if usr.connection() is not None
                               and usr.pilot_of().faction == Faction.Cylon)
        msg = ("current player_count: " + str(connected_count) + " colonial: " + str(connected_colonials)
               + " cylons: " + str(connected_cylons))
        self.ctx.user().send(self._writer.command(msg))

    def ship_card_of_faction(self, faction):
        if faction is None:
            return None
        ship_cards = []
        for kartya in self._catalogue.all_cards_of_view(CardView.Ship):
            if kartya.faction != faction:
                continue
            if self._catalogue.card_of(kartya.card_guid_of(), CardView.Owner) is None:
                continue
            if self._catalogue.card_of(kartya.card_guid_of(), CardView.World) is None:
                continue
            if not self.carries_weapons(kartya):
                continue
            if not self.prefab_agrees_with_faction(kartya):
                continue
            ship_cards.append(kartya)
        if len(ship_cards) == 0:
            return None
        faction_prefab_matches = [kartya for kartya in ship_cards if self.prefab_wears_faction(kartya, faction)]
        prefab_candidates = ship_cards if len(faction_prefab_matches) == 0 else faction_prefab_matches
        configured_ships = [kartya for kartya in prefab_candidates
                            if first_best_config_for_guid(kartya.card_guid_of()) is not None]
        jeloltek = prefab_candidates if len(configured_ships) == 0 else configured_ships
        if (preferred := self.best_ship_candidate(jeloltek)) is not None:
            return preferred
        if len(configured_ships) != 0:
            prefab_preferred = self.best_ship_candidate(prefab_candidates)
            if prefab_preferred is not None:
                return prefab_preferred
        if (tier_one_fallback := self.tier_one_fallback(jeloltek)) is not None:
            return tier_one_fallback
        if len(configured_ships) != 0:
            if (prefab_fallback := self.tier_one_fallback(prefab_candidates)) is not None:
                return prefab_fallback
        return jeloltek[0]

    def tell_console(self, szoveg) -> None:
        self.ctx.user().send(self._writer.message(str(szoveg)))

    def tier_one_fallback(self, candidates):
        if candidates is None or len(candidates) == 0:
            return None
        for kartya in candidates:
            if (kartya.tier == 1 and kartya.ship_role_deprecated is not None
                and kartya.ship_role_deprecated != OldShipRole.Mothership
                and kartya.ship_role_deprecated != OldShipRole.None_):
                return kartya
        return None

_ALIAS_FILE = "GameData/local/console_aliases.json"
_alias_cache: dict | None = None


def operator_aliases() -> dict:
    global _alias_cache
    if _alias_cache is None:
        table: dict = {}
        try:
            resolved = paths.JATEKADAT / "local" / "console_aliases.json"
            if resolved.exists():
                raw = json.loads(resolved.read_text(encoding="utf-8"))
                table = {str(k): str(v) for k, v in raw.get("aliases", {}).items()}
        except (OSError, ValueError) as baj:
            log.warning("console alias file unreadable: %s", baj)
        _alias_cache = table
    return _alias_cache
