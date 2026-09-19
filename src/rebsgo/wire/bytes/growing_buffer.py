# github.com/Shran21

from __future__ import annotations

import logging

from rebsgo.helpers.locks import ReentrantLock

log = logging.getLogger(__name__)


class GrowingBuffer:
    def __init__(self, size: int = 64):
        if size < 0:
            raise ValueError(f'starting size below zero: {size}')
        self.buffer = bytearray()
        self.count = 0
        self.length_written = False
        self._frozen_bytes = None
        self.lock = ReentrantLock()

    def write_one(self, b: int) -> None:
        if self.length_written:
            log.error('buffer already flushed; writes are over')
            self._frozen_bytes = None
        self.buffer.append(b & 0xFF)
        self.count += 1

    def write(self, data) -> None:
        if self.length_written:
            log.error('buffer already flushed; writes are over')
            self._frozen_bytes = None
        self.buffer.extend(data)
        self.count = len(self.buffer)

    def write_to(self, out) -> None:
        out.write(self.frozen_bytes())

    def reset(self) -> None:
        self.count = 0
        self.buffer = bytearray()
        self.length_written = False
        self._frozen_bytes = None

    @property
    def to_byte_array(self) -> bytes:
        return bytes(self.buffer)

    def frozen_bytes(self) -> bytes:
        self.write_data_length()
        if self._frozen_bytes is None:
            self._frozen_bytes = bytes(self.buffer)
        return self._frozen_bytes

    def size(self) -> int:
        return self.count

    def __str__(self) -> str:
        return bytes(self.buffer[:self.count]).decode("latin-1")

    def write_data_length(self) -> None:
        with self.lock:
            if self.length_written:
                return
            hossz = self.size() - 2
            self.buffer[0] = (hossz >> 8) & 255
            self.buffer[1] = hossz & 255
            self.length_written = True
