# github.com/Shran21

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from rebsgo.admission import reasons
from rebsgo.admission.gate import BelepesElutasitva
from rebsgo.admission.reasons import reason_of
from rebsgo.helpers.log_tags import tag
from rebsgo.pilots.state.boosts.boost import Boost
from rebsgo.pilots.state.pilot import Pilot
from rebsgo.pilots.state.tallies import AssignmentLog
from rebsgo.protocol.wire_base import BgoProtocol
from rebsgo.protocol.pilot.pilot_replies import PilotReplies
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.reply_base import ReplyBase
from rebsgo.runtime.sessions import GuestSession
from rebsgo.vocabulary.sorszamos_enum import SorszamosEnum
from rebsgo.vocabulary.pilot import BoostKind, BoostSource
import logging


class AdmissionResult:
    def __init__(self, player_id: int, session, is_valid: bool):
        self._player_id = player_id
        self._session = session
        self._is_valid = is_valid

    @staticmethod
    def valid_session(user_id: int, session: str) -> "AdmissionResult":
        return AdmissionResult(user_id, session, True)

    @staticmethod
    def refuse_session(user_id: int = -1) -> "AdmissionResult":
        return AdmissionResult(user_id, None, False)

    @property
    def player_id(self) -> int:
        return self._player_id

    def session(self):
        return self._session

    @property
    def usable(self) -> bool:
        return self._is_valid

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return (self._player_id == other._player_id and self._session == other._session
                and self._is_valid == other._is_valid)

    def __hash__(self) -> int:
        return hash((self._player_id, self._session, self._is_valid))

    def __str__(self) -> str:
        allapot = 'let in' if self._is_valid else 'turned away'
        return f'<pilot {self._player_id} {allapot} on session {self._session}>'


class LoginError(SorszamosEnum):
    Unknown = 0
    AlreadyConnected = 1
    WrongProtocol = 2
    WrongSession = 3
    WrongUserId = 4
    WrongPlayerId = 5
    WrongPlayerName = 6


class LoginProtocolClientMessage(Enum):
    Init = 1
    Pilot = 2
    Echo = 5

    @staticmethod
    def from_code(uzenet_kod: int):
        return _login_protocol_client_message_BY_VALUE.get(uzenet_kod)
_login_protocol_client_message_BY_VALUE = {member.value: member for member in LoginProtocolClientMessage}


class ServerMessage(Enum):
    Hello = 0
    Init = 1
    Error = 2
    Pilot = 3
    Wait = 4
    Echo = 5

    @classmethod
    def from_code(cls, uzenet_kod: int) -> "ServerMessage | None":
        return _server_message_BY_VALUE.get(uzenet_kod)
_server_message_BY_VALUE = {member.value: member for member in ServerMessage}


class LoginReplies(ReplyBase):
    UZENETEK = {
        "srv_revision": (ServerMessage.Init.value, [("uint32", 4578)]),
        "hello": (ServerMessage.Hello.value, []),
        "login_queue": (ServerMessage.Wait.value, [('uint32', 'queue_position')]),
        "login_error": (ServerMessage.Error.value, [('byte', 'login_error.value'), ('string', 'error_message')]),
    }

    def __init__(self):
        super().__init__(ProtocolID.Login)

    def player(self, bgo_admin_roles):
        bw = self.new_message()
        bw.write_uint16(ServerMessage.Pilot.value)
        local_date_time = datetime.now(timezone.utc)
        l = int(local_date_time.timestamp() * 1000)
        (bw
         .write_int32(local_date_time.year)
         .write_int32(local_date_time.month)
         .write_int32(local_date_time.day)
         .write_int32(local_date_time.hour)
         .write_int32(local_date_time.minute)
         .write_int32(local_date_time.second)
         .write_int64(l)
         .write_desc(bgo_admin_roles))
        return bw


log = logging.getLogger(__name__)


