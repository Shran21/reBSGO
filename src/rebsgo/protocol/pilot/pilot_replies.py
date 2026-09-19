# github.com/Shran21
from __future__ import annotations

import time

from rebsgo.protocol.messages import PilotReply
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.reply_base import ReplyBase
from rebsgo.vocabulary.pilot import ResourceKind
from rebsgo.gamedata.ship_parts.parts import ShipItemBody


class PilotReplies(ReplyBase):
    UZENETEK = {
        "remove_missions": (
            PilotReply.RemoveMissions.value,
            [("uint16_collection", "remove_ids")]),
        "counters": (PilotReply.Tallies.value, [("desc", "counters")]),
        "experience": (PilotReply.Experience.value, [("uint32", "exp")]),
        "spent_experience": (
            PilotReply.SpentExperience.value,
            [("uint32", "spent_exp")]),
        "skills": (
            PilotReply.Skills.value,
            [("boolean", False), ("desc", "skill_book")]),
        "cannot_stack_boosters": (PilotReply.CannotStackBoosters.value, []),
        "remove_factor_ids": (
            PilotReply.RemoveFactors.value,
            [("uint16_collection", "ids")]),
        "space_property_buffer": (
            PilotReply.Stats.value,
            [("desc", "space_property_buffer")]),
        "character_services": (
            PilotReply.PilotServices.value,
            [("desc", "character_services")]),
        "anchor": (
            PilotReply.Anchor.value,
            [("uint32", "object_id_to_anchor_on")]),
        "un_anchor": (
            PilotReply.Unanchor.value,
            [("uint32", "space_object_id_of_player_ship"),
             ("desc", "unanchor_reason")]),
        "active_player_ship": (PilotReply.ActiveShip.value, [('uint16', 'ship_id')]),
        "reset": (PilotReply.Reset.value, []),
        "name": (PilotReply.Name.value, [('string', 'name_chosen')]),
        "write_id": (PilotReply.ID.value, [('uint32', 'id')]),
        "faction": (PilotReply.Faction.value, [('byte', 'faction.value')]),
    }

    def __init__(self):
        super().__init__(ProtocolID.Pilot)

    def hangar_ship_stats(self, hangar_ship):
        bw = self.new_message()
        bw.write_msg_type(PilotReply.Stats.value)
        ship_stats = hangar_ship.ship_stats().stats_of
        all_stats = ship_stats.all_stats
        bw.write_length(len(all_stats))
        for stat, value in all_stats.items():
            bw.write_byte(1)
            bw.write_uint16(stat.value)
            bw.write_single(value)
        return bw

    def ship_info_durability(self, ship):
        ship_id = ship.server_id
        durability = ship.durability
        bw = self.new_message()
        bw.write_msg_type(PilotReply.ShipInfo.value)
        bw.write_uint16(ship_id)
        bw.write_single(durability)
        return bw

    def ship_sticker_binding(self, hangar_ship):
        bw = self.new_message()
        bw.write_msg_type(PilotReply.Stickers.value)
        bw.write_uint16(hangar_ship.server_id)
        bw.write_desc_collection(hangar_ship.stickers)
        return bw

    def ship_slots(self, hangar_ship):
        bw = self.new_message()
        bw.write_msg_type(PilotReply.Slots.value)
        bw.write_uint16(hangar_ship.server_id)
        rekeszek = list(hangar_ship.ship_slots.pairs)
        bw.write_length(len(rekeszek))
        for _slot_id, rekesz in rekeszek:
            bw.write_desc(rekesz)
        return bw

    def mail_box(self, mail_box):
        if mail_box is None:
            raise TypeError('the mailbox is required')
        bw = self.new_message()
        bw.write_msg_type(PilotReply.Mail.value)
        bw.write_desc(mail_box)
        return bw

    def missions(self, assignments):
        from rebsgo.pilots.state.tallies import AssignmentLog

        bw = self.new_message()
        bw.write_msg_type(PilotReply.Missions.value)
        if isinstance(assignments, AssignmentLog):
            bw.write_desc(assignments)
        else:
            bw.write_desc_collection(assignments)
        return bw

    def merits_cap(self, nyersanyag_hatar):
        if nyersanyag_hatar.guid != ResourceKind.Token.guid:
            raise ValueError('token cap applied to a non-token')
        bw = self.new_message()
        bw.write_msg_type(PilotReply.ResourceHardcap.value)
        bw.write_guid(ResourceKind.Token.guid)
        bw.write_int32(nyersanyag_hatar.farmed)
        bw.write_int32(nyersanyag_hatar.max())
        return bw

    def all_container_items(self, container):
        bw = self.new_message()
        bw.write_desc(container)
        return bw

    def factors(self, boosts):
        from rebsgo.pilots.state.boosts.boosts import Boosts

        bw = self.new_message()
        bw.write_msg_type(PilotReply.Boosts.value)
        if isinstance(boosts, Boosts):
            bw.write_desc(boosts)
        else:
            bw.write_desc_collection(boosts)
        return bw

    def avatar_description(self, avatar_description):
        if avatar_description is None:
            return self._write_empty_avatar_description()
        bw = self.new_message()
        bw.write_uint16(PilotReply.Avatar.value)
        bw.write_desc(avatar_description)
        return bw

    def _write_empty_avatar_description(self):
        bw = self.new_message()
        bw.write_uint16(29)
        bw.write_msg_type(PilotReply.Avatar.value)
        bw.write_uint16(0)
        bw.write_uint16(0)
        bw.write_byte(0)
        return bw

    def character_services_dummy(self, user):
        player = user.pilot_of()
        bw = self.new_message()
        bw.write_msg_type(PilotReply.PilotServices.value)
        current_sector_id = player.sector_id
        bw.write_byte(current_sector_id & 0xFF)
        eligible = False
        bw.write_boolean(eligible)
        bw.write_int64(0)
        now_ms = int(time.time() * 1000)
        cooldown = now_ms - 100000
        last_used = now_ms
        bw.write_int64(cooldown)
        bw.write_int64(cooldown)
        bw.write_int64(last_used)
        bw.write_int64(last_used)
        cubits_price = 100000
        bw.write_single(cubits_price)
        bw.write_single(cubits_price)
        bw.write_length(0)
        return bw

    def dradis_mission_statistics_rewards(self, kuldetes_kezdet: int, kuldetes_vege: int,
                                          max_waves: int, waves_completed: int, kiirtott_ellenseg: int,
                                          ftl_ranks, item_list):
        bw = self.new_message()
        bw.write_msg_type(PilotReply.Statistics.value)
        bw.write_uint32(kuldetes_kezdet)
        bw.write_uint32(kuldetes_vege)
        bw.write_uint32(max_waves)
        bw.write_uint32(waves_completed)
        bw.write_uint32(0)
        bw.write_uint32(kiirtott_ellenseg)
        bw.write_uint32(ftl_ranks.value)
        bw.write_guid(0)
        ShipItemBody.to_wire(bw, item_list)
        return bw
