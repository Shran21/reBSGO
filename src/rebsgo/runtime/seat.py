# github.com/Shran21

from __future__ import annotations

import logging

from rebsgo.pilots.state.whereabouts import Offline
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.vocabulary.world import PlaceKind, SceneChange
from rebsgo.helpers.locks import ReentrantLock
from rebsgo.helpers.log_tags import tag

log = logging.getLogger(__name__)


class Seat:
    def __init__(self, connection, player, protocol_desk, session):
        self._lock = ReentrantLock()
        if connection is None:
            raise TypeError('a seat needs the line it sits on')
        self._connection = connection
        if player is None:
            raise TypeError('a seat needs the pilot sitting in it')
        self._player = player
        tag("userID", str(player.user_id_of()))
        if protocol_desk is None:
            raise TypeError('a seat needs its protocol desk')
        self._protocol_desk = protocol_desk
        if session is None:
            raise TypeError('a seat needs its session')
        self._session = session
        self._user_disconnected_subscriber = None
        self._socket_address = None
        self._last_account_safe = None
        self._space_objects_sent_once = False


    @staticmethod
    def of_playerless(karakter_nelkuli, player) -> "Seat":
        return Seat(karakter_nelkuli.connection(), player, karakter_nelkuli.protocol_desk,
                    karakter_nelkuli.session())

    def pilot_of(self):
        return self._player

    def user_log(self) -> str:
        return self._player.player_log + " " + ("" if self._connection is None
                                               else self._connection.pretty_address())

    @property
    def user_log_simple(self) -> str:
        return self._player.player_log

    def same_address(self, other: "Seat") -> bool:
        remote_socket_addr = self.pilot_of().last_remote_address
        current_ip_addr = remote_socket_addr[0]
        other_remote_socket_addr = other.pilot_of().last_remote_address
        other_ip_addr = other_remote_socket_addr[0]
        return current_ip_addr == other_ip_addr


    def connection(self):
        with self._lock:
            return self._connection

    def attach_link(self, connection) -> None:
        with self._lock:
            if self.connection() is not None:
                if self._connection != connection:
                    self._session.kapcsolat_elment()
                    if not self._connection.is_closed():
                        self._connection.close_connection('newer connection wins; the older one gets closed out')
            else:
                if self._session is not None and self._session.nyitva:
                    self._session.kapcsolat_elment()
            self._connection = connection
            self._space_objects_sent_once = False
            if self._connection is not None:
                self._socket_address = self._connection.remote_socket_address()
                self._player.note_remote_address(self._socket_address, False)
                self._connection.on_link_closed(self)

    def is_connected(self) -> bool:
        return self._connection is not None and not self._connection.is_closed()

    def send(self, kimenet) -> bool:
        if self._connection is None:
            return False
        send_successful = self._connection.send(kimenet)
        if not send_successful:
            self.attach_link(None)
        return send_successful


    def attach_session(self, hely) -> None:
        with self._lock:
            self._session.kapcsolat_elment()
            self._session = hely

    def session(self):
        with self._lock:
            return self._session


    @property
    def protocol_desk(self):
        return self._protocol_desk

    def protocol_of(self, protocol_id):
        return self._protocol_desk.protocol_of(protocol_id)


    @property
    def was_sent_space_objects(self) -> bool:
        return self._space_objects_sent_once

    def mark_sent_space_objects(self) -> None:
        self._space_objects_sent_once = True

    def reset_sent_space_objects(self) -> None:
        self._space_objects_sent_once = False


    def on_user_gone(self, tavozas_figyelo) -> None:
        self._user_disconnected_subscriber = tavozas_figyelo

    def on_link_gone(self, connection, reason: str) -> None:
        log.info('%s dropped out, reason=%s', self.user_log_simple, reason)
        self.attach_link(None)
        self._player.note_logout()
        self._player.note_remote_address(self._socket_address, True)
        is_in_space = self._player.location.game_location == PlaceKind.Space
        game_protocol = self.protocol_of(ProtocolID.Game)
        is_respawn_send = game_protocol.respawn_offer_sent
        if is_in_space and is_respawn_send:
            game_protocol.dock_now(True)
        self._player.location.switch_state(
            Offline(self._player.location, SceneChange.None_))
        if self._user_disconnected_subscriber is not None:
            self._user_disconnected_subscriber.on_gone(self)


    @property
    def last_account_safe(self):
        return self._last_account_safe

    @last_account_safe.setter
    def last_account_safe(self, safe_record) -> None:
        self._last_account_safe = safe_record


    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self._player == other._player

    def __hash__(self) -> int:
        return hash(self._player)
