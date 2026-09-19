# github.com/Shran21
from __future__ import annotations

from contextlib import suppress

import logging
import socket as _socket
import threading

from rebsgo.helpers.guarded import GuardedFlag

log = logging.getLogger(__name__)


def _trim_ascii_ws(s: str) -> str:
    kezdet, vege = 0, len(s)
    while kezdet < vege and ord(s[kezdet]) <= 0x20:
        kezdet += 1
    while vege > kezdet and ord(s[vege - 1]) <= 0x20:
        vege -= 1
    return s[kezdet:vege]


class ChatHub:
    OPEN_GLOBAL_ID = 2200
    FLEET_LOCAL_COLONIAL_ID = 2301
    FLEET_GLOBAL_COLONIAL_ID = 2302
    FLEET_LOCAL_CYLON_ID = 2311
    FLEET_GLOBAL_CYLON_ID = 2312
    SYSTEM_WIDE_BASE = 20000
    SYSTEM_LOCAL_BASE = 30000
    FRAKCIO_SAV = 3000
    SAV_MERET = 3 * FRAKCIO_SAV
    OPEN_LOCAL_BASE = 40000
    SQUADRON_BASE = 50000
    WING_BASE = 60000

    def __init__(self, server_settings):
        self._server_settings = server_settings
        self._client_port = getattr(server_settings, "chat_client_port", 0)
        self._running = GuardedFlag(False)
        self._client_server_socket = None
        self._admin_server_socket = None
        self._faction_by_user = {}
        self._clients_by_user_id = {}
        self._clients_by_name = {}
        self._last_known_sector = {}
        self._party_by_user = {}
        self._guild_by_user = {}
        self._maps_lock = threading.Lock()

    def start(self) -> None:
        if not self._running.set_if(False, True):
            return
        self._start_client_listener()
        self._start_admin_listener()

    def stop(self) -> None:
        if not self._running.set_if(True, False):
            return
        self._close_server_socket(self._client_server_socket)
        self._close_server_socket(self._admin_server_socket)
        with self._maps_lock:
            connections = list(self._clients_by_user_id.values())
            self._clients_by_user_id.clear()
            self._clients_by_name.clear()
        for connection in connections:
            connection.close()

    @staticmethod
    def _spawn(target) -> None:
        threading.Thread(target=target, daemon=True).start()

    def _start_client_listener(self) -> None:
        try:
            sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
            sock.bind(("", self._client_port))
            sock.listen(50)
            self._client_server_socket = sock
        except OSError as e:
            log.error('chat refused to start on port {}: {}'.format(self._client_port, e))
            return

        def _loop():
            log.info('chat listening on port {}'.format(self._client_port))
            while self._running.get():
                try:
                    socket, _addr = self._client_server_socket.accept()
                    self._spawn(lambda s=socket: self._handle_client_connection(s))
                except OSError as e:
                    if self._running.get():
                        log.warning('chat connection turned away: {}'.format(e))

        self._spawn(_loop)

    def _start_admin_listener(self) -> None:
        admin_port = self._server_settings.chat_server_port
        if admin_port <= 0:
            log.warning('chat control disabled - port set to zero')
            return

        try:
            sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
            sock.bind(("", admin_port))
            sock.listen(50)
            self._admin_server_socket = sock
        except OSError as e:
            log.error('chat control refused to start on port {}: {}'.format(admin_port, e))
            return

        def _loop():
            log.info('chat control listening on port {}'.format(admin_port))
            while self._running.get():
                try:
                    socket, _addr = self._admin_server_socket.accept()
                    self._spawn(lambda s=socket: self._handle_admin_connection(s))
                except OSError as e:
                    if self._running.get():
                        log.warning('chat control connection turned away: {}'.format(e))

        self._spawn(_loop)

    def _handle_client_connection(self, socket) -> None:
        try:
            connection = _ChatPeer(socket)
        except OSError as e:
            log.warning('chat connection never formed: {}'.format(e))
            self._close_socket(socket)
            return

        log.info('chat client attached: {}'.format(self._peer(socket)))
        try:
            while self._running.get():
                sor = connection.reader.readline()
                if sor == "":
                    break
                trimmed = _trim_ascii_ws(sor)
                if trimmed != "":
                    self._handle_client_line(connection, trimmed)
        except OSError as e:
            log.info('chat client detached: {}'.format(e))
        finally:
            self._remove_client(connection)
            connection.close()

    def _handle_admin_connection(self, socket) -> None:
        log.info('chat control attached: {}'.format(self._peer(socket)))
        puffer = ""
        try:
            while self._running.get():
                data = socket.recv(1024)
                if not data:
                    break
                puffer += data.decode("utf-8", "replace")
                idx = puffer.find("#")
                while idx >= 0:
                    uzenet = puffer[:idx]
                    puffer = puffer[idx + 1:]
                    self._handle_admin_message(uzenet)
                    idx = puffer.find("#")
        except OSError as e:
            log.info('chat control connection dropped: {}'.format(e))
        finally:
            self._close_socket(socket)

    def _handle_admin_message(self, message: str) -> None:
        if message.startswith("bs%"):
            rakomany = message[3:]
            parts = rakomany.split("@")
            if len(parts) < 3:
                return
            verb = parts[0].lower()
            try:
                user_id = int(parts[1])
                ertek = int(parts[2])
            except ValueError:
                return
            if verb == "admin":
                if len(parts) >= 4:
                    with suppress(ValueError):
                        self._frakcio_bejegyzese(user_id, int(parts[3]))
                self._update_user_sector(user_id, ertek)
            elif verb == "party":
                self._update_dynamic_membership(
                    user_id, ertek, self._party_by_user, ChatHub.SQUADRON_BASE, "squadron")
            elif verb == "guild":
                self._update_dynamic_membership(
                    user_id, ertek, self._guild_by_user, ChatHub.WING_BASE, "wing")

    def _handle_client_line(self, connection, line: str) -> None:
        parts = line.split("%", 2)
        if len(parts) == 0:
            return
        cmd = parts[0]
        if cmd == "bu":
            self._handle_login(connection, parts)
        elif cmd == "bx":
            self._send_room_list(connection)
        elif cmd == "bz":
            self._handle_join(connection, parts)
        elif cmd == "a":
            self._chat_line_arrived(connection, parts)
        else:
            log.debug('that chat command is unknown: {}'.format(cmd))

    def _handle_login(self, connection, parts) -> None:
        if len(parts) < 3:
            return
        params = parts[2].split("@")
        if len(params) < 2:
            return
        user_name = params[0]
        try:
            user_id = int(params[1])
        except ValueError:
            return

        faction = 0
        if len(params) >= 9:
            with suppress(ValueError):
                faction = int(params[8])

        with self._maps_lock:
            elozo = self._clients_by_user_id.get(user_id)
            self._clients_by_user_id[user_id] = connection
            self._clients_by_name[user_name.lower()] = connection
            sector = self._last_known_sector.get(user_id, 0)
            oldal = self._faction_by_user.get(user_id, faction)
        if elozo is not None and elozo is not connection:
            elozo.close()

        connection.user_id = user_id
        connection.user_name = user_name
        connection.faction = oldal
        connection.sector_id = sector

        connection.send(f'bv%{user_id}#')
        self._send_room_list(connection)

        with self._maps_lock:
            party_id = self._party_by_user.get(user_id, 0)
            guild_id = self._guild_by_user.get(user_id, 0)
        if party_id:
            self._apply_dynamic_room(connection, ChatHub.SQUADRON_BASE, party_id, "squadron")
        if guild_id:
            self._apply_dynamic_room(connection, ChatHub.WING_BASE, guild_id, "wing")

    def _handle_join(self, connection, parts) -> None:
        if len(parts) < 3:
            return
        room_part = parts[2]
        at_index = room_part.find("@")
        if at_index >= 0:
            room_part = room_part[:at_index]
        with suppress(ValueError):
            room_id = int(room_part)
            if self._idegen_szoba(connection, room_id):
                return
            connection.joined_rooms.add(room_id)

    @staticmethod
    def _szoba_oldala(room_id: int) -> int:
        if room_id in (ChatHub.FLEET_LOCAL_COLONIAL_ID, ChatHub.FLEET_GLOBAL_COLONIAL_ID):
            return 1
        if room_id in (ChatHub.FLEET_LOCAL_CYLON_ID, ChatHub.FLEET_GLOBAL_CYLON_ID):
            return 2
        for kezdet in (ChatHub.SYSTEM_WIDE_BASE, ChatHub.SYSTEM_LOCAL_BASE):
            if kezdet <= room_id < kezdet + ChatHub.SAV_MERET:
                return (room_id - kezdet) // ChatHub.FRAKCIO_SAV
        return 0

    @staticmethod
    def _idegen_szoba(connection, room_id: int) -> bool:
        oldal = ChatHub._szoba_oldala(room_id)
        return oldal != 0 and connection.faction in (1, 2) and oldal != connection.faction

    def _chat_line_arrived(self, connection, parts) -> None:
        if len(parts) < 3:
            return
        try:
            room_id = int(parts[1])
        except ValueError:
            return

        if self._idegen_szoba(connection, room_id):
            return

        szoveg = parts[2]
        if szoveg.endswith("@"):
            szoveg = szoveg[:-1]
        if szoveg.startswith("/w "):
            self._handle_whisper(connection, _trim_ascii_ws(szoveg[3:]))
            return

        self._broadcast_to_room(room_id, connection.user_name, szoveg)

    def _handle_whisper(self, sender, sugas: str) -> None:
        parts = sugas.split(" ", 1)
        if len(parts) < 2:
            sender.send("ct#")
            return
        target_name = parts[0]
        uzenet = parts[1]
        if target_name.lower() == sender.user_name.lower():
            sender.send("cu#")
            return

        with self._maps_lock:
            cimzett = self._clients_by_name.get(target_name.lower())
        if cimzett is None:
            sender.send("ct#")
            return

        cimzett.send("cv%" + sender.user_name + "@" + uzenet + "#")
        sender.send("cw%" + target_name + "@" + uzenet + "#")

    def _broadcast_to_room(self, room_id: int, user_name: str, text: str) -> None:
        uzenet = f'a%{room_id}@' + user_name + "@" + text + "#"
        with self._maps_lock:
            clients = list(self._clients_by_user_id.values())
        for client in clients:
            if room_id in client.joined_rooms:
                client.send(uzenet)

    def _send_room_list(self, connection) -> None:
        self._send_system_open_channels_update(connection)
        self._send_fleet_channels_update(connection)

    def _send_system_open_channels_update(self, connection) -> None:
        sector_id = max(connection.sector_id, 0)
        system_wide = self._system_wide_id(sector_id, connection.faction)
        system_local = self._system_local_id(sector_id, connection.faction)
        open_local = self._open_local_id(sector_id)

        szektorhoz_kotott = (
            (ChatHub.SYSTEM_WIDE_BASE, ChatHub.SYSTEM_WIDE_BASE + ChatHub.SAV_MERET),
            (ChatHub.SYSTEM_LOCAL_BASE, ChatHub.SYSTEM_LOCAL_BASE + ChatHub.SAV_MERET),
            (ChatHub.OPEN_LOCAL_BASE, ChatHub.OPEN_LOCAL_BASE + 10000),
        )
        connection.joined_rooms = {
            i for i in connection.joined_rooms
            if not any(also <= i < felso for also, felso in szektorhoz_kotott)
        }
        connection.joined_rooms.update(
            (system_wide, system_local, open_local, ChatHub.OPEN_GLOBAL_ID))

        connection.send(self._build_system_open_channels_update(
            connection, system_local, system_wide, open_local))

    def _send_fleet_channels_update(self, connection) -> None:
        connection.send(self._build_fleet_channels_update(connection.faction))

    def _build_system_open_channels_update(self, connection, system_local: int,
                                           system_wide: int, open_local: int) -> str:
        if connection.faction == 1:
            system_label = "System-Colonial"
        elif connection.faction == 2:
            system_label = "System-Cylon"
        else:
            system_label = "System"
        open_label = "Open Channel"

        return ("fz%"
                f'-1|{system_local}|{system_label}|0|0|0}}'
                f'-1|{system_wide}|{system_label}|0|0|1}}'
                f'-1|{open_local}|{open_label}|0|0|0}}'
                f'-1|{ChatHub.OPEN_GLOBAL_ID}|{open_label}|0|0|1}}#')

    def _build_fleet_channels_update(self, faction: int) -> str:
        sorok = []
        if faction != 2:
            sorok.append(f'{ChatHub.FLEET_LOCAL_COLONIAL_ID}|Fleet-Colonial|0|1|0|0|0}}')
            sorok.append(f'{ChatHub.FLEET_GLOBAL_COLONIAL_ID}|Fleet-Colonial|0|1|0|0|1}}')
        if faction != 1:
            sorok.append(f'{ChatHub.FLEET_LOCAL_CYLON_ID}|Fleet-Cylon|0|2|0|0|0}}')
            sorok.append(f'{ChatHub.FLEET_GLOBAL_CYLON_ID}|Fleet-Cylon|0|2|0|0|1}}')
        sorok[-1] = sorok[-1][:-1] + "#"
        return "by%" + "".join(sorok)

    def _system_local_id(self, sector_id: int, faction: int = 0) -> int:
        return ChatHub.SYSTEM_LOCAL_BASE + faction * ChatHub.FRAKCIO_SAV + sector_id

    def _system_wide_id(self, sector_id: int, faction: int = 0) -> int:
        return ChatHub.SYSTEM_WIDE_BASE + faction * ChatHub.FRAKCIO_SAV + sector_id

    def _open_local_id(self, sector_id: int) -> int:
        return ChatHub.OPEN_LOCAL_BASE + sector_id

    def _frakcio_bejegyzese(self, user_id: int, faction: int) -> None:
        if faction not in (1, 2):
            return
        with self._maps_lock:
            self._faction_by_user[user_id] = faction
            kapcsolat = self._clients_by_user_id.get(user_id)
        if kapcsolat is not None and kapcsolat.faction != faction:
            kapcsolat.faction = faction
            self._send_room_list(kapcsolat)

    def _update_user_sector(self, user_id: int, sector_id: int) -> None:
        with self._maps_lock:
            self._last_known_sector[user_id] = sector_id
            connection = self._clients_by_user_id.get(user_id)
        if connection is not None:
            connection.sector_id = sector_id
            self._send_system_open_channels_update(connection)

    def _update_dynamic_membership(self, user_id: int, group_id: int, store: dict,
                                   base: int, room_prefix: str) -> None:
        with self._maps_lock:
            if group_id > 0:
                store[user_id] = group_id
            else:
                store.pop(user_id, None)
            connection = self._clients_by_user_id.get(user_id)
        if connection is not None:
            self._apply_dynamic_room(connection, base, group_id, room_prefix)

    def _apply_dynamic_room(self, connection, base: int, group_id: int, room_prefix: str) -> None:
        old_rooms = {r for r in connection.joined_rooms if base <= r < base + 10000}
        new_room = base + group_id if group_id > 0 else 0
        for room in old_rooms:
            if room == new_room:
                continue
            connection.joined_rooms.discard(room)
            connection.send(f'fr%{room}#')
        if new_room and new_room not in connection.joined_rooms:
            connection.joined_rooms.add(new_room)
            connection.send(f'fq%{new_room}@' + room_prefix + "_" + str(group_id) + "@0#")

    def _remove_client(self, connection) -> None:
        with self._maps_lock:
            if connection.user_id != -1:
                if self._clients_by_user_id.get(connection.user_id) is connection:
                    del self._clients_by_user_id[connection.user_id]
            if connection.user_name is not None and connection.user_name.strip() != "":
                if self._clients_by_name.get(connection.user_name.lower()) is connection:
                    del self._clients_by_name[connection.user_name.lower()]

    @staticmethod
    def _close_server_socket(fogado_aljzat) -> None:
        if fogado_aljzat is None:
            return
        with suppress(OSError):
            fogado_aljzat.close()

    @staticmethod
    def _close_socket(socket) -> None:
        with suppress(OSError):
            socket.close()

    @staticmethod
    def _peer(socket):
        try:
            return socket.getpeername()
        except OSError:
            return None


class _ChatPeer:

    def __init__(self, socket):
        self.socket = socket
        self.reader = socket.makefile("r", encoding="utf-8", errors="replace", newline="")
        self._write_lock = threading.Lock()
        self.joined_rooms = set()

        self.user_id = -1
        self.user_name = ""
        self.faction = 0
        self.sector_id = 0

    def send(self, message: str) -> None:
        with self._write_lock:
            with suppress(OSError):
                self.socket.sendall(message.encode("utf-8"))

    def close(self) -> None:
        with suppress(OSError):
            self.socket.close()
