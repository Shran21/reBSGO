# github.com/Shran21
from __future__ import annotations

import logging
from enum import Enum

from rebsgo.services import Services
from rebsgo.protocol.wire_base import BgoProtocol
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.vocabulary.world import PlaceKind
from rebsgo.helpers.guarded import GuardedFlag

log = logging.getLogger(__name__)


class _ClientMessage(Enum):
    SceneLoaded = 1
    Disconnect = 2
    StopDisconnect = 3
    QuitLogin = 4

    @staticmethod
    def from_code(uzenet_kod: int):
        return _CM_BY_VALUE.get(uzenet_kod)


class _ServerMessage(Enum):
    LoadNextScene = 1
    DisconnectTimer = 2
    Disconnect = 100


_CM_BY_VALUE = {member.value: member for member in _ClientMessage}


class SceneProtocol(BgoProtocol):
    class DisconnectReason(Enum):
        NotScheduled = 0
        StartTimer = 1
        TimerRunning = 2
        StartDisconnectRequest = 3
        AbortDisconnect = 4

    def __init__(self, ctx):
        super().__init__(ProtocolID.Scene, ctx)
        self._logout_future = None
        self._properly_logged_out = True
        self._scene_loaded_flag = GuardedFlag(False)
        from rebsgo.chat.client.chat_link import ChatLink
        self._chat_api = Services.get(ChatLink)

    def seed_user(self, user) -> None:
        self._logout_future = None
        self._properly_logged_out = False
        super().seed_user(user)

    def read_message(self, msg_type: int, br) -> None:
        client_message = _ClientMessage.from_code(msg_type)
        if client_message is None:
            return

        if client_message == _ClientMessage.SceneLoaded:
            self._scene_loaded_flag.set(True)
            self._offer_daily_bonus()
        elif client_message == _ClientMessage.QuitLogin:
            player = self.user().pilot_of()
            location = player.location
            location.set_location(location.non_disconnect_location(), location.sector_id,
                                  location.sector_guid)
            self.push_scene_change()
        elif client_message == _ClientMessage.StopDisconnect:
            self._abort_logout()
        elif client_message == _ClientMessage.Disconnect:
            game_location = self.user().pilot_of().location.game_location
            if game_location == PlaceKind.Room:
                self._book_logout(15)
            elif game_location == PlaceKind.Space:
                is_in_combat = self.user().pilot_of().hangar_of().active_ship().ship_stats().is_in_combat
                delay = self._logout_delay_in_combat() if is_in_combat else 15
                self._book_logout(delay)
        else:
            log.error(f'scene met a message kind it does not know: {msg_type}')

    def _offer_daily_bonus(self) -> None:
        try:
            from rebsgo.services import Services
            from rebsgo.runtime.daily_bonus_service import LoginStreakService
            Services.get(LoginStreakService).offer_user(self.user())
        except KeyError:
            pass
        except Exception:
            log.exception('the daily reward offer fell over on scene load')

    def _book_logout(self, keses_mp: int) -> None:
        if self._logout_future is not None:
            return

        self.user().send(self.push_disconnect_countdown(keses_mp))

        def _kilepes():
            self.user().send(self.push_disconnect())
            self._logout_future = None

        self._logout_future = self.ctx.timetable.after(keses_mp, _kilepes)

    def _abort_logout(self) -> None:
        if self._logout_future is None or self._logout_future.called_off:
            return

        self._logout_future.call_off()
        self._logout_future = None

    @property
    def logout_underway(self) -> bool:
        return self._logout_future is not None

    @property
    def logout_done(self) -> bool:
        return self._properly_logged_out and self._logout_future is not None

    def _logout_delay_in_combat(self) -> int:
        tier = self.user().pilot_of().hangar_of().active_ship().ship_card_of().tier
        return 45 + tier * 15

    def push_disconnect(self):
        bw = self.new_message()
        bw.write_msg_type(_ServerMessage.Disconnect.value)
        return bw

    def push_disconnect_countdown(self, disconnect_timer: float):
        bw = self.new_message()
        bw.write_msg_type(_ServerMessage.DisconnectTimer.value)
        bw.write_single(disconnect_timer)
        return bw

    def push_scene_change(self) -> None:
        bw = self.new_message()
        location = self.user().pilot_of().location
        if location.game_location == PlaceKind.Disconnect:
            restored = location.non_disconnect_location()
            if restored not in (PlaceKind.Space, PlaceKind.Room, PlaceKind.Starter,
                                PlaceKind.Avatar, PlaceKind.Zone):
                restored = PlaceKind.Room
            log.info("send_load_next_scene: restoring Disconnect location to %s %s",
                     restored, self.user().user_log())
            location.set_location(restored, location.sector_id, location.sector_guid)
        bw.write_msg_type(_ServerMessage.LoadNextScene.value)
        bw.write_desc(location)

        self.user().reset_sent_space_objects()
        self._scene_loaded_flag.set(False)

        community_protocol = self.user().protocol_of(ProtocolID.Community)
        if community_protocol.is_chat_connected:
            jatekos = self.user().pilot_of()
            self._chat_api.send_user_position(jatekos.user_id_of(), location.sector_id,
                                              jatekos.faction.value)

        self.user().send(bw)
