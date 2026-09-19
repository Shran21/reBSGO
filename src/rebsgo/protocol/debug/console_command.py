# github.com/Shran21
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

log = logging.getLogger(__name__)


class ConsoleCommand(ABC):
    def __init__(self, command: str, kello_jogok: int):
        self.command = command
        self.required_permissions = kello_jogok
        self.user = None

    def seed_user(self, user) -> None:
        if user is None:
            raise TypeError("user must not be None")
        self.user = user

    def execute(self, br) -> None:
        allowed = self._permissions_check
        if not allowed:
            log.warning('%s reached for a console command their rank does not cover',
                    self.user.user_log())
            return
        self.own_work(br)

    @property
    def _permissions_check(self) -> bool:
        return self.user.pilot_of().bgo_admin_roles.allowed(self.required_permissions)

    @abstractmethod
    def own_work(self, br) -> None:
        ...
