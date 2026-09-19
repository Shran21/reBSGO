# github.com/Shran21
from __future__ import annotations

import logging
import socket as _socket

from rebsgo.wire.bytes.wire_in import WireIn
from rebsgo.runtime.links import LinkBase
from rebsgo.wire.links.outbox.queued_outbox import QueuedOutbox
from rebsgo.journal import hivasi_lanc

log = logging.getLogger(__name__)


class TcpLink(LinkBase):
    def __init__(self, socket):
        super().__init__(socket)
        self.socket.setsockopt(_socket.IPPROTO_TCP, _socket.TCP_NODELAY, 1)
        self._input = self.socket.makefile("rb", buffering=65535)
        kimenet = self.socket.makefile("wb", buffering=65535)
        self._is_closed = False
        self._packet_sender = QueuedOutbox(kimenet)

    def send(self, bw) -> bool:
        return self._packet_sender.send(bw)

    def next_message(self) -> WireIn:
        if self._is_closed or self.socket.fileno() == -1:
            raise RuntimeError('reading from a link that is closed')
        try:
            hossz = WireIn.buffer_size(self._read_byte_array_len(2))
            return WireIn(self._read_byte_array_len(hossz))
        except _socket.timeout:
            self.close_connection('connection idled past its deadline: %s'
                                  % (self.remote_socket_address(),))
        except OSError as io_hiba:
            self.close_connection('read fell over: ' + hivasi_lanc(io_hiba))
        raise RuntimeError('reading from a link that is closed')

    def _read_byte_array_len(self, length: int) -> bytes:
        tomb = bytearray()
        already_read = 0
        now_read = 0
        while already_read < length and now_read != -1:
            darabka = self._input.read(length - already_read)
            now_read = -1 if (darabka is None or len(darabka) == 0) else len(darabka)
            if now_read != -1:
                tomb.extend(darabka)
                already_read += now_read
        if now_read == -1:
            raise OSError('the byte stream ended')
        return bytes(tomb)

    def is_closed(self) -> bool:
        return self._is_closed

    def close_connection(self, reason: str) -> None:
        try:
            if self.socket.fileno() != -1:
                self.socket.close()
        except OSError as io_hiba:
            log.warning('closing the connection went wrong', exc_info=io_hiba)
        finally:
            if not self._is_closed:
                log.info('closing link {} because {}'.format(self.remote_socket_address(), reason))
                self._is_closed = True
                self._notify_connection_closed(reason)
            self._packet_sender.shutdown()

    def _notify_connection_closed(self, reason: str) -> None:
        if self.connection_closed_subscriber is None:
            return
        self.connection_closed_subscriber.on_link_gone(self, reason)
