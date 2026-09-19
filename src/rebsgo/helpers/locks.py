# github.com/Shran21

from __future__ import annotations

import threading


class ReentrantLock:

    def __init__(self):
        self._lock = threading.RLock()

    def lock(self) -> None:
        self._lock.acquire()

    def unlock(self) -> None:
        self._lock.release()

    @property
    def try_lock(self) -> bool:
        return self._lock.acquire(blocking=False)

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        return self._lock.acquire(blocking, timeout)

    def release(self) -> None:
        self._lock.release()

    def __enter__(self) -> "ReentrantLock":
        self._lock.acquire()
        return self

    def __exit__(self, *exc) -> bool:
        self._lock.release()
        return False


class _RWChildLock:
    def __init__(self, acquire, release):
        self._acquire = acquire
        self._release = release

    def lock(self) -> None:
        self._acquire()

    def unlock(self) -> None:
        self._release()

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        self._acquire()
        return True

    def release(self) -> None:
        self._release()

    def __enter__(self) -> "_RWChildLock":
        self._acquire()
        return self

    def __exit__(self, *exc) -> bool:
        self._release()
        return False


class ReadWriteLock:

    def __init__(self):
        self._cond = threading.Condition(threading.Lock())
        self._readers: dict[int, int] = {}
        self._writer_owner: int | None = None
        self._writer_count = 0
        self._read_lock = _RWChildLock(self._acquire_read, self._release_read)
        self._write_lock = _RWChildLock(self._acquire_write, self._release_write)

    @property
    def read_lock(self) -> _RWChildLock:
        return self._read_lock

    @property
    def write_lock(self) -> _RWChildLock:
        return self._write_lock

    def _acquire_read(self) -> None:
        me = threading.get_ident()
        with self._cond:
            if me in self._readers or self._writer_owner == me:
                self._readers[me] = self._readers.get(me, 0) + 1
                return
            while self._writer_owner is not None:
                self._cond.wait()
            self._readers[me] = self._readers.get(me, 0) + 1

    def _release_read(self) -> None:
        me = threading.get_ident()
        with self._cond:
            darab = self._readers.get(me, 0)
            if darab <= 1:
                self._readers.pop(me, None)
            else:
                self._readers[me] = darab - 1
            if not self._readers:
                self._cond.notify_all()

    def _acquire_write(self) -> None:
        me = threading.get_ident()
        with self._cond:
            if self._writer_owner == me:
                self._writer_count += 1
                return
            while self._writer_owner is not None or len(self._readers) > 0:
                self._cond.wait()
            self._writer_owner = me
            self._writer_count = 1

    def _release_write(self) -> None:
        with self._cond:
            self._writer_count -= 1
            if self._writer_count == 0:
                self._writer_owner = None
                self._cond.notify_all()


class Zarhato:
    @property
    def _olvasva(self) -> _RWChildLock:
        return self._read_write_lock.read_lock

    @property
    def _irva(self) -> _RWChildLock:
        return self._read_write_lock.write_lock
