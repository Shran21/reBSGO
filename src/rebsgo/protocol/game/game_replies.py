# github.com/Shran21
from __future__ import annotations

from rebsgo.wire.bytes.wire_out import WireOut
from rebsgo.protocol.messages import GameReply
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.reply_base import ReplyBase
from rebsgo.vocabulary.pilot import FactionGroup, ResourceKind
from rebsgo.native.hotpath import (
    encode_combat_info_packet,
    encode_object_left_ids_packet,
    encode_weapon_shot_packet,
)
from rebsgo.gamedata.ship_parts.parts import ShipItemBody


class GameReplies(ReplyBase):
    UZENETEK = {
        "docking_delay": (
            GameReply.DockingDelay.value,
            [("single", "delay")]),
        "space_object_state": (
            GameReply.ObjectState.value,
            [("desc", "space_object_state")]),
        "flare_released": (
            GameReply.FlareReleased.value,
            [("uint32", "object_id")]),
        "missile_decoyed": (
            GameReply.MissileDecoyed.value,
            [("uint32", "missile_object_id")]),
        "collide": (GameReply.Collide.value, []),
        "time_origin": (GameReply.TimeOrigin.value, [("int64", "ms")]),
        "object_left": (
            GameReply.ObjectLeft.value,
            [("desc_collection", "object_left_descriptions")]),
        "stop_group_jump": (
            GameReply.StopGroupJump.value,
            [("uint32", "player_id")]),
        "leader_stop_group_jump": (GameReply.LeaderStopGroupJump.value, []),
        "cast": (
            GameReply.Cast.value,
            [("uint16", "slot_id"), ("byte", 0), ("byte", 1)]),
        "stop_slot_ability": (
            GameReply.StopSlotAbility.value,
            [("uint16", "slot_id")]),
        "virus_blocked": (GameReply.VirusBlocked.value, [("uint32", 0)]),
        "stop_jump": (GameReply.StopJump.value, []),
        "changed_player_speed": (
            GameReply.ChangedPlayerSpeed.value,
            [("single", "speed")]),
        "mine_field_explosions": (
            GameReply.MineField.value,
            [("uint32", 0), ("uint32", "object_id")]),
        "spawn_options": (GameReply.RespawnChoices.value, [('uint32_collection', 'sector_ids'), ('uint32_collection', 'carrier_player_ids')]),
        "jump": (GameReply.FTLCharge.value, [('single', 'cooldown'), ('guid', 'star_guid'), ('boolean', 'is_solo_jump')]),
        "outpost_state_broadcast": (GameReply.OutpostStateBroadcast.value, [('uint16', 'colonial_op_points'), ('single', 'colonial_op_delta'), ('uint16', 'cylon_op_points'), ('single', 'cylon_op_delta')]),
        "update_roles": (GameReply.UpdateRoles.value, [('uint32', 'user_id'), ('uint32', 'roles.value')]),
    }

    def __init__(self):
        super().__init__(ProtocolID.Game)

    def cargo_interaction_wait(self, cargo_object_id: int, duration_ms: int):
        from rebsgo.world.objects.bodies import CargoInteractionResult
        bw = self.new_message()
        bw.write_msg_type(GameReply.CargoInteraction.value)
        bw.write_byte(CargoInteractionResult.Wait.value)
        bw.write_uint32(cargo_object_id)
        bw.write_uint32(duration_ms)
        return bw

    def cargo_interaction_result(self, result, cargo_object_id: int):
        result_value = result.value if hasattr(result, "value") else int(result)
        bw = self.new_message()
        bw.write_msg_type(GameReply.CargoInteraction.value)
        bw.write_byte(result_value)
        bw.write_uint32(cargo_object_id)
        return bw

    def who_is(self, space_object, player_visibility_override=None):
        bw = self.new_message()
        bw.write_msg_type(GameReply.WhoIs.value)
        bw.write_uint32(space_object.id_in_space())
        if player_visibility_override is not None and hasattr(space_object, "write_with_visibility_override"):
            space_object.write_with_visibility_override(bw, player_visibility_override)
        else:
            bw.write_desc(space_object)
        return bw

    def move(self, space_object, coalescable: bool = True):
        object_id = space_object.id_in_space()
        maneuver = space_object.mover_of().current_maneuver
        bw = self.new_message()
        bw.write_msg_type(GameReply.Move.value)
        bw.write_uint32(object_id)
        bw.write_desc(maneuver)
        if not coalescable:
            return self._mark_sender_priority(bw, "interactive")
        return self._mark_movement_coalescable(bw, object_id)

    def initial_move(self, space_object):
        return self.move(space_object, coalescable=False)

    def sync_move(self, space_object, coalescable: bool = True):
        mozgato = space_object.mover_of()
        object_id = space_object.id_in_space()
        tick = mozgato.frame_tick
        movement_frame = mozgato.frame
        maneuver = mozgato.current_maneuver
        bw = self.new_message()
        bw.write_msg_type(GameReply.SyncMove.value)
        bw.write_uint32(object_id)
        bw.write_desc(tick)
        bw.write_desc(movement_frame)
        bw.write_desc(maneuver)
        if not coalescable:
            return self._mark_sender_priority(bw, "interactive")
        return self._mark_movement_coalescable(bw, object_id)

    def initial_sync_move(self, space_object):
        return self.sync_move(space_object, coalescable=False)

    @staticmethod
    def _mark_movement_coalescable(bw, object_id: int):
        bw._rebsgo_coalesce_key = ("game-movement", object_id)
        bw._rebsgo_sender_priority = "snapshot"
        return bw

    @staticmethod
    def _mark_sender_priority(bw, priority: str):
        bw._rebsgo_sender_priority = priority
        return bw

    def scan(self, object_id: int, banyaszott, is_minable: bool, mining_price, visszatoltes):
        bw = self.new_message()
        bw.write_msg_type(GameReply.Scan.value)
        bw.write_uint32(object_id)
        if banyaszott is None or banyaszott.card_guid_of() == ResourceKind.None_.guid:
            ShipItemBody.write_none(bw)
        else:
            ShipItemBody.to_wire(bw, banyaszott)
        bw.write_boolean(is_minable)
        bw.write_desc(mining_price)
        bw.write_date_time(visszatoltes)
        return bw

    def weapon_shot(self, from_obj_id: int, kilovo_pont: int, target_obj_id: int, weapon_fx_type):
        native_packet = encode_weapon_shot_packet(
            self.protocol_id.value,
            GameReply.WeaponShot.value,
            from_obj_id,
            kilovo_pont,
            target_obj_id,
            weapon_fx_type.value,
        )
        if native_packet is not None:
            return WireOut.from_frozen_bytes(native_packet)

        return (self.new_message()
                .write_msg_type(GameReply.WeaponShot.value)
                .write_uint32(from_obj_id)
                .write_uint16(kilovo_pont)
                .write_uint32(target_obj_id)
                .write_byte(weapon_fx_type.value))

    def object_left_ids(self, object_ids, removing_cause):
        native_packet = encode_object_left_ids_packet(
            self.protocol_id.value,
            GameReply.ObjectLeft.value,
            object_ids,
            removing_cause.byte_value,
        )
        if native_packet is not None:
            return WireOut.from_frozen_bytes(native_packet)

        bw = self.new_message()
        bw.write_msg_type(GameReply.ObjectLeft.value)
        bw.write_length(len(object_ids))
        for object_id in object_ids:
            bw.write_uint32(object_id)
            bw.write_int32(0)
            bw.write_byte(removing_cause.byte_value)
        return bw

    def combat_info(self, sajat_sebzes: bool, object_id: int, damage: float, wrecked: bool,
                    landed_critical: bool):
        native_packet = encode_combat_info_packet(
            self.protocol_id.value,
            GameReply.CombatInfo.value,
            sajat_sebzes,
            object_id,
            damage,
            wrecked,
            landed_critical,
        )
        if native_packet is not None:
            return WireOut.from_frozen_bytes(native_packet)

        bw = self.new_message()
        bw.write_msg_type(GameReply.CombatInfo.value)
        bw.write_boolean(sajat_sebzes)
        bw.write_uint32(object_id)
        bw.write_single(-damage)
        destroyed_and_critical = 0
        destroyed_and_critical |= 1 if wrecked else 0
        destroyed_and_critical |= 2 if landed_critical else 0
        bw.write_byte(destroyed_and_critical)
        return bw

    def space_property_buffer(self, property_buffer):
        bw = self.new_message()
        bw.write_msg_type(GameReply.Info.value)
        bw.write_uint32(property_buffer.owner.owner_id)
        bw.write_desc(property_buffer)
        return bw

    def switch_visibility_as(self, object_id: int, lathatosag):
        return self.switch_visibility(object_id, lathatosag.is_visible(),
                                      lathatosag.change_visibility_reason)

    def switch_visibility(self, object_id: int, is_visible: bool, change_visibility_reason):
        bw = self.new_message()
        bw.write_msg_type(GameReply.ChangeVisibility.value)
        bw.write_uint32(object_id)
        bw.write_boolean(is_visible)
        bw.write_byte(change_visibility_reason.value)
        return bw

    def update_faction_group(self, object_id: int, uj_frakciocsoport):
        bw = self.new_message()
        bw.write_msg_type(GameReply.UpdateFactionGroup.value)
        bw.write_uint32(object_id)
        bw.write_boolean(uj_frakciocsoport == FactionGroup.Group1)
        return bw
