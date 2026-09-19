# github.com/Shran21
from __future__ import annotations


class SquadJumpRow:
    def __init__(self, user, state):
        self._user = user
        self._state = state

    def user(self):
        return self._user

    @property
    def state(self):
        return self._state
