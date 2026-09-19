# github.com/Shran21
from __future__ import annotations

from contextlib import suppress

import logging
import socket as _socket
import threading

from rebsgo.schedule import TimedCall

log = logging.getLogger(__name__)


class ChatLink:
    RECONNECT_INTERVAL = 1_000
    MAX_RECONNECT_INTERVAL = 4 * 60 * 1_000
    CONNECT_TIMEOUT_MILLIS = 4 * 60 * 1_000

    def __init__(self, server_settings):
        self._server_settings = server_settings
        self._net_socket = None
        self._host = None
        self._port = 0
        self._is_connected = False
        self._reconnect_attempts = 0
        self._reconnect_interval_millisecond = ChatLink.RECONNECT_INTERVAL
        self._reconnect_timer = None
        self._lock = threading.Lock()

    def start(self) -> None:
        self._host = self._server_settings.chat_server_address
        self._port = self._server_settings.chat_server_port
        self._connect()

    def _connect(self) -> None:
        try:
            sock = _socket.create_connection(
                (self._host, self._port), timeout=ChatLink.CONNECT_TIMEOUT_MILLIS / 1000.0)
            sock.settimeout(None)
            log.info('chat backend reached at {}:{}'.format(self._host, self._port))
            with self._lock:
                self._net_socket = sock
                self._is_connected = True
                self._reconnect_attempts = 0
                self._reconnect_interval_millisecond = ChatLink.RECONNECT_INTERVAL
        except OSError as cause:
            log.error('chat backend unreachable: {}'.format(cause))
            self._is_connected = False
            self._reconnect()

    def _reconnect(self) -> None:
        ora = TimedCall(self._reconnect_interval_millisecond / 1000.0, self._on_reconnect_timer)
        with self._lock:
            self._reconnect_timer = ora
        ora.start()
        self._reconnect_attempts += 1
        self._reconnect_interval_millisecond = min(
            self._reconnect_interval_millisecond * 2, ChatLink.MAX_RECONNECT_INTERVAL)

    def _on_reconnect_timer(self) -> None:
        log.info('reattaching to the chat backend (try {})'.format(self._reconnect_attempts + 1))
        self._connect()

    def send_user_position(self, user_id: int, sector_id: int, faction: int = 0) -> None:
        self._send_admin(f'bs%admin@{user_id}@{sector_id}@{faction}#', "position update")

    def squad_membership_changed(self, player_id: int, party_id: int) -> None:
        self._send_admin(f'bs%party@{player_id}@{party_id}#', "party join")

    def party_left(self, player_id: int) -> None:
        self._send_admin(f'bs%party@{player_id}@0#', "party leave")

    def guild_joined(self, player_id: int, guild_id: int) -> None:
        self._send_admin(f'bs%guild@{player_id}@{guild_id}#', "guild join")

    def guild_left(self, player_id: int) -> None:
        self._send_admin(f'bs%guild@{player_id}@0#', "guild leave")

    def _send_admin(self, message: str, what: str) -> None:
        if not self._is_connected or self._net_socket is None:
            log.warning("Cannot send {}: Not connected to chat server".format(what))
            return
        try:
            self._net_socket.sendall(message.encode("utf-8"))
            log.debug("{} sent successfully".format(what))
        except OSError as cause:
            log.error("Failed to send {}: {}".format(what, cause))
            self._is_connected = False
            self._reconnect()

    def stop(self) -> None:
        with self._lock:
            if self._reconnect_timer is not None:
                self._reconnect_timer.call_off()
            if self._net_socket is not None:
                with suppress(OSError):
                    self._net_socket.close()
