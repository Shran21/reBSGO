# github.com/Shran21
from __future__ import annotations

import logging
import threading

from rebsgo.wire.links.greeter import Greeter

log = logging.getLogger(__name__)


class FrontDoor:
    def __init__(self, port: int, backlog: int):
        try:
            self._connection_accepter = Greeter(port, backlog)
        except OSError as e:
            raise RuntimeError(e)
        self._new_connection_subscriber = None
        self._is_shutdown = False
        self._lock = threading.Lock()

    def on_listener_event(self, fogado_figyelo) -> None:
        self._new_connection_subscriber = fogado_figyelo

    def run(self) -> None:
        while not self._is_shutdown:
            try:
                new_connection = self._connection_accepter.accept()
                if self._new_connection_subscriber is not None:
                    self._new_connection_subscriber.on_new_link(new_connection)
            except OSError:
                pass
            except Exception:
                log.exception("the door could not take a new connection")
                self.shutdown()

    def is_shutdown(self) -> bool:
        return self._is_shutdown

    def shutdown(self) -> None:
        with self._lock:
            if not self._is_shutdown:
                self._is_shutdown = True
                self._connection_accepter.shutdown()

    def __repr__(self) -> str:
        return f'<FrontDoor kapcsolat-fogadó={self._connection_accepter}>'
