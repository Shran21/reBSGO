# github.com/Shran21

from __future__ import annotations

from datetime import datetime, timedelta, timezone


class ChatBan:
    def __init__(self):
        self._silenced_until = {}

    def silence(self, user_id: int, until: datetime) -> None:
        self._silenced_until[user_id] = until

    def silence_hours(self, user_id: int, hours: float) -> None:
        self.silence(user_id, datetime.now(timezone.utc) + timedelta(hours=hours))

    def may_chat(self, user_id: int) -> bool:
        hatarido = self._silenced_until.get(user_id)
        if hatarido is None:
            return True

        lejart = datetime.now(timezone.utc) > hatarido
        if lejart:
            self._silenced_until.pop(user_id, None)

        return lejart