class LoginProtocol(BgoProtocol):
    def __init__(self, ctx, kapu, data_store, pilot_roster, protocol_desk,
                 tavozas_figyelo, kuldetes_frissito):
        super().__init__(ProtocolID.Login, ctx)
        self._kapu = kapu
        self._data_store = data_store
        self._pilot_roster = pilot_roster
        self._protocol_desk = protocol_desk
        self._user_disconnected_subscriber = tavozas_figyelo
        self._mission_updater = kuldetes_frissito
        self._writer = LoginReplies()

    @property
    def replies(self) -> LoginReplies:
        return self._writer

    def read_message(self, msg_type: int, br) -> None:
        login_protocol_client_message = LoginProtocolClientMessage.from_code(msg_type)
        if login_protocol_client_message == LoginProtocolClientMessage.Init:
            self.ctx.connection().send(self._writer.srv_revision())
        elif login_protocol_client_message == LoginProtocolClientMessage.Pilot:
            br.read_byte()
            br.read_uint32()
            client_build = br.read_string()

            jegy = br.read_string()

            session_handling_result = self._redeem_ticket(jegy, self.ctx.connection())
            if not session_handling_result.usable:
                log.info('session invalid; admission halts here')
                return

            player_id = session_handling_result.player_id
            tag("userID", str(player_id))
            log.info('admission granted on ticket %s', session_handling_result.session())
            log.info("client build %s", client_build)
            if (not self.ctx.server_config.ignore_client_build
                    and client_build not in self.ctx.server_config.known_client_builds):
                log.warning("pilot %s arrives on an unlisted client build: %s",
                            player_id, client_build)
            hely = session_handling_result.session()
            playerless_user = GuestSession(self.ctx.connection(), hely, self._protocol_desk)
            self._pilot_roster.reserve_bare(player_id, playerless_user)

            ex_user = self._find_returning_user(player_id)

            if ex_user is None:
                log.info('player %s arrives with no account on file', player_id)
                mission_book = AssignmentLog(player_id, self._mission_updater)
                player = Pilot(player_id, self.ctx.server_config, mission_book)
                new_user = self._pilot_roster.pilot_born(player)

                new_user.attach_link(self.ctx.connection())
                new_user.attach_session(hely)
                new_user.on_user_gone(self._user_disconnected_subscriber)
                self.ctx.connection().send(self._writer.player(new_user.pilot_of().bgo_admin_roles))
                new_user.protocol_desk.login_done(new_user)

                end_time = datetime(2024, 1, 1, 0, 0, 0)

                if (not new_user.pilot_of().factors.boosted_by(BoostSource.Holiday)
                    and datetime.now(timezone.utc).replace(tzinfo=None) < end_time):
                    new_user.pilot_of().factors.take_boost(
                        Boost.ending_at(BoostKind.Loot, BoostSource.Holiday, 1.0, end_time))
                    new_user.pilot_of().factors.take_boost(
                        Boost.ending_at(BoostKind.Experience, BoostSource.Holiday, 1.0, end_time))
                    new_user.pilot_of().factors.take_boost(
                        Boost.ending_at(BoostKind.AsteroidYield, BoostSource.Holiday, 1.0, end_time))
                    new_user.send(PilotReplies().factors(new_user.pilot_of().factors))

                community_protocol = new_user.protocol_desk.protocol_of(ProtocolID.Community)
                chat_server_url = self._chat_address_for_client(self.ctx)
                community_protocol.push_chat_session("", 860, "us", chat_server_url)
                community_protocol.push_friend_list()
            else:
                delete_was_pending = self._pilot_roster.release_bare(player_id) is not None
                log.info(f'login name smuggled a delete character: {delete_was_pending}')
                existing_user = ex_user
                self.seed_user(existing_user)

                if len(self.user().protocol_desk.all_protocols()) == 1:
                    self._protocol_desk.login_done(self.user())
                else:
                    self._protocol_desk.restore_registry(self.user())

                setting_protocol = self._protocol_desk.protocol_of(ProtocolID.Setting)
                setting_protocol.push_settings()
                self.user().attach_link(self.ctx.connection())
                self.user().attach_session(hely)
                self.user().send(self._writer.player(self.user().pilot_of().bgo_admin_roles))
                player_protocol = self.user().protocol_of(ProtocolID.Pilot)
                self.user().on_user_gone(self._user_disconnected_subscriber)
                self._protocol_desk.restore_registry(self.user())
                player_protocol.announce_character()
                community_protocol = self._protocol_desk.protocol_of(ProtocolID.Community)
                chat_server_url = self._chat_address_for_client(self.ctx)
                community_protocol.push_chat_session("", 860, "us", chat_server_url)
                community_protocol.push_friend_list()
        elif login_protocol_client_message == LoginProtocolClientMessage.Echo:
            pass
        else:
            log.error("Unknown message_type in LoginProtocol.")

    def _chat_address_for_client(self, ctx) -> str:
        cim = (ctx.server_config.chat_server_address or "").strip()
        if cim not in ("", "127.0.0.1") and cim.lower() != "localhost":
            return cim
        local_address = ctx.connection().local_host_address()
        if local_address.strip() == "":
            return cim
        log.warning("ChatServerUrl was '%s', overriding with local address '%s'", cim, local_address)
        return local_address

    def _redeem_ticket(self, jegy: str, connection) -> AdmissionResult:
        honnan = connection.remote_address()
        if honnan is None:
            connection.send(self._writer.login_error(
                LoginError.WrongSession, "unknown connection"))
            return AdmissionResult.refuse_session()

        try:
            engedely = self._kapu.beengedi(jegy, honnan)
        except BelepesElutasitva as elutasitva:
            log.info('admission turned away from %s - %s', honnan, elutasitva)
            hiba = (LoginError.AlreadyConnected
                    if reason_of(elutasitva) == reasons.ALREADY_ONLINE
                    else LoginError.WrongSession)
            connection.send(self._writer.login_error(hiba, str(elutasitva)))
            return AdmissionResult.refuse_session()

        return AdmissionResult.valid_session(
            engedely.pilota, self._kapu.nevsor.hely(engedely))

    def _find_returning_user(self, user_id: int):
        elo = self._pilot_roster.by_id(user_id)
        if elo is None and self._data_store.user_present(user_id):
            elo = self._pilot_roster.pilot_born(
                self._data_store.stored_pilot(user_id))
        return elo
