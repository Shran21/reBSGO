# github.com/Shran21

from __future__ import annotations


class ServerHandles:
    def __init__(self, connection, catalogue, server_config, timetable,
                 merok, rng, galaxy, user=None):
        self._connection = connection
        self._catalogue = catalogue
        self._server_config = server_config
        self._timetable = timetable
        self._merok = merok
        self._galaxy = galaxy
        self._rng = rng
        self._user = user

    def connection(self):
        return self._connection

    @property
    def catalogue(self):
        return self._catalogue

    @property
    def server_config(self):
        return self._server_config

    @property
    def timetable(self):
        return self._timetable

    @property
    def merok(self):
        return self._merok

    @property
    def galaxy(self):
        return self._galaxy

    @property
    def rng(self):
        return self._rng

    def user(self, user=None):
        if user is None:
            return self._user
        self._user = user
