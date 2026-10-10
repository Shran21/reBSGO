# github.com/Shran21

from __future__ import annotations

from abc import ABC, abstractmethod
import datetime
import logging
log = logging.getLogger(__name__)


class LinkBase(ABC):
    def __init__(self, socket):
        self.socket = socket
        self.connection_closed_subscriber = None
        self.connection_time_stamp = datetime.datetime.now(datetime.timezone.utc)

    @abstractmethod
    def send(self, bw) -> bool:
        ...

    def on_link_closed(self, bontas_figyelo) -> None:
        if bontas_figyelo is not None:
            self.connection_closed_subscriber = bontas_figyelo

    def remote_socket_address(self):
        if self.socket is None:
            return None
        try:
            return self.socket.getpeername()
        except OSError:
            return None

    def remote_address(self) -> str | None:
        remote = self.remote_socket_address()
        if remote is None:
            return None
        return remote[0]

    def pretty_address(self) -> str:
        remote = self.remote_socket_address()
        if remote is None:
            return ""
        try:
            return remote[0] + " "
        except Exception as ex:
            log.error("Fix Address pretty print %s", ex)
        return "error"

    def ip_remote_host_address(self) -> str:
        remote = self.remote_socket_address()
        if remote is None:
            return ""
        return remote[0]

    def local_host_address(self) -> str:
        try:
            if self.socket is None:
                return ""
            local = self.socket.getsockname()
            if local is None:
                return ""
            return local[0]
        except Exception as ex:
            log.error("Fix local address pretty print %s", ex)
        return ""

    def link_timeout(self, wait_ms: int) -> None:
        self.socket.settimeout(None if wait_ms == 0 else wait_ms / 1000.0)
