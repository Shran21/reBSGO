# github.com/Shran21
from __future__ import annotations

import logging
from enum import Enum

from rebsgo.world.carriers.carrier_anchor import (
    build_carrier_anchor_hold_move,
    random_position_around_carrier,
    release_carrier_anchor,
    release_carrier_anchors,
)
from rebsgo.world.carriers.carrier_mode import (
    can_ship_dock_at_carrier,
    get_carrier_mode_config,
    is_carrier_space_object,
)
from rebsgo.gamedata.from_json.template_readers import claim_rules
from rebsgo.world.carriers.carrier_transponder_target import try_get_carrier_transponder_player_id
from rebsgo.world.movement.maneuvers import DirectionalManeuver, NoRollManeuver, FollowManeuver, PitchYawTurnPlan, TurnManeuver, TurnQweasdManeuver, DirectionTurnPlan
from rebsgo.world.movement.held_keys import QWEASD
from rebsgo.pilots.state.whereabouts import InCic, AtOutpost
from rebsgo.protocol.wire_base import BgoProtocol
from rebsgo.protocol.game.steps.mining_request import MiningRequest
from rebsgo.protocol.game.game_steps import RespawnChoices
from rebsgo.protocol.game.game_steps import ShipInSector
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.protocol_book_replies import replies_for, game_replies, debug_message
from rebsgo.world.sectors.powers.power_bits import CastOrder
from rebsgo.world.sectors.powers.stealth import deactivate_player_stealth
from rebsgo.world.sectors.sides import Stance, relation
from rebsgo.world.sectors.clockwork import OutpostBeaconTimer
from rebsgo.world.objects.bodies import CargoObject
from rebsgo.vocabulary.world import VisibilityCause, PlaceKind, DepartureCause, ObjectKind, SceneChange
from rebsgo.vocabulary.pilot import Faction, Gear
from rebsgo.vocabulary.combat import ManeuverKind, SpeedMode
from rebsgo.geometry.primitives.euler3 import Euler3
from rebsgo.geometry.primitives.transform import Transform
from rebsgo.geometry.primitives.vector2 import Vector2
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.geometry.maths.maths import Maths
from rebsgo.gamedata.cards.world_cards import GalaxyMapCard
from rebsgo.gamedata.reading import AbilityActionKind, ObjectStat
from rebsgo.helpers.guarded import GuardedFlag, GuardedCell
from rebsgo.helpers.rolling_latency_stats import now_ms


log = logging.getLogger(__name__)


class _ClientMessage(Enum):
    WhoIs = 3
    SubscribeInfo = 10
    UnSubscribeInfo = 11
    MoveToDirection = 12
    MoveToDirectionWithoutRoll = 13
    CastSlotAbility = 21
    CastImmutableSlotAbility = 22
    LockTarget = 25
    WASD = 29
    QWEASD = 30
    Mining = 35
    Loot = 41
    TakeLootItems = 43
    Dock = 45
    Jump = 46
    AnsStartQueue = 48
    AnsJump = 50
    Follow = 52
    Quit = 54
    SetSpeed = 56
    SetGear = 57
    JumpIn = 61
    MoveInfo = 63
    StopJump = 65
    SelectRespawnLocation = 70
    GroupJump = 72
    StopGroupJump = 73
    RequestJumpToTarget = 75
    CompleteJump = 76
    RequestUnanchor = 77
    RequestAnchor = 78
    RequestLaunchStrikes = 79
    CancelMiningRequest = 82
    RequestJumpToBeacon = 85
    ToggleAbilityOn = 86
    ToggleAbilityOff = 87
    UpdateAbilityTargets = 88
    GroupJumpToBeacon = 89
    DirectionTurnPlan = 100
    PitchYawTurnPlan = 101
    CancelDocking = 102
    GroupJumpToTarget = 103
    CargoInteraction = 106

    @staticmethod
    def from_code(uzenet_kod: int):
        return _CM_BY_VALUE.get(uzenet_kod)


_CM_BY_VALUE = {member.value: member for member in _ClientMessage}

_UPDATE_MESSAGES = frozenset({
    _ClientMessage.CastImmutableSlotAbility, _ClientMessage.CastSlotAbility, _ClientMessage.Mining,
    _ClientMessage.LockTarget, _ClientMessage.MoveInfo, _ClientMessage.SubscribeInfo,
    _ClientMessage.UnSubscribeInfo, _ClientMessage.WhoIs, _ClientMessage.Loot,
})

_SPACE_COMBAT_LOCATIONS = frozenset({
    PlaceKind.Space, PlaceKind.Arena, PlaceKind.BattleSpace,
    PlaceKind.Tournament, PlaceKind.Zone,
})

_CAPITAL_AUTOFIRE_ACTIONS = frozenset()


