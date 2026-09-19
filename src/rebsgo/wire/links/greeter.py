# github.com/Shran21
from __future__ import annotations

import logging
import socket as _socket

from rebsgo.wire.links.link_handle import LinkHandle

log = logging.getLogger(__name__)


class Greeter:
    ELSO_SZO_TURELEM = 10
    LINK_TURELEM_MS = 60_000

    def __init__(self, port: int, backlog: int):
        self._server_socket = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        self._server_socket.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        self._server_socket.bind(("", port))
        self._server_socket.listen(backlog)

    def accept(self) -> LinkHandle:
        incoming_client = self._server_socket.accept()[0]
        incoming_client.settimeout(Greeter.ELSO_SZO_TURELEM)
        log.info('link opened: {}'.format(incoming_client.getpeername()))
        return LinkHandle(incoming_client, Greeter.LINK_TURELEM_MS)

    def shutdown(self) -> None:
        try:
            self._server_socket.close()
        except OSError as mar_zarva:
            log.warning('this connection is closed already', exc_info=mar_zarva)

    def __repr__(self) -> str:
        return f'<Greeter szerver-kapcsolat={self._server_socket}>'
