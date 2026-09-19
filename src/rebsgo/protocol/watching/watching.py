# github.com/Shran21

from __future__ import annotations

from rebsgo.pilots.state.watching import PilotInfoWatcher
from rebsgo.world.capitals.capital_ship_cards import send_capital_ship_cards_for_guids
import logging
from enum import Enum
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.messages import WatchReply
from rebsgo.protocol.reply_base import ReplyBase
from rebsgo.vocabulary.world import PlaceKind


class LevelWatch(PilotInfoWatcher):
    def __init__(self, user, subscribe_protocol):
        super().__init__(user, subscribe_protocol)

    def on_update(self, player_id: int, info_type, ertek) -> None:
        self.user.send(self.subscribe_protocol_write_only.player_level(player_id, ertek))


class MedalWatch(PilotInfoWatcher):
    def __init__(self, user, subscribe_protocol):
        super().__init__(user, subscribe_protocol)

    def on_update(self, player_id: int, info_type, erem_allas) -> None:
        self.user.send(self.subscribe_protocol_write_only.player_medal(player_id, erem_allas))


class PlaceWatch(PilotInfoWatcher):
    def __init__(self, user, subscribe_protocol):
        super().__init__(user, subscribe_protocol)

    def on_update(self, player_id: int, info_type, location) -> None:
        self.user.send(self.subscribe_protocol_write_only.player_location(player_id, location.location))


class ShipWatch(PilotInfoWatcher):
    def __init__(self, user, subscribe_protocol):
        super().__init__(user, subscribe_protocol)

    def on_update(self, player_id: int, info_type, hangar_valtozas) -> None:
        send_capital_ship_cards_for_guids(self.user, hangar_valtozas.ship_guids)
        self.user.send(self.subscribe_protocol_write_only.player_ships(player_id, hangar_valtozas))

log = logging.getLogger(__name__)


class ClanWatch(PilotInfoWatcher):
    def __init__(self, user, figyelo_valaszok):
        super().__init__(user, figyelo_valaszok)

    def on_update(self, player_id: int, info_type, guild) -> None:
        if guild is not None:
            try:
                self.user.send(self.subscribe_protocol_write_only.player_guild(player_id, guild))
            except ValueError as hiba:
                log.error('%s guild notice undeliverable: %s',
                          self.user.user_log(), hiba)


class InfoKind(Enum):
    Name = 1
    Faction = 2
    Avatar = 4
    Wing = 8
    Ships = 16
    Status = 32
    Level = 64
    Title = 128
    Place = 256
    Medal = 512
    Stats = 1024
    Logout = 2048
    TournamentIndicator = 4096

    @classmethod
    def from_code(cls, value: int) -> "InfoKind | None":
        return _BY_VALUE.get(value)

_BY_VALUE = {member.value: member for member in InfoKind}


class WatchReplies(ReplyBase):
    UZENETEK = {
        "player_logout": (
            WatchReply.PlayerLogout.value,
            [("uint32", "user_id"), ("long_date_time", "logout_date")]),
        "player_title": (
            WatchReply.PlayerTitle.value,
            [("uint32", "user_id"), ("guid", "title_guid")]),
        "player_status": (
            WatchReply.PlayerStatus.value,
            [("uint32", "user_id"), ("boolean", "is_online")]),
        "player_level": (
            WatchReply.PlayerLevel.value,
            [("uint32", "user_id"), ("byte", "level")]),
        "player_name": (
            WatchReply.PilotName.value,
            [("uint32", "user_id"), ("string", "user_name")]),
        "player_avatar": (
            WatchReply.PilotAvatar.value,
            [("uint32", "user_id"), ("desc", "avatar_description")]),
        "player_faction": (WatchReply.PilotFaction.value, [('uint32', 'user_id'), ('byte', 'faction.value')]),
    }

    def __init__(self):
        super().__init__(ProtocolID.Subscribe)

    def space_property_buffer(self, property_buffer):
        bw = self.new_message()
        bw.write_msg_type(WatchReply.PlayerStats.value)
        bw.write_uint32(property_buffer.owner.owner_id)
        bw.write_desc(property_buffer)
        return bw

    def player_medal(self, user_id: int, erem_allas):
        bw = self.new_message()
        bw.write_msg_type(WatchReply.PlayerMedal.value)
        bw.write_uint32(user_id)
        bw.write_byte(erem_allas.pvp_medal.value)
        bw.write_byte(erem_allas.tournament_medal.value)
        bw.write_byte(erem_allas.killer_medal.value)
        bw.write_byte(erem_allas.assist_medal.value)
        return bw

    def player_location(self, player_id: int, location):
        game_location = location.game_location
        sector_guid = location.sector_guid
        room_guid = location.room_guid()
        bw = self.new_message()
        bw.write_msg_type(WatchReply.PlayerLocation.value)
        bw.write_uint32(player_id)
        bw.write_byte(game_location.value)
        if game_location in (PlaceKind.Space, PlaceKind.Story, PlaceKind.Arena,
                             PlaceKind.BattleSpace, PlaceKind.Tournament, PlaceKind.Zone):
            bw.write_guid(sector_guid)
        elif game_location == PlaceKind.Room:
            bw.write_guid(sector_guid)
            bw.write_guid(room_guid)
        return bw

    def player_ships(self, user_id: int, hangar_valtozas):
        bw = self.new_message()
        bw.write_msg_type(WatchReply.PlayerShips.value)
        bw.write_uint32(user_id)
        bw.write_string(hangar_valtozas.ship_name)
        bw.write_uint32_collection(hangar_valtozas.ship_guids)
        return bw

    def player_guild(self, user_id: int, klan):
        if klan is None:
            raise TypeError('the clan is required to say who someone is in it')
        member_info = klan.guild_member_info_of(user_id)
        if member_info is None:
            raise ValueError('guild member record would not read')
        bw = self.new_message()
        bw.write_msg_type(WatchReply.PilotClan.value)
        bw.write_uint32(user_id)
        bw.write_uint32(klan.id)
        bw.write_uint32(member_info.player_role.value)
        bw.write_string(klan.name)
        return bw