class GameProtocol(BgoProtocol):
    KOTEGELT = {
        _ClientMessage.Loot: "_on_batched_loot",
        _ClientMessage.WhoIs: "_on_batched_who_is",
        _ClientMessage.UnSubscribeInfo: "_on_batched_un_subscribe_info",
        _ClientMessage.SubscribeInfo: "_on_batched_subscribe_info",
        _ClientMessage.MoveInfo: "_on_batched_move_info",
        _ClientMessage.LockTarget: "_on_batched_lock_target",
        _ClientMessage.CastSlotAbility: "_on_batched_cast_slot_ability",
        _ClientMessage.CastImmutableSlotAbility: "_on_batched_cast_immutable_slot_ability",
    }

    def __init__(self, ctx, pilot_roster, sector_book):
        super().__init__(ProtocolID.Game, ctx)
        self._handlers = {}
        self._writer = game_replies()
        self._sector_book = sector_book
        self._jump_target_sector_id = -1
        self._jump_target_sector_guid = -1
        self._is_jumping = False
        self._is_respawn_send = False
        self._dock_future = None
        self._pilot_roster = pilot_roster
        self._complete_jump_flag = GuardedFlag(False)
        self._last_respawn_options = GuardedCell()
        self._jump_companions = None

    def mount_handlers(self) -> None:
        self._handlers[_ClientMessage.Mining] = MiningRequest(self.ctx.user(), self._sector_book)

    def seed_user(self, user) -> None:
        super().seed_user(user)
        self._replay_pending_respawn()

    def _replay_pending_respawn(self) -> None:
        respawn_opts = self._last_respawn_options.get()
        self._last_respawn_options.set(None)
        if respawn_opts is None:
            return

        log.info('no respawn point picked since last logout - taking the first available')

        respawn_sector_id = GalaxyMapCard.start_sector(self.user().pilot_of().faction) \
            if len(respawn_opts.sector_ids) == 0 else respawn_opts.sector_ids[0]

        from rebsgo.services import Services
        from rebsgo.gamedata.library import Catalogue
        star = Services.get(Catalogue).map_card.star(respawn_sector_id)
        if star is not None:
            self.user().pilot_of().location.set_location(
                PlaceKind.Room, star.id, star.sector_guid)
            self._release_capital_ship_after_death()

    @property
    def replies(self):
        return self._writer

    def on_gone(self) -> None:
        super().on_gone()
        self._complete_jump_flag.set(False)
        self._jump_target_sector_id = -1
        sector = self._resolve_sector()
        if sector is None:
            return
        sector.departures_desk.on_user_left(self._user_id)

    def _capital_autofire_on_lock(self, sec_player_ship, target_id: int) -> None:
        if not _CAPITAL_AUTOFIRE_ACTIONS:
            return
        try:
            from rebsgo.world.capitals.capital_roster import CAPITAL_SLOT
            active = self.user().pilot_of().hangar_of().active_ship()
            if active is None or active.server_id != CAPITAL_SLOT:
                return
            player_ship = sec_player_ship.player_ship
            rekeszek = player_ship.space_subscribe_info().ship_slots
            if rekeszek is None:
                return
            queue = sec_player_ship.sector().cast_desk
            obj_id = player_ship.id_in_space()
            armed = 0
            for rekesz in rekeszek.values():
                kepesseg = rekesz.ship_ability()
                if kepesseg is None or kepesseg.ship_ability_card is None:
                    continue
                if kepesseg.ship_ability_card.ability_action_type not in _CAPITAL_AUTOFIRE_ACTIONS:
                    continue
                slot_id = rekesz.ship_system.server_id
                queue.disarm_auto_cast(slot_id, obj_id)
                if target_id and target_id != 0:
                    queue.arm_auto_cast(CastOrder(player_ship, slot_id, True, target_id))
                armed += 1
            log.info("%s capital auto-fire: target=%s armed_weapons=%s",
                     self.user().user_log(), target_id, armed)
        except Exception:
            log.exception("capital auto-fire on lock failed")

    @staticmethod
    def _get_slot_action_type(player_ship, ability_id: int):
        rekeszek = player_ship.space_subscribe_info().ship_slots
        if rekeszek is None:
            return None
        slot = rekeszek.slot(ability_id)
        if slot is None or slot.ship_ability() is None:
            return None
        return slot.ship_ability().ship_ability_card.ability_action_type

    def _handle_toggled_ability_off(self, sector, player_ship, ability_id: int) -> None:
        action_type = GameProtocol._get_slot_action_type(player_ship, ability_id)
        if action_type == AbilityActionKind.ToggleStealth:
            self._set_cloaked_and_broadcast(sector, player_ship, False)
        elif action_type == AbilityActionKind.ToggleSystem:
            self._remove_modifier_for_system(player_ship, ability_id)
        elif action_type == AbilityActionKind.Fortify:
            self._deactivate_fortify(sector, player_ship, ability_id)

    @staticmethod
    def _remove_modifier_for_system(player_ship, ability_id: int) -> bool:
        mutatok = player_ship.space_subscribe_info()
        modifiers = mutatok.modifiers
        if modifiers is None:
            return False
        to_remove = {
            modifier.server_id
            for modifier in modifiers.all()
            if (modifier.ship_system is not None
                and modifier.ship_system.server_id == ability_id)
        }
        if to_remove:
            mutatok.remove_modifiers(to_remove)
            return True
        return False

    def _deactivate_fortify(self, sector, player_ship, ability_id: int, send_stop: bool = False,
                            release_anchors: bool = False) -> None:
        removed = self._remove_modifier_for_system(player_ship, ability_id)
        allapot = player_ship.world_state_of()
        if not removed and not allapot.is_fortified:
            return
        allapot.set_fortified(False)
        sector.ctx.sender().push_to_everyone(self._writer.space_object_state(allapot))
        if release_anchors and is_carrier_space_object(player_ship):
            release_carrier_anchors(sector.ctx, player_ship, "fortify deactivated")
        if send_stop:
            self.user().send(self._writer.stop_slot_ability(ability_id))

    def _set_cloaked_and_broadcast(self, sector, player_ship, cloaked: bool) -> None:
        allapot = player_ship.world_state_of()
        if allapot.is_cloaked == cloaked:
            return
        allapot.cloak(cloaked)
        sender = sector.ctx.sender()
        sender.push_to_everyone(self._writer.space_object_state(allapot))

        visibility = player_ship.visibility_of()
        if cloaked:
            visibility.start_stealth()
        else:
            visibility.finish_stealth()

    @staticmethod
    def _remove_auto_casts_by_action_type(sector, player_ship, action_type) -> None:
        rekeszek = player_ship.space_subscribe_info().ship_slots
        if rekeszek is None:
            return
        queue = sector.cast_desk
        for rekesz in rekeszek.values():
            kepesseg = rekesz.ship_ability()
            if kepesseg is None or kepesseg.ship_ability_card.ability_action_type != action_type:
                continue
            queue.disarm_auto_cast(rekesz.ship_system.server_id, player_ship.id_in_space())

    KEZELOK = {
        _ClientMessage.RequestAnchor: "_on_request_anchor",
        _ClientMessage.RequestUnanchor: "_on_request_unanchor",
        _ClientMessage.RequestLaunchStrikes: "_on_request_launch_strikes",
        _ClientMessage.RequestJumpToTarget: "_on_request_jump_to_target",
        _ClientMessage.JumpIn: "_on_jump_in",
        _ClientMessage.Jump: "_on_jump",
        _ClientMessage.GroupJump: "_on_group_jump",
        _ClientMessage.RequestJumpToBeacon: "_on_request_jump_to_beacon",
        _ClientMessage.GroupJumpToBeacon: "_on_group_jump_to_beacon",
        _ClientMessage.StopJump: "_on_stop_jump",
        _ClientMessage.StopGroupJump: "_on_stop_group_jump",
        _ClientMessage.Quit: "_on_quit",
        _ClientMessage.CompleteJump: "_on_complete_jump",
        _ClientMessage.SelectRespawnLocation: "_on_select_respawn_location",
        _ClientMessage.PitchYawTurnPlan: "_on_pitch_yaw_turn_plan",
        _ClientMessage.DirectionTurnPlan: "_on_direction_turn_plan",
        _ClientMessage.MoveToDirection: "_on_move_to_direction",
        _ClientMessage.MoveToDirectionWithoutRoll: "_on_move_to_direction_without_roll",
        _ClientMessage.QWEASD: "_on_qweasd",
        _ClientMessage.WASD: "_on_wasd",
        _ClientMessage.SetGear: "_on_set_gear",
        _ClientMessage.SetSpeed: "_on_set_speed",
        _ClientMessage.ToggleAbilityOn: "_on_toggle_ability_on",
        _ClientMessage.UpdateAbilityTargets: "_on_update_ability_targets",
        _ClientMessage.ToggleAbilityOff: "_on_toggle_ability_off",
        _ClientMessage.Dock: "_on_dock",
        _ClientMessage.CancelDocking: "_on_cancel_docking",
        _ClientMessage.CargoInteraction: "_on_cargo_interaction",
    }
    for _uzenet in _UPDATE_MESSAGES:
        KEZELOK.setdefault(_uzenet, "_cmd_update_messages")
    del _uzenet

    def read_message(self, msg_type, br) -> None:
        client_message = _ClientMessage.from_code(msg_type)
        kezelo = self.KEZELOK.get(client_message)
        if kezelo is None:
            log.error(f'game protocol has no branch for message kind {client_message}')
            return
        getattr(self, kezelo)(msg_type, br, client_message)

    def _on_request_anchor(self, msg_type, br, client_message) -> None:
        target_id = br.read_uint32()
        self._handle_request_anchor(target_id)

    def _on_request_unanchor(self, msg_type, br, client_message) -> None:
        self._handle_request_unanchor()

    def _on_request_launch_strikes(self, msg_type, br, client_message) -> None:
        self._handle_request_launch_strikes()

    def _on_request_jump_to_target(self, msg_type, br, client_message) -> None:
        self._handle_request_jump_to_target(br)

    def _on_jump_in(self, msg_type, br, client_message) -> None:
        self._handle_jump_in()

    def _on_jump(self, msg_type, br, client_message) -> None:
        self._handle_jump(br)

    def _on_group_jump(self, msg_type, br, client_message) -> None:
        self._handle_group_jump(br)

    def _on_request_jump_to_beacon(self, msg_type, br, client_message) -> None:
        sector_id = br.read_uint32()
        self._handle_jump_to_beacon(sector_id)

    def _on_group_jump_to_beacon(self, msg_type, br, client_message) -> None:
        self._handle_group_jump_to_beacon(br)

    def _on_stop_jump(self, msg_type, br, client_message) -> None:
        self._handle_stop_jump()

    def _on_stop_group_jump(self, msg_type, br, client_message) -> None:
        self._handle_stop_group_jump()

    def _on_quit(self, msg_type, br, client_message) -> None:
        self._handle_quit()

    def _on_complete_jump(self, msg_type, br, client_message) -> None:
        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.pair_complete():
            log.warning('cheat %s: jump completion without a sector or a ship', self.user().user_log())
            return
        self._complete_jump_flag.set(True)

    def _on_select_respawn_location(self, msg_type, br, client_message) -> None:
        self._handle_select_respawn_location(br)

    def _on_pitch_yaw_turn_plan(self, msg_type, br, client_message) -> None:
        self._handle_turn_by_pitch_yaw_strikes(br)

    def _on_direction_turn_plan(self, msg_type, br, client_message) -> None:
        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.pair_complete():
            return
        player_ship = sec_player_ship.player_ship
        direction_input = br.read_euler3()
        roll_input = br.read_single()
        strafe_direction = br.read_vector2()
        turn_toward_strikes = DirectionTurnPlan(direction_input, roll_input,
                                                strafe_direction.x, strafe_direction.y)
        self._queue_wire_maneuver(player_ship, turn_toward_strikes, sec_player_ship.sector())

    def _on_move_to_direction(self, msg_type, br, client_message) -> None:
        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.pair_complete():
            return
        player_ship = sec_player_ship.player_ship
        irany = br.read_euler3()
        self._queue_wire_maneuver(player_ship, DirectionalManeuver(irany), sec_player_ship.sector())

    def _on_move_to_direction_without_roll(self, msg_type, br, client_message) -> None:
        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.pair_complete():
            return
        player_ship = sec_player_ship.player_ship
        irany = br.read_euler3()
        self._queue_wire_maneuver(
            player_ship, NoRollManeuver(irany), sec_player_ship.sector())

    def _on_qweasd(self, msg_type, br, client_message) -> None:
        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.pair_complete():
            return
        player_ship = sec_player_ship.player_ship
        bitmask = br.read_byte()
        self._queue_wire_maneuver(
            player_ship, TurnQweasdManeuver(QWEASD(bitmask)), sec_player_ship.sector())

    def _on_wasd(self, msg_type, br, client_message) -> None:
        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.pair_complete():
            return
        player_ship = sec_player_ship.player_ship
        bitmask = br.read_byte()
        self._queue_wire_maneuver(player_ship, TurnManeuver(QWEASD(bitmask)), sec_player_ship.sector())

    def _on_set_gear(self, msg_type, br, client_message) -> None:
        self._handle_set_gear(br)

    def _on_set_speed(self, msg_type, br, client_message) -> None:
        self._handle_set_speed(br)

    def _on_toggle_ability_on(self, msg_type, br, client_message) -> None:
        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.pair_complete():
            return
        player_ship = sec_player_ship.player_ship
        sector = sec_player_ship.sector()
        ability_id = br.read_uint16()
        target_ids = tuple(br.read_uint32_array())
        player_id = player_ship.pilot_id()
        enqueued_ms = now_ms()
        callback = lambda: self._apply_toggle_ability_on_command(
            sector, player_id, ability_id, target_ids, enqueued_ms)
        if not self._enqueue_player_sector_command(sector, callback, "toggle_ability_on"):
            callback()

    def _on_update_ability_targets(self, msg_type, br, client_message) -> None:
        ability_id = br.read_uint16()
        target_ids = tuple(br.read_uint32_array())
        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.pair_complete():
            return
        player_ship = sec_player_ship.player_ship
        sector = sec_player_ship.sector()
        player_id = player_ship.pilot_id()
        enqueued_ms = now_ms()
        callback = lambda: self._apply_update_ability_targets_command(
            sector, player_id, ability_id, target_ids, enqueued_ms)
        if not self._enqueue_player_sector_command(sector, callback, "update_ability_targets"):
            callback()

    def _on_toggle_ability_off(self, msg_type, br, client_message) -> None:
        ability_id = br.read_uint16()
        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.pair_complete():
            return
        player_ship = sec_player_ship.player_ship
        sector = sec_player_ship.sector()
        player_id = player_ship.pilot_id()
        callback = lambda: self._apply_toggle_ability_off_command(sector, player_id, ability_id)
        if not self._enqueue_player_sector_command(sector, callback, "toggle_ability_off"):
            callback()

    def _on_dock(self, msg_type, br, client_message) -> None:
        self._handle_dock(br)

    def _on_cancel_docking(self, msg_type, br, client_message) -> None:
        sector_and_player_ship = self._locate_ship_in_sector()
        if not sector_and_player_ship.pair_complete():
            log.error('cannot abort docking - ship or sector missing %s',
                      self.user().user_log_simple)
            return
        if self._dock_future is not None:
            self._dock_future.call_off()
            sector_and_player_ship.player_ship.world_state_of().mark_docking(False)

    def _cmd_update_messages(self, msg_type, br, client_message) -> None:
        self._decode_update(br, client_message)

    def _on_cargo_interaction(self, msg_type, br, client_message) -> None:
        cargo_object_id = br.read_uint32()
        raw_cargo_interaction = br.read_byte()
        interaction = CargoObject.Interaction.from_code(raw_cargo_interaction)
        if interaction is None:
            return
        self._handle_cargo_interaction(cargo_object_id, interaction)


    def _handle_request_anchor(self, target_id: int) -> None:
        sec_player_ship = self._locate_ship_in_sector()
        sector = sec_player_ship.sector()
        player_ship = sec_player_ship.player_ship
        if sector is None or player_ship is None or player_ship.is_removed():
            log.warning('neither sector nor ship resolvable, or the ship is gone %s, %s',
                        sector is None, player_ship is None)
            return

        celpont = sector.ctx.space_objects().get(target_id)
        if celpont is None:
            log.warning('docking target absent')
            return
        target_to_dock = celpont
        if target_to_dock.is_removed():
            log.warning("Target space_object to dock is removed! %s", self.user().user_log())
            return

        self._try_anchor_to_carrier(sector, player_ship, target_id, target_to_dock, "RequestAnchor")

    def _try_anchor_to_carrier(self, sector, player_ship, target_id: int, target_to_dock, source: str) -> bool:
        carrier_config = get_carrier_mode_config()
        if not is_carrier_space_object(target_to_dock):
            log.warning("%s target is not a carrier base-mode ship target=%s user=%s",
                        source, target_id, self.user().user_log())
            return False
        if (carrier_config.require_fortified_for_anchor
            and not target_to_dock.world_state_of().is_fortified):
            log.warning("%s target carrier is not fortified target=%s user=%s",
                        source, target_id, self.user().user_log())
            return False
        player_ship_card = player_ship.ship_card_of()
        if not can_ship_dock_at_carrier(player_ship_card):
            log.warning("%s ship role cannot dock at carrier ship=%s user=%s",
                        source,
                        None if player_ship_card is None else player_ship_card.card_guid_of(),
                        self.user().user_log())
            return False

        user_to_dock_at = self._pilot_roster.by_id(target_to_dock.pilot_id())
        if user_to_dock_at is None:
            log.error('the carrier to dock with is not in the sector')
            return False

        party_of_user = self.user().pilot_of().party()
        if carrier_config.party_only:
            if party_of_user is None:
                log.error("%s but user has no party!", source)
                return False
            party_to_dock_at = user_to_dock_at.pilot_of().party()
            if party_to_dock_at is None:
                log.error("Squad of user to dock at is not present")
                return False

            if not party_to_dock_at.is_in_party(player_ship.pilot_id()):
                log.error('cheat: dock target %s shares no party with %s',
                          user_to_dock_at.user_log(), self.user().user_log())
                self.user().send(debug_message(
                    "dokkolás olyan pilótához, aki nincs a rajban"))
                return False

        owner_card = target_to_dock.owner_card
        actual_distance = Vector3.distance(player_ship.mover_of().position_of(),
                                           target_to_dock.mover_of().position_of())
        dock_range = max(owner_card.dock_range, carrier_config.dock_range)
        if not owner_card.is_dockable or dock_range < actual_distance:
            log.warning('dock check failed: dockable=%s at distance=%s',
                        owner_card.is_dockable, actual_distance)
            return False

        player_visibility = player_ship.visibility_of()
        anchor_hold_buffer = build_carrier_anchor_hold_move(
            sector.ctx, target_to_dock, player_ship, clear_new_maneuver=True)
        player_visibility.switch_visibility(False, VisibilityCause.Anchor, target_id)
        target_to_dock.world_state_of().anchor_to(player_ship.pilot_id())
        pilot_wire = replies_for(ProtocolID.Pilot)
        anchor_buffer = pilot_wire.anchor(target_id)
        if anchor_hold_buffer is not None:
            self.user().send([anchor_hold_buffer, anchor_buffer])
        else:
            self.user().send(anchor_buffer)
        if party_of_user is not None:
            community_protocol_write_only = replies_for(ProtocolID.Community)
            party_anchor_buffer = community_protocol_write_only.party_anchor(
                target_to_dock.pilot_id(), player_ship.pilot_id(), True)
            party_of_user.tell_squad(party_anchor_buffer)
        return True

    def _handle_request_launch_strikes(self) -> None:
        sec_player_ship = self._locate_ship_in_sector()
        sector = sec_player_ship.sector()
        player_ship = sec_player_ship.player_ship
        if sector is None or player_ship is None or player_ship.is_removed():
            log.warning('RequestLaunchStrikes lacks a live sector or ship %s, %s',
                        sector is None, player_ship is None)
            return
        released = release_carrier_anchors(sector.ctx, player_ship, "launch strikes button")
        log.info("RequestLaunchStrikes: released %s anchored ships user=%s",
                 released, self.user().user_log())

    def _handle_request_unanchor(self) -> None:
        log.info('release requested')
        sec_player_ship = self._locate_ship_in_sector()
        sector = sec_player_ship.sector()
        player_ship = sec_player_ship.player_ship
        if sector is None or player_ship is None or player_ship.is_removed():
            log.warning('neither sector nor ship resolvable, or the ship is gone %s, %s',
                        sector is None, player_ship is None)
            return

        player_visibility = player_ship.visibility_of()
        if player_visibility.is_visible():
            log.warning("VisibleSet is already visible but set visible to true again??")
            return

        anchored_object_id_to = player_visibility.anchored_object_id
        from rebsgo.protocol.pilot.pilot_steps import ReleaseCause
        anchored_to = sector.ctx.space_objects().get(anchored_object_id_to)
        if anchored_to is None:
            player_visibility.switch_visibility(True, VisibilityCause.Anchor)
            pilot_wire = replies_for(ProtocolID.Pilot)
            self.user().send(pilot_wire.un_anchor(
                player_ship.id_in_space(), ReleaseCause.Default))
            log.warning('anchor target is not around')
            return
        release_carrier_anchor(sector.ctx, anchored_to, player_ship.pilot_id())

    def _handle_jump_in(self) -> None:
        sector = self._sector_book.sector_by_id(self.user().pilot_of().sector_id)
        if sector is None:
            log.warning('%s finished a jump into a sector id we cannot resolve: %s',
                        self.user().user_log(), self.user().pilot_of().sector_id)
            return
        user_in_sector = sector.ctx.users().user(self.user().pilot_of().user_id_of())
        log.info(f'pilot inside sector {user_in_sector}')
        if self._last_respawn_options.get() is not None:
            log.warning("%s cheat jump_in but user was dead and respawn opts sent", self.user().user_log())
            return
        log.info("%s JumpIn %s", self.user().user_log(), sector.id)
        sector.arrival_gate.arrival_queue(self.user(), self._jump_companions)
        self._jump_companions = None
        try:
            if (player_proto := self.user().protocol_of(ProtocolID.Pilot)) is not None:
                player_proto.update_capital_galaxy_sector(sector.id)
        except Exception:
            log.exception("capital galaxy follow on jump-in failed")

    def _handle_jump(self, br) -> None:
        sector_id = br.read_uint32()
        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.pair_complete():
            log.error('%sjump with neither ship nor sector', self.user().user_log())
            return
        player_ship = sec_player_ship.player_ship
        if player_ship.is_removed():
            log.error('%s jump asked by a ship already gone from the world',
                      self.user().user_log())
            return
        log.info('%sjump asked toward sector %s', self.user().user_log(), sector_id)

        sector_exists = sector_id in self.ctx.galaxy.map_card.stars
        if not sector_exists:
            log.error('%sjump asked toward a sector that does not exist %s',
                      self.user().user_log(), sector_id)
        star = self.ctx.galaxy.map_card.star(sector_id)
        if star is None:
            log.error("Error in fetch galaxystar, cannot find sectorID %s in jump_query by user %s",
                      sector_id, self.user().user_log())
            return
        star_destination = star
        source_star = self.ctx.galaxy.map_card.star(self.user().pilot_of().sector_id)
        if source_star is None:
            log.error('%sjump asked from a sector that is unresolvable %s',
                      self.user().user_log(), self.user().pilot_of().sector_id)
            return
        ftl_jump_range = player_ship.space_subscribe_info().stat(ObjectStat.FtlRange)
        jump_distance = Vector2.distance(source_star.position_of(), star_destination.position_of())
        can_jump_distance = jump_distance <= ftl_jump_range
        jump_open_to = star_destination.jump_open_to(player_ship.faction)
        if (GalaxyMapCard.is_base_sector(Faction.negated(player_ship.faction), sector_id)
            or not jump_open_to or not can_jump_distance
                or self._sector_gate_refuses(sector_id)):
            if not can_jump_distance:
                log.error('%s jump asked from beyond allowed reach %s range %s',
                          self.user().user_log(), jump_distance, ftl_jump_range)
            notification_protocol = self.user().protocol_of(ProtocolID.Notification)
            notification_protocol.refuse_jump()
            return

        charge = player_ship.space_subscribe_info().stat(ObjectStat.FtlCharge)
        is_in_combat = player_ship.space_subscribe_info().is_in_combat
        self.jump_now(sec_player_ship.sector().jump_book, sector_id, charge, is_in_combat)

    def _handle_group_jump(self, br) -> None:
        sector_id = br.read_uint32()
        player_ids = br.read_uint32_array()
        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.pair_complete():
            log.error('%sjump with neither ship nor sector', self.user().user_log())
            return
        player_ship = sec_player_ship.player_ship
        sector = sec_player_ship.sector()
        star = self.ctx.galaxy.map_card.star(sector_id)
        if star is None:
            log.error("Error in fetch galaxystar, cannot find sectorID %s in jump_query by user %s",
                      sector_id, self.user().user_log())
            return
        star_destination = star
        can_jump = star_destination.jump_open_to(player_ship.faction)
        if (GalaxyMapCard.is_base_sector(Faction.negated(player_ship.faction), sector_id)
                or not can_jump or self._sector_gate_refuses(sector_id)):
            notification_protocol = self.user().protocol_of(ProtocolID.Notification)
            notification_protocol.refuse_jump()
            return
        self.party_jump(sector, sector_id, player_ids)

    def _handle_jump_to_beacon(self, sector_id: int) -> None:
        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.pair_complete():
            log.error('%sJumpToBeacon but no space_ship and no sector!', self.user().user_log())
            return
        player_ship = sec_player_ship.player_ship
        if player_ship.is_removed():
            log.error('%s Cheat PlayerShip is removed but beacon jump request received',
                      self.user().user_log())
            return

        if not self._is_jump_destination_allowed(sector_id, player_ship, True):
            return

        ora = self._get_target_beacon_timer(sector_id)
        arrival_transform = None if ora is None else ora.arrival_transform_for(
            player_ship.faction, self.user().pilot_of().user_id_of())
        if arrival_transform is None:
            log.warning("%s JumpToBeacon denied: no active beacon in sector %s for faction %s",
                        self.user().user_log(), sector_id, player_ship.faction)
            notification_protocol = self.user().protocol_of(ProtocolID.Notification)
            notification_protocol.refuse_jump()
            return

        charge = player_ship.space_subscribe_info().stat(ObjectStat.FtlCharge)
        is_in_combat = player_ship.space_subscribe_info().is_in_combat
        self.jump_now(sec_player_ship.sector().jump_book, sector_id, charge, is_in_combat,
                      arrival_transform)

    def _handle_group_jump_to_beacon(self, br) -> None:
        sector_id = br.read_uint32()
        player_ids = br.read_uint32_array()
        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.pair_complete():
            log.error('%sGroupJumpToBeacon but no space_ship and no sector!',
                      self.user().user_log())
            return
        player_ship = sec_player_ship.player_ship
        sector = sec_player_ship.sector()

        if not self._is_jump_destination_allowed(sector_id, player_ship, False):
            return

        ora = self._get_target_beacon_timer(sector_id)
        if ora is None or not ora.is_beacon_active(player_ship.faction):
            log.warning("%s GroupJumpToBeacon denied: no active beacon in sector %s for faction %s",
                        self.user().user_log(), sector_id, player_ship.faction)
            notification_protocol = self.user().protocol_of(ProtocolID.Notification)
            notification_protocol.refuse_jump()
            return

        arrival_by_user_id = {}
        if (party := self.user().pilot_of().party()) is not None:
            party_members = [party.leader()]
            party_members.extend([tag for tag in party.members() if tag != party.leader()])
            for tag in party_members:
                user_id = tag.pilot_of().user_id_of()
                if tag == party.leader() or any(ertek == user_id for ertek in player_ids):
                    transform = ora.arrival_transform_for(player_ship.faction, user_id)
                    if transform is not None:
                        arrival_by_user_id[user_id] = transform
        self.party_jump(sector, sector_id, player_ids, arrival_by_user_id)

    def _sector_gate_refuses(self, sector_id: int) -> bool:
        from rebsgo.gamedata.from_json.template_readers import sector_policy
        policy = sector_policy()
        if policy.is_disabled(sector_id):
            log.info('%s jump refused: sector %s is closed by policy',
                     self.user().user_log(), sector_id)
            return True
        limit = policy.player_limit(sector_id)
        if limit is None:
            return False
        sector = self._sector_book.sector_by_id(sector_id)
        if sector is None:
            return False
        try:
            headcount = len(sector.ctx.users().users())
        except Exception:
            return False
        if headcount >= limit:
            log.info('%s jump refused: sector %s is full (%s of %s)',
                     self.user().user_log(), sector_id, headcount, limit)
            return True
        return False

    def _is_jump_destination_allowed(self, sector_id: int, player_ship, enforce_distance: bool) -> bool:
        star = self.ctx.galaxy.map_card.star(sector_id)
        if star is None:
            log.error("Error in fetch galaxystar, cannot find sectorID %s in jump_query by user %s",
                      sector_id, self.user().user_log())
            return False
        if self._sector_gate_refuses(sector_id):
            notification_protocol = self.user().protocol_of(ProtocolID.Notification)
            notification_protocol.refuse_jump()
            return False
        star_destination = star
        jump_open_to = star_destination.jump_open_to(player_ship.faction)
        can_jump_distance = True
        if enforce_distance:
            source_star = self.ctx.galaxy.map_card.star(
                self.user().pilot_of().sector_id)
            if source_star is None:
                log.error('%sjump asked from a sector that is unresolvable %s',
                          self.user().user_log(), self.user().pilot_of().sector_id)
                return False
            ftl_jump_range = player_ship.space_subscribe_info().stat(ObjectStat.FtlRange)
            jump_distance = Vector2.distance(source_star.position_of(), star_destination.position_of())
            can_jump_distance = jump_distance <= ftl_jump_range
            if not can_jump_distance:
                log.error('%s Cheat user tried to beacon jump while no jump range distance %s range %s',
                          self.user().user_log(), jump_distance, ftl_jump_range)
        if GalaxyMapCard.is_base_sector(Faction.negated(player_ship.faction), sector_id) \
                or not jump_open_to or not can_jump_distance:
            notification_protocol = self.user().protocol_of(ProtocolID.Notification)
            notification_protocol.refuse_jump()
            return False
        return True

    def _handle_request_jump_to_target(self, br) -> None:
        sector_id = br.read_uint32()
        target_space_id = br.read_uint32()
        sec_player_ship = self._locate_ship_in_sector()
        sector = sec_player_ship.sector()
        player_ship = sec_player_ship.player_ship
        if sector is None or player_ship is None or player_ship.is_removed():
            log.warning('RequestJumpToTarget lacks a live sector or ship %s, %s',
                        sector is None, player_ship is None)
            return

        if not self._is_jump_destination_allowed(sector_id, player_ship, False):
            return

        target_sector = self._sector_book.sector_by_id(sector_id)
        celpont = self._resolve_carrier_jump_target(target_sector, target_space_id)
        if (celpont is None or celpont.is_removed()
            or not is_carrier_space_object(celpont)
            or not celpont.world_state_of().is_fortified
            or celpont.faction != player_ship.faction):
            log.warning("%s RequestJumpToTarget denied: target %s in sector %s is not a fortified "
                        "friendly carrier", self.user().user_log(), target_space_id, sector_id)
            notification_protocol = self.user().protocol_of(ProtocolID.Notification)
            notification_protocol.refuse_jump()
            return

        if celpont.pilot_id() == player_ship.pilot_id():
            log.warning("%s RequestJumpToTarget denied: cannot jump to own carrier target=%s sector=%s",
                        self.user().user_log(), target_space_id, sector_id)
            notification_protocol = self.user().protocol_of(ProtocolID.Notification)
            notification_protocol.refuse_jump()
            return

        if get_carrier_mode_config().transponder_party_only():
            party = self.user().pilot_of().party()
            if party is None or not party.is_in_party(celpont.pilot_id()):
                log.warning("%s RequestJumpToTarget denied: not in the carrier owner's party (owner=%s)",
                            self.user().user_log(), celpont.pilot_id())
                notification_protocol = self.user().protocol_of(ProtocolID.Notification)
                notification_protocol.refuse_jump()
                return

        arrival_position = random_position_around_carrier(
            celpont.mover_of().position_of())
        arrival_transform = Transform(arrival_position, Euler3.zero())
        log.info("%s RequestJumpToTarget: jumping to fortified carrier %s (player %s) in sector %s",
                 self.user().user_log(), target_space_id, celpont.pilot_id(), sector_id)

        charge = player_ship.space_subscribe_info().stat(ObjectStat.FtlCharge)
        is_in_combat = player_ship.space_subscribe_info().is_in_combat
        self.jump_now(sector.jump_book, sector_id, charge, is_in_combat,
                      arrival_transform)

    @staticmethod
    def _resolve_carrier_jump_target(cel_szektor, target_space_id: int):
        if cel_szektor is None:
            return None
        ctx = cel_szektor.ctx
        celpont = ctx.space_objects().get(target_space_id)
        if celpont is not None:
            return celpont

        target_player_id = try_get_carrier_transponder_player_id(target_space_id)
        if target_player_id is None:
            return None

        users = ctx.users()
        if (celpont := users.ship_of_pilot(target_player_id)) is not None:
            return celpont

        for obj in ctx.space_objects().space_objects_of_entity_type(ObjectKind.Pilot):
            if obj.pilot_id() == target_player_id:
                return obj
        return None

    def _get_target_beacon_timer(self, sector_id: int):
        target_sector = self._sector_book.sector_by_id(sector_id)
        if target_sector is None:
            return None
        return target_sector.timer_updater.timer_of_type(OutpostBeaconTimer)

    def _handle_stop_jump(self) -> None:
        log.info('%sjump called off', self.user().user_log())
        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.pair_complete():
            return
        self._is_jumping = False
        player = self.user().pilot_of()
        sec_player_ship.sector().jump_book.remove_jump(player.user_id_of())

    def _handle_stop_group_jump(self) -> None:
        log.info('%sasked to halt the group jump', self.user().user_log())
        party = self.user().pilot_of().party()
        if party is None:
            return
        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.pair_complete():
            log.warning('group-jump halt with neither sector nor ship %s', sec_player_ship)
            return
        sector = sec_player_ship.sector()
        is_leader = party.leader() == self.user()
        stop_bw = self._writer.leader_stop_group_jump() if is_leader \
            else self._writer.stop_group_jump(self.user().pilot_of().user_id_of())
        for tag in party.members():
            if is_leader:
                sector.jump_book.remove_jump(tag.pilot_of().user_id_of())
            else:
                if tag == self.user():
                    sector.jump_book.remove_jump(tag.pilot_of().user_id_of())
            tag.send(stop_bw)

    def _handle_quit(self) -> None:
        if not self._is_jumping:
            log.info('%s left the sector mid-jump', self.user().user_log())
            return
        player = self.user().pilot_of()
        player.location.set_location(PlaceKind.Space, self._jump_target_sector_id,
                                     self._jump_target_sector_guid)
        scene_prot = self.user().protocol_of(ProtocolID.Scene)
        scene_prot.push_scene_change()
        self._jump_target_sector_id = -1
        self._jump_target_sector_guid = -1
        self._is_jumping = False
        log.info('%s left the sector', self.user().user_log())

    def _handle_select_respawn_location(self, br) -> None:
        respawn_sector_id = br.read_uint32()
        respawn_player_id = br.read_uint32()
        log.info('%srespawn point: %s respawning pilot: %s', self.user().user_log(),
                 respawn_sector_id, respawn_player_id)

        sec_player_ship = self._locate_ship_in_sector()
        player_ship = sec_player_ship.player_ship
        log.info(f'both sides present, outcome {sec_player_ship.pair_complete()}')
        if sec_player_ship.pair_complete() and not player_ship.is_dead():
            log.warning('%s cheat: respawn pick while the ship still lives',
                        self.user().user_log())
            return

        last_tmp_spawn_opts = self._last_respawn_options.get()
        if last_tmp_spawn_opts is None:
            log.warning('%s cheat: respawn pick that was never offered', self.user().user_log())
            return
        log.info(f'latest temporary spawn options {last_tmp_spawn_opts}')
        selected_respawn_sector_id_is_valid = respawn_sector_id in last_tmp_spawn_opts.sector_ids
        if not selected_respawn_sector_id_is_valid:
            log.warning('%s cheat user selected respawn opts sector_id not valid',
                        self.user().user_log())
            return

        sector = self._sector_book.sector_by_id(respawn_sector_id)
        if sector is None:
            log.warning('%srespawn choice in a sector that holds nothing',
                        self.user().user_log())
            return
        player = self.user().pilot_of()
        sector.departures_desk.respawn_choice_made(self.user().pilot_of().user_id_of())
        player.location.set_location(PlaceKind.Room, respawn_sector_id, sector.sector_guid)
        self.dock_now(True)
        self._last_respawn_options.set(None)

    def _handle_turn_by_pitch_yaw_strikes(self, br) -> None:
        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.pair_complete():
            return
        player_ship = sec_player_ship.player_ship
        pitch_yaw_roll_factor = br.read_vector3()
        strafe_direction = br.read_vector2()
        strafe_magnitude = br.read_single()
        opts = player_ship.mover_of().movement_options
        current_gear = opts.gear_of
        log.info("PitchYawTurnPlan - Gear: %s, StrafeAccel: %s, StrafeMaxSpeed: %s, StrafeDir: %s, StrafeMag: %s",
                 current_gear, opts.strafe_acceleration, opts.strafe_max_speed, strafe_direction,
                 strafe_magnitude)
        turn_by_strikes = PitchYawTurnPlan(pitch_yaw_roll_factor, strafe_direction, strafe_magnitude)
        self._queue_wire_maneuver(player_ship, turn_by_strikes, sec_player_ship.sector())

    def _handle_set_gear(self, br) -> None:
        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.pair_complete():
            return
        player_ship = sec_player_ship.player_ship
        gear_val = br.read_byte()
        new_gear = Gear.from_code(gear_val)
        if new_gear is None:
            return
        mover = player_ship.mover_of()
        movement_options = mover.movement_options
        sebesseg = 0
        acceleration = player_ship.space_subscribe_info().stat(ObjectStat.Acceleration)
        if new_gear == Gear.Regular:
            sebesseg = movement_options.throttle_speed
        elif new_gear == Gear.Boost:
            sector = sec_player_ship.sector()
            deactivate_player_stealth(sector.ctx, player_ship, sector.cast_desk)
            fortify_slot_ids = self._get_active_fortify_slot_ids(player_ship)
            for fortify_slot_id in fortify_slot_ids:
                sector.cast_desk.disarm_auto_cast(
                    fortify_slot_id, player_ship.id_in_space())
                self._deactivate_fortify(
                    sector, player_ship, fortify_slot_id, send_stop=True, release_anchors=False)
            sebesseg = player_ship.space_subscribe_info().stat(ObjectStat.BoostSpeed)
            acc_bonus = player_ship.space_subscribe_info().stat(ObjectStat.AccelerationMultiplierOnBoost)
            acceleration *= acc_bonus
            current_maneuver = mover.current_maneuver
            if current_maneuver is not None and isinstance(current_maneuver, PitchYawTurnPlan):
                old_strafe = current_maneuver.strafe_direction.copy()
                old_strafe.x_to(0)
                old_strafe.y_to(0)
                new_turn_by_pitch = PitchYawTurnPlan(
                    current_maneuver.pitch_yaw_roll_factor.copy(), old_strafe,
                    current_maneuver.strafe_magnitude)
                self._queue_wire_maneuver(player_ship, new_turn_by_pitch, sec_player_ship.sector())
        movement_options.accelerate_at(acceleration)
        movement_options.set_speed(sebesseg)
        movement_options.shift_to(new_gear)
        if (mods := player_ship.space_subscribe_info().modifiers) is not None:
            all_slides = {ship_modifier.server_id for ship_modifier in mods.of_type(AbilityActionKind.Slide)}
            player_ship.space_subscribe_info().remove_modifiers(all_slides)
        if mover.current_maneuver.maneuver_type == ManeuverKind.Rest:
            irany = Euler3.from_quaternion(mover.rotation_of())
            self._queue_wire_maneuver(player_ship, DirectionalManeuver(irany), sec_player_ship.sector())
        self._note_updown_input(player_ship)

    @staticmethod
    def _get_active_fortify_slot_ids(player_ship) -> set[int]:
        mutatok = player_ship.space_subscribe_info()
        modifiers = mutatok.modifiers
        if modifiers is None:
            return set()
        return {
            modifier.ship_system.server_id
            for modifier in modifiers.of_type(AbilityActionKind.Fortify)
            if modifier.ship_system is not None
        }

    def _handle_set_speed(self, br) -> None:
        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.pair_complete():
            return
        player_ship = sec_player_ship.player_ship
        speed_mode = SpeedMode.from_code(br.read_byte())
        client_speed = br.read_single()
        mover = player_ship.mover_of()
        manover = mover.current_maneuver
        movement_options = mover.movement_options
        max_speed = player_ship.space_subscribe_info().stat(ObjectStat.Speed)
        client_speed_cleaned = Maths.clamp_safe(client_speed, 0, max_speed)
        if client_speed_cleaned > 0:
            sector = sec_player_ship.sector()
            for fortify_slot_id in self._get_active_fortify_slot_ids(player_ship):
                sector.cast_desk.disarm_auto_cast(
                    fortify_slot_id, player_ship.id_in_space())
                self._deactivate_fortify(
                    sector, player_ship, fortify_slot_id, send_stop=True, release_anchors=False)
        movement_options.throttle_to(client_speed_cleaned)
        if movement_options.gear_of == Gear.Regular:
            movement_options.set_speed(client_speed_cleaned)
        self._note_updown_input(player_ship)
        if manover.maneuver_type == ManeuverKind.Rest:
            irany = Euler3.from_quaternion(mover.rotation_of())
            self._queue_wire_maneuver(player_ship, DirectionalManeuver(irany), sec_player_ship.sector())

    def _handle_dock(self, br) -> None:
        sec_and_player_ship = self._locate_ship_in_sector()
        dock_object_id = br.read_uint32()
        log.info("Received dock request, dock_delay was %s (useless value)", br.read_single())
        if not sec_and_player_ship.pair_complete():
            log.error('docking, sector and ship both resolved: %s', sec_and_player_ship)
            return

        sector = sec_and_player_ship.sector()
        player_ship = sec_and_player_ship.player_ship
        cel = sector.ctx.space_objects().get(dock_object_id)
        if cel is not None and is_carrier_space_object(cel):
            self._try_anchor_to_carrier(sector, player_ship, dock_object_id, cel, "Dock")
        elif (panasz := self._dock_refusal(player_ship, cel)) is not None:
            log.error('%s %s', panasz, self.user().pilot_of().player_log)
        else:
            self.dock_now(player_ship.is_dead())

    @staticmethod
    def _dock_refusal(player_ship, cel) -> str | None:
        if cel is None:
            return 'dock request aimed at a target that does not exist:'
        owner_card = cel.owner_card
        if not owner_card.is_dockable:
            return 'cheat: attempted to dock at something undockable'
        tavolsag = Vector3.distance(player_ship.mover_of().position_of(),
                                    cel.mover_of().position_of())
        if tavolsag > owner_card.dock_range:
            return ('cheat: docking target is valid but far outside docking range '
                    f'{tavolsag}')
        return None

    def jump_now(self, jump_book, target_sector_id: int, alap_toltes: float,
                 under_fire: bool, arrival_transform=None) -> None:
        player = self.user().pilot_of()
        charge_time = alap_toltes * 4 if under_fire else alap_toltes
        jump_book.book_jump_out(player.user_id_of(), target_sector_id, charge_time, [],
                                arrival_transform)
        self.launch_jump(target_sector_id, charge_time, True)

    def party_jump(self, mostani_szektor, target_sector_id: int, player_ids, arrival_transform_by_user_id=None) -> None:
        party = self.user().pilot_of().party()
        if party is None:
            log.error('group jump from a pilot with no group')
            return
        party_members = party.members()
        users_to_jump = [party.leader()]
        for party_member in party_members:
            party_player = party_member.pilot_of()
            if (party_player.location.sector_id == mostani_szektor.id
                and any(ertek == party_player.user_id_of() for ertek in player_ids)):
                users_to_jump.append(party_member)

        charge_time = 0
        anyone_in_combat = False
        for user_to_jump in users_to_jump:
            player_ship = mostani_szektor.ctx.users().ship_of_pilot(
                user_to_jump.pilot_of().user_id_of())
            if player_ship is None:
                continue
            player_charge_time = player_ship.space_subscribe_info().stat_or_default(ObjectStat.FtlCharge)
            charge_time = Maths.max(player_charge_time, charge_time)
            if player_ship.space_subscribe_info().is_in_combat:
                anyone_in_combat = True
        final_charge_time = charge_time * 4 if anyone_in_combat else charge_time

        for user_to_jump in users_to_jump:
            game_protocol = user_to_jump.protocol_of(ProtocolID.Game)
            game_protocol.launch_jump(target_sector_id, final_charge_time, False)
            arrival_transform = None
            if arrival_transform_by_user_id is not None:
                arrival_transform = arrival_transform_by_user_id.get(user_to_jump.pilot_of().user_id_of())
            mostani_szektor.jump_book.book_jump_out(
                user_to_jump.pilot_of().user_id_of(), target_sector_id, final_charge_time, player_ids,
                arrival_transform)

    @property
    def respawn_offer_sent(self) -> bool:
        return self._is_respawn_send

    def _decode_update(self, br, inital_client_message) -> None:
        uzenet = inital_client_message
        elso = True
        while br.can_read:
            if not elso:
                uzenet = _ClientMessage.from_code(br.read_uint16())
            elso = False

            if (sajat_kezelo := self._handlers.get(uzenet)) is not None:
                sajat_kezelo.handle(br)
                continue
            kezelo = self.KOTEGELT.get(uzenet)
            if kezelo is None:
                log.error('batched message of an unknown kind: %s', uzenet)
                continue
            getattr(self, kezelo)(br)

    def _on_batched_loot(self, br) -> None:
        br.read_uint32()
        log.error('request from a path believed dead: %s %s', _ClientMessage.Loot, self.user().user_log())

    def _on_batched_who_is(self, br) -> None:
        br.read_uint32()
        log.error('request from a path believed dead: %s %s', _ClientMessage.WhoIs, self.user().user_log())

    def _on_batched_un_subscribe_info(self, br) -> None:
        object_id = br.read_uint32()
        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.has_a_sector():
            return
        sector = sec_player_ship.sector()
        obj_to_unsup_at = sector.ctx.space_objects().get(object_id)
        if obj_to_unsup_at is None:
            return
        obj_to_unsup_at.space_subscribe_info().remove_subscriber(self)

    def _on_batched_subscribe_info(self, br) -> None:
        object_id = br.read_uint32()
        sector = self._resolve_sector()
        if sector is None:
            return
        obj_to_sub_at = sector.ctx.space_objects().get(object_id)
        if obj_to_sub_at is None:
            return
        obj_to_sub_at.space_subscribe_info().watch_with(self)

    def _on_batched_move_info(self, br) -> None:
        tomb = br.read_uint32_array()

    def _on_batched_lock_target(self, br) -> None:
        sec_player_ship = self._locate_ship_in_sector()
        target_chosen_by_player = br.read_uint32()
        if not sec_player_ship.has_player_ship:
            return
        sec_player_ship.player_ship.space_subscribe_info().target_object_id = target_chosen_by_player
        self._capital_autofire_on_lock(sec_player_ship, target_chosen_by_player)

    def _on_batched_cast_slot_ability(self, br) -> None:
        ability_id = br.read_uint16()
        target_ids = tuple(br.read_uint32_array())
        player = self.user().pilot_of()
        if player.location.game_location not in _SPACE_COMBAT_LOCATIONS:
            log.warning('%sability request from outside space; their location was %s',
                        self.user().user_log(), player.location.game_location)
            return
        sec_player_ship = self._locate_ship_in_sector()
        sector = sec_player_ship.sector()
        if sec_player_ship.has_player_ship:
            rekeszek = sec_player_ship.player_ship.space_subscribe_info().ship_slots
            if rekeszek is not None:
                slot = rekeszek.slot(ability_id)
                log.debug("user=%s, CastSlotAbility id=%s, target_ids=%s, slot=%s",
                         self.user().user_log(), ability_id, target_ids, slot)
        player_id = player.user_id_of()
        enqueued_ms = now_ms()
        callback = lambda: self._apply_cast_slot_ability_command(
            sector, player_id, ability_id, target_ids, enqueued_ms)
        if not self._enqueue_player_sector_command(sector, callback, "cast_slot_ability"):
            callback()

    def _on_batched_cast_immutable_slot_ability(self, br) -> None:
        ability_id = br.read_uint16()
        target_ids = br.read_uint32_array()
        player = self.user().pilot_of()
        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.pair_complete():
            log.error('immutable-slot cast with neither half resolved %s', sec_player_ship)
            return
        sector = sec_player_ship.sector()
        player_ship = sector.ctx.users().ship_of_pilot(player.user_id_of())
        if player_ship is None or len(target_ids) != 1:
            return
        if (target_obj := sector.ctx.space_objects().get(target_ids[0])) is not None:
            viszony = relation(
                player_ship, target_obj,
                sector.ctx.blueprint().sector_cards().regulation_card().target_bracket_mode)
            if viszony == Stance.Friend:
                self._queue_wire_maneuver(player_ship, FollowManeuver(target_obj), sector)

    def _resolve_player_ship_in_sector(self, sector, player_id):
        return sector.ctx.users().ship_of_pilot(player_id)

    @staticmethod
    def _mark_ability_request(cast_request, enqueued_ms: float) -> None:
        cast_request.mark_enqueued(enqueued_ms)

    def _add_auto_ability_request(self, sector, player_ship, ability_id: int, target_ids, enqueued_ms: float) -> None:
        cast_request = CastOrder(player_ship, ability_id, True, *target_ids)
        self._mark_ability_request(cast_request, enqueued_ms)
        sector.cast_desk.arm_auto_cast(cast_request)

    def _add_manual_ability_request(self, sector, player_ship, ability_id: int, target_ids, enqueued_ms: float) -> None:
        cast_request = CastOrder(player_ship, ability_id, False, *target_ids)
        self._mark_ability_request(cast_request, enqueued_ms)
        sector.cast_desk.enqueue_cast(cast_request)

    def _apply_toggle_ability_on_command(
            self, sector, player_id: int, ability_id: int, target_ids, enqueued_ms: float) -> None:
        player_ship = self._resolve_player_ship_in_sector(sector, player_id)
        if player_ship is None:
            return
        action_type = self._get_slot_action_type(player_ship, ability_id)
        if action_type == AbilityActionKind.Fortify and player_ship.world_state_of().is_fortified:
            sector.cast_desk.disarm_auto_cast(ability_id, player_ship.id_in_space())
            self._deactivate_fortify(sector, player_ship, ability_id)
            return
        self._add_auto_ability_request(sector, player_ship, ability_id, target_ids, enqueued_ms)

    def _apply_update_ability_targets_command(
            self, sector, player_id: int, ability_id: int, target_ids, enqueued_ms: float) -> None:
        player_ship = self._resolve_player_ship_in_sector(sector, player_id)
        if player_ship is None:
            return
        sector.cast_desk.disarm_auto_cast(ability_id, player_ship.id_in_space())
        self._add_auto_ability_request(sector, player_ship, ability_id, target_ids, enqueued_ms)

    def _apply_toggle_ability_off_command(self, sector, player_id: int, ability_id: int) -> None:
        player_ship = self._resolve_player_ship_in_sector(sector, player_id)
        if player_ship is None:
            return
        sector.cast_desk.disarm_auto_cast(ability_id, player_ship.id_in_space())
        self._handle_toggled_ability_off(sector, player_ship, ability_id)

    def _apply_cast_slot_ability_command(
            self, sector, player_id: int, ability_id: int, target_ids, enqueued_ms: float) -> None:
        player_ship = self._resolve_player_ship_in_sector(sector, player_id)
        if player_ship is None:
            return
        if (ship_slots := player_ship.space_subscribe_info().ship_slots) is None:
            return
        action_type = self._get_slot_action_type(player_ship, ability_id)
        if action_type == AbilityActionKind.ToggleStealth:
            if player_ship.world_state_of().is_cloaked:
                sector.cast_desk.disarm_auto_cast(
                    ability_id, player_ship.id_in_space())
                self._set_cloaked_and_broadcast(sector, player_ship, False)
            else:
                self._add_auto_ability_request(sector, player_ship, ability_id, target_ids, enqueued_ms)
        elif action_type == AbilityActionKind.Fortify:
            if player_ship.world_state_of().is_fortified:
                sector.cast_desk.disarm_auto_cast(
                    ability_id, player_ship.id_in_space())
                self._deactivate_fortify(sector, player_ship, ability_id)
            else:
                self._add_auto_ability_request(sector, player_ship, ability_id, target_ids, enqueued_ms)
        else:
            self._add_manual_ability_request(sector, player_ship, ability_id, target_ids, enqueued_ms)

    def _enqueue_player_sector_command(self, sector, callback, description: str, coalesce_key=None) -> bool:
        command_queue_getter = getattr(sector, "command_queue_of", None)
        if not callable(command_queue_getter):
            return False
        command_queue = command_queue_getter()
        if coalesce_key is not None:
            enqueue_coalesced = getattr(command_queue, "enqueue_player_input_coalesced", None)
            if callable(enqueue_coalesced):
                enqueue_coalesced(callback, coalesce_key, description, "GameProtocol")
                return True
        command_queue.enqueue_player_input(callback, description, "GameProtocol")
        return True

    def _queue_wire_maneuver(self, space_object, maneuver, sector=None) -> None:
        if space_object is None or maneuver is None:
            return

        def _apply() -> None:
            space_object.mover_of().queue_maneuver(maneuver)
            space_object.visibility_of().settle_ghost_jump()

        coalesce_key = ("movement", space_object.id_in_space())
        if sector is not None and self._enqueue_player_sector_command(sector, _apply, "movement", coalesce_key):
            return
        _apply()

    def _note_updown_input(self, space_object) -> None:
        space_object.mover_of().flag_movement_dirty()
        space_object.visibility_of().settle_ghost_jump()

    def dock_now(self, mar_halott: bool, operator_rights: bool = False) -> None:
        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.pair_complete():
            log.info("dock_procedure, sec_player_ship not both present=%s, is_already_dead=%s, is_admin=%s",
                     sec_player_ship, mar_halott, operator_rights)
            mar_halott = True
        player_ship = sec_player_ship.player_ship
        sector = sec_player_ship.sector()

        self._is_respawn_send = False
        if self._dock_future is not None and not self._dock_future.settled:
            self._dock_future.call_off()

        dock_delay = 0
        if not mar_halott:
            is_in_combat = player_ship.space_subscribe_info().is_in_combat
            is_zero_rule = operator_rights or not is_in_combat
            ship_tier = player_ship.ship_card_of().tier
            dock_delay = 0 if is_zero_rule else 10 * ship_tier
        self.user().send(self._writer.docking_delay(dock_delay))

        def _dokkolas_kesz():
            if not mar_halott:
                sector.departures_desk.note_removal_cause(player_ship, DepartureCause.Dock)
            scene_protocol = self.user().protocol_of(ProtocolID.Scene)
            current_location = self.user().pilot_of().location
            if current_location.sector_id == 0 or current_location.sector_id == 6:
                current_location.switch_state(InCic(current_location))
            else:
                if mar_halott:
                    current_location.switch_state(AtOutpost(current_location, SceneChange.Die))
                else:
                    current_location.switch_state(AtOutpost(current_location))
            capital_released = self._release_capital_ship_after_death() if mar_halott else False
            scene_protocol.push_scene_change()
            if mar_halott and not capital_released:
                active_stats = self.user().pilot_of().hangar_of().active_ship().ship_stats()
                max_hp = active_stats.stat_or_default(ObjectStat.MaxHullPoints)
                from rebsgo.helpers.floats import f32
                new_hp = f32(max_hp * 0.25)
                active_stats.set_hull(new_hp)

        self._dock_future = self.ctx.timetable.after(int(dock_delay), _dokkolas_kesz)
        if not mar_halott:
            player_ship.world_state_of().mark_docking(True)

    def _resolve_sector(self):
        if self.user() is None:
            return None
        player = self.user().pilot_of()
        return self._sector_book.sector_by_id(player.sector_id)

    def _ship_of_pilot(self, sector):
        return sector.ctx.users().ship_of_pilot(self.user().pilot_of().user_id_of())

    _CARGO_LOOT_SECONDS = claim_rules().cargo_loot_seconds

    def _handle_cargo_interaction(self, cargo_object_id: int, interaction) -> None:
        from rebsgo.world.objects.bodies import CargoInteractionResult

        sec_player_ship = self._locate_ship_in_sector()
        if not sec_player_ship.has_a_sector() or sec_player_ship.player_ship is None:
            return
        sector = sec_player_ship.sector()
        player_ship = sec_player_ship.player_ship

        cargo = sector.ctx.space_objects().get(cargo_object_id)
        if cargo is None or not isinstance(cargo, CargoObject) or cargo.is_removed():
            self.user().send(self._writer.cargo_interaction_result(
                CargoInteractionResult.Lost, cargo_object_id))
            return

        tavolsag = player_ship.mover_of().position_of().distance_(
            cargo.mover_of().position_of())
        if tavolsag > cargo.range:
            self.user().send(self._writer.cargo_interaction_result(
                CargoInteractionResult.Range, cargo_object_id))
            return

        if interaction != CargoObject.Interaction.Loot:
            return

        self.user().send(self._writer.cargo_interaction_wait(
            cargo_object_id, GameProtocol._CARGO_LOOT_SECONDS * 1000))

        user = self.user()

        def _zsakmany_landol():
            try:
                if cargo.is_removed():
                    return
                re_sps = self._locate_ship_in_sector()
                if not re_sps.has_a_sector() or re_sps.sector() is not sector or re_sps.player_ship is None:
                    return
                re_ship = re_sps.player_ship
                re_dist = re_ship.mover_of().position_of().distance_(
                    cargo.mover_of().position_of())
                if re_dist > cargo.range:
                    user.send(self._writer.cargo_interaction_result(
                        CargoInteractionResult.Range, cargo_object_id))
                    return
                zsakmany = sector.loot_ownership.take_out(cargo)
                if zsakmany is None:
                    user.send(self._writer.cargo_interaction_result(
                        CargoInteractionResult.Lost, cargo_object_id))
                    return
                sector.spoils_split.cargo_loot(user, cargo, zsakmany)
                sector.departures_desk.note_removal_cause(
                    cargo, DepartureCause.Collected, GameProtocol._CARGO_LOOT_SECONDS)
                user.send(self._writer.cargo_interaction_result(
                    CargoInteractionResult.Success, cargo_object_id))
            except Exception:
                log.exception("cargo loot completion failed for %s", cargo_object_id)

        self.ctx.timetable.after(GameProtocol._CARGO_LOOT_SECONDS, _zsakmany_landol)

    def _locate_ship_in_sector(self) -> ShipInSector:
        sector = self._resolve_sector()
        if sector is None:
            return ShipInSector.NO_SECTOR
        return ShipInSector(sector, self._ship_of_pilot(sector))

    def _release_capital_ship_after_death(self) -> bool:
        try:
            player_protocol = self.user().protocol_of(ProtocolID.Pilot)
            if player_protocol is None:
                return False
            return player_protocol.release_capital_ship_after_death()
        except Exception:
            log.exception("capital death release failed")
            return False

    def scan(self, object_id: int, banyaszott, is_minable: bool, mining_price, visszatoltes, sector_id: int):
        bw = self._writer.scan(object_id, banyaszott, is_minable, mining_price, visszatoltes)
        if (sector := self._sector_book.sector_by_id(sector_id)) is not None:
            sector.mining_sector_operations.book_mining(self._user_id, object_id, mining_price)
        return bw

    def launch_jump(self, sector_id: int, cooldown: float, lone_jump: bool) -> None:
        self._jump_target_sector_id = sector_id
        csillag = self.ctx.galaxy.map_card.stars.get(sector_id)
        if csillag is None:
            log.error(f'no such sector on this server {sector_id} - nothing to jump toward')
            return
        self._jump_target_sector_guid = csillag.sector_guid
        self._is_jumping = True
        bw = self._writer.jump(
            cooldown=cooldown, is_solo_jump=lone_jump,
            star_guid=self.ctx.galaxy.map_card.stars.get(sector_id).sector_guid)
        self.user().send(bw)

    def push_respawn_choices(self) -> bool:
        if self.user() is None or not self.user().is_connected():
            is_user_null = self.user() is None
            is_user_disconnected = False
            if not is_user_null:
                is_user_disconnected = self.user().is_connected()
            log.error('respawn choices asked for a pilot who is not here: %s, connected=%s', is_user_null, is_user_disconnected)
            return False
        player = self.user().pilot_of()
        self._is_respawn_send = True
        carrier_ids = []
        respawn_locations = []

        stars = self.ctx.galaxy.map_card.stars
        my_sector = stars.get(player.sector_id)
        opposing_side = self.user().pilot_of().faction.opposing_side()

        jeloltek = [map_star_desc for map_star_desc in stars.values()
                    if not GalaxyMapCard.is_base_sector(opposing_side, map_star_desc.id)]
        sorted_stars = sorted(jeloltek,
                              key=lambda o: Vector2.sub(my_sector.position_of(), o.position_of()).magnitude())

        for map_star_desc in sorted_stars:
            if len(respawn_locations) >= 2:
                break
            sector = self._sector_book.sector_by_id(map_star_desc.id)
            if sector is None:
                continue
            tmp_respawn_sector = sector
            if GalaxyMapCard.is_base_sector(player.faction, tmp_respawn_sector.id):
                respawn_locations.append(map_star_desc.id)
                carrier_ids.append(0)
            else:
                op_state = tmp_respawn_sector.colonial_op_state if player.faction == Faction.Colonial \
                    else tmp_respawn_sector.cylon_op_state
                is_op = op_state.is_outpost_cached
                if not is_op:
                    continue
                respawn_locations.append(map_star_desc.id)
                carrier_ids.append(0)
        self._last_respawn_options.set(RespawnChoices(respawn_locations, carrier_ids))
        return self.user().send(self._writer.spawn_options(respawn_locations, carrier_ids))

    @property
    def complete_jump_flag(self) -> GuardedFlag:
        return self._complete_jump_flag

    def flush_property_buffer(self, property_buffer) -> bool:
        if self.user() is None or not self.user().is_connected():
            log.warning('base properties going out to a pilot who is not here')
            return False
        bw = self._writer.space_property_buffer(property_buffer)
        return self.user().send(bw)

    def user_id(self) -> int:
        return self._user_id

    def jump_out_completed(self, player_ids) -> None:
        self._jump_companions = player_ids

    @property
    def last_respawn_options(self) -> GuardedCell:
        return self._last_respawn_options
