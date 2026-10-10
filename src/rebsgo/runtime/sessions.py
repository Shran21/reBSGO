# github.com/Shran21

from __future__ import annotations


class GuestSession:
    def __init__(self, connection, session, protocol_desk):
        self._connection = connection
        self._session = session
        self._protocol_desk = protocol_desk

    def connection(self):
        return self._connection

    def session(self):
        return self._session

    @property
    def protocol_desk(self):
        return self._protocol_desk
