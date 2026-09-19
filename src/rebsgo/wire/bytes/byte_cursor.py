# github.com/Shran21

from __future__ import annotations


class ByteCursor:
    def __init__(self, buf, offset: int = 0, length: int | None = None):
        self.buf = buf
        if length is None:
            self.pos = 0
            self.count = len(buf)
            self.mark = 0
        else:
            self.pos = offset
            self.count = min(offset + length, len(buf))
            self.mark = offset

    def read(self) -> int:
        if self.pos < self.count:
            b = self.buf[self.pos] & 0xFF
            self.pos += 1
            return b
        return -1

    def read_nbytes(self, n: int) -> bytes:
        vege = min(self.pos + n, self.count)
        eredmeny = bytes(self.buf[self.pos:vege])
        self.pos = vege
        return eredmeny

    def all_bytes(self) -> bytes:
        eredmeny = bytes(self.buf[self.pos:self.count])
        self.pos = self.count
        return eredmeny

    def skip(self, n: int) -> int:
        k = self.count - self.pos
        if n < k:
            k = 0 if n < 0 else n
        self.pos += int(k)
        return k

    @property
    def available(self) -> int:
        return self.count - self.pos

    def mark_pos(self, elore_olvasas: int = 0) -> None:
        self.mark = self.pos

    def reset(self) -> None:
        self.pos = self.mark

    def close(self) -> None:
        pass
