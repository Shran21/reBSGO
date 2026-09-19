# github.com/Shran21
from __future__ import annotations

import logging
from enum import Enum

from rebsgo.world.capitals.capital_ship_cards import send_capital_ship_cards_for_guids
from rebsgo.pilots.state.pilot_bits import HangarChange
from rebsgo.protocol.wire_base import BgoProtocol
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.watching.watching import ClanWatch
from rebsgo.protocol.watching.watching import InfoKind
from rebsgo.protocol.watching.watching import LevelWatch
from rebsgo.protocol.watching.watching import PlaceWatch
from rebsgo.protocol.watching.watching import MedalWatch
from rebsgo.protocol.messages import WatchReply
from rebsgo.protocol.watching.watching import ShipWatch
from rebsgo.protocol.watching.watching import WatchReplies


log = logging.getLogger(__name__)


class _ClientMessage(Enum):
    Info = 1
    Subscribe = 2
    Unsubscribe = 3
    SubscribeStats = 4
    UnsubscribeStats = 5

    @staticmethod
    def from_code(value: int):
        return _CM_BY_VALUE.get(value)


_CM_BY_VALUE = {member.value: member for member in _ClientMessage}


class SubscribeProtocol(BgoProtocol):
    ADATFAJTAK = {
        InfoKind.Name: "_on_info_name",
        InfoKind.Faction: "_on_info_faction",
        InfoKind.Avatar: "_on_info_avatar",
        InfoKind.Ships: "_on_info_ships",
        InfoKind.Level: "_on_info_level",
        InfoKind.Medal: "_on_info_medal",
        InfoKind.Place: "_on_info_place",
        InfoKind.Wing: "_on_info_wing",
    }

    ServerMessage = WatchReply

    def __init__(self, pilot_roster, ctx):
        super().__init__(ProtocolID.Subscribe, ctx)
        self._pilot_roster = pilot_roster
        self._writer = WatchReplies()

    @property
    def replies(self) -> WatchReplies:
        return self._writer

    def read_message(self, msg_type: int, br) -> None:
        client_message = _ClientMessage.from_code(msg_type)
        this_player = self.user().pilot_of()
        if client_message is None:
            log.error(f'subscribe met a client message it does not know, pilot:{this_player.user_id_of()}')
            return

        if client_message == _ClientMessage.Info:
            self._handle_info(br)
        elif client_message == _ClientMessage.Subscribe:
            self._handle_subscribe(br)
        elif client_message == _ClientMessage.Unsubscribe:
            self._handle_unsubscribe(br, this_player)
        elif client_message == _ClientMessage.SubscribeStats:
            self._handle_subscribe_stats(br, this_player)
        elif client_message == _ClientMessage.UnsubscribeStats:
            self._handle_unsubscribe_stats(br, this_player)
        else:
            log.warning('%ssubscribing %s has no implementation', self.user().user_log(),
                        client_message)

    def _handle_info(self, br) -> None:
        player_id = br.read_uint32()
        flags = br.read_uint32()
        types = SubscribeProtocol.probe_info_types(flags)
        self._answer_info_request(player_id, types)

    def _handle_subscribe(self, br) -> None:
        player_id = br.read_uint32()
        flags = br.read_uint32()
        types = SubscribeProtocol.probe_info_types(flags)
        user = self._pilot_roster.by_id(player_id)
        if user is None:
            return
        user_to_subscribe = user
        for type_ in types:
            if type_ == InfoKind.Name:
                log.error('%s subscribed to something that takes no subscribers %s',
                          self.user().user_log(), type_)
            elif type_ == InfoKind.Level:
                user_to_subscribe.pilot_of().skill_book.watch_with(
                    LevelWatch(self.user(), self._writer))
            elif type_ == InfoKind.Medal:
                user_to_subscribe.pilot_of().player_medals.watch_with(
                    MedalWatch(self.user(), self._writer))
            elif type_ == InfoKind.Wing:
                log.debug('%s subscribing to guild updates', self.user().pilot_of().player_log)
                user_to_subscribe.pilot_of().player_guild.watch_with(
                    ClanWatch(self.user(), self._writer))
            elif type_ == InfoKind.Title:
                pass
            elif type_ == InfoKind.Ships:
                user_to_subscribe.pilot_of().hangar_of().watch_with(
                    ShipWatch(self.user(), self._writer))
            elif type_ == InfoKind.Place:
                user_to_subscribe.pilot_of().location.watch_with(
                    PlaceWatch(self.user(), self._writer))
            else:
                log.error('%s subscribe request named an unknown kind%s', self.user().user_log(),
                          type_)

    def _handle_unsubscribe(self, br, this_player) -> None:
        player_id = br.read_uint32()
        flags = br.read_uint32()
        types = SubscribeProtocol.probe_info_types(flags)
        user = self._pilot_roster.by_id(player_id)
        if user is None:
            return
        user_to_un_subscribe = user
        for type_ in types:
            if type_ == InfoKind.Level:
                user_to_un_subscribe.pilot_of().skill_book.remove_subscriber(this_player.user_id_of())
            elif type_ == InfoKind.Medal:
                user_to_un_subscribe.pilot_of().player_medals.remove_subscriber(this_player.user_id_of())
            elif type_ == InfoKind.Wing:
                user_to_un_subscribe.pilot_of().player_guild.remove_subscriber(this_player.user_id_of())
            elif type_ == InfoKind.Ships:
                user_to_un_subscribe.pilot_of().hangar_of().remove_subscriber(this_player.user_id_of())
            elif type_ == InfoKind.Place:
                user_to_un_subscribe.pilot_of().location.remove_subscriber(this_player.user_id_of())
            elif type_ == InfoKind.Title:
                pass
            else:
                log.error('%sunsubscribing from kind: %s has no implementation',
                          self.user().user_log(), type_)

    def _handle_subscribe_stats(self, br, this_player) -> None:
        player_id = br.read_uint32()
        if (player := self._pilot_roster.by_id(player_id)) is not None:
            active_ship = player.pilot_of().hangar_of().active_ship()
            if player_id == this_player.user_id_of():
                player_protocol = self.user().protocol_of(ProtocolID.Pilot)
                active_ship.ship_stats().watch_with(player_protocol)
            else:
                active_ship.ship_stats().watch_with(self)

    def _handle_unsubscribe_stats(self, br, this_player) -> None:
        player_id = br.read_uint32()
        found_player = self._pilot_roster.by_id(player_id)
        if found_player is not None:
            active_ship = found_player.pilot_of().hangar_of().active_ship()
            if player_id == this_player.user_id_of():
                active_ship.ship_stats().remove_subscriber(self.user().protocol_of(ProtocolID.Pilot))
            else:
                active_ship.ship_stats().remove_subscriber(self)
        else:
            log.warning('%sunsubscribe from a ship that is not around', self.user().user_log())

    def _answer_info_request(self, player_id: int, types) -> None:
        kirol = self._pilot_roster.by_id(player_id)
        if kirol is None:
            return
        for fajta in types:
            kezelo = self.ADATFAJTAK.get(fajta)
            if kezelo is None:
                continue
            getattr(self, kezelo)(player_id, kirol)

    def _on_info_name(self, player_id: int, kirol) -> None:
        self.user().send(self._writer.player_name(player_id, kirol.pilot_of().name))

    def _on_info_faction(self, player_id: int, kirol) -> None:
        self.user().send(
            self._writer.player_faction(player_id, kirol.pilot_of().faction))

    def _on_info_avatar(self, player_id: int, kirol) -> None:
        self.user().send(self._writer.player_avatar(
            player_id, kirol.pilot_of().avatar_description.get()))

    def _on_info_ships(self, player_id: int, kirol) -> None:
        hangar = kirol.pilot_of().hangar_of()
        ship_name = hangar.active_ship().name
        guids = hangar.sorted_guids()
        send_capital_ship_cards_for_guids(self.user(), guids)
        hangar_ships_update = HangarChange(ship_name, guids)
        self.user().send(self._writer.player_ships(player_id, hangar_ships_update))

    def _on_info_level(self, player_id: int, kirol) -> None:
        szint = kirol.pilot_of().skill_book.get()
        self.user().send(self._writer.player_level(player_id, szint))

    def _on_info_medal(self, player_id: int, kirol) -> None:
        medals = kirol.pilot_of().player_medals.get()
        self.user().send(self._writer.player_medal(player_id, medals))

    def _on_info_place(self, player_id: int, kirol) -> None:
        self.user().send(
            self._writer.player_location(player_id, kirol.pilot_of().location))

    def _on_info_wing(self, player_id: int, kirol) -> None:
        if (guild := kirol.pilot_of().guild()) is not None:
            try:
                self.user().send(self._writer.player_guild(player_id, guild))
                self.user().send(self._writer.player_location(
                    player_id, kirol.pilot_of().location))
            except ValueError as hibas_ertek:
                log.error('%scall chain looks off %s', self.user().user_log(), hibas_ertek)
                log.exception("the clan details could not be sent")

    @staticmethod
    def probe_info_types(request_sent: int):
        eredmeny = set()
        for type_ in InfoKind:
            valasz = request_sent & (type_.value & 0xFFFFFFFF)
            if valasz > 0:
                if (extracted := InfoKind.from_code(valasz)) is not None:
                    eredmeny.add(extracted)
        return eredmeny

    def flush_property_buffer(self, property_buffer) -> bool:
        if self.user() is None:
            log.error('property push with no pilot attached')
            return False

        bw = self._writer.space_property_buffer(property_buffer)
        return self.user().send(bw)

    def user_id(self) -> int:
        return self._user_id
