# github.com/Shran21
from __future__ import annotations

import logging
import time

from rebsgo.wire.links.tcp_link import TcpLink

log = logging.getLogger(__name__)


class LinkHandle(TcpLink):
    def __init__(self, socket, bytes_per_second_limit_before_kick: float):
        super().__init__(socket)
        self._bytes_per_second_limit_before_kick = bytes_per_second_limit_before_kick
        self._start_time = int(time.time() * 1000)
        self._total_incoming = 0.0
        self._max_bytes_per_second = 0.0

    def next_message(self):
        atmeneti = super().next_message()

        self._total_incoming += atmeneti.size

        elapsed = int(time.time() * 1000) - self._start_time
        seconds = elapsed * 0.001
        bytes_per_second = self._total_incoming / seconds if seconds != 0 else float("inf")
        self._max_bytes_per_second = max(self._max_bytes_per_second, bytes_per_second)

        if bytes_per_second >= self._bytes_per_second_limit_before_kick:
            issue_text = (f'a kliens túl sok bájtot küldött, a kapcsolat bontva {self.socket.getpeername()} {bytes_per_second}/' + str(self._bytes_per_second_limit_before_kick))
            self.close_connection("TcpLink closed because " + issue_text)

        return atmeneti
