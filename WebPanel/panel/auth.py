# github.com/Shran21

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sqlite3
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass

from panel.settings import GAME_ROOT, Settings

sys.path.insert(0, str(GAME_ROOT / "src"))

from rebsgo.admission.passwords import Jelszotar  # noqa: E402
from rebsgo.vocabulary.pilot import ServerRoles  # noqa: E402

_SIGNING_LABEL = b"rebsgo/panel-ticket/1\x00"
COOKIE_NAME = "panel_ticket"


class LoginRefused(Exception):
    def __init__(self, message_key: str):
        super().__init__(message_key)
        self.message_key = message_key


@dataclass(frozen=True, slots=True)
class Session:
    pilot_id: int
    name: str
    role_bits: int
    expires: int

    def wears(self, role: ServerRoles) -> bool:
        return bool(self.role_bits & role.value)

    def wears_any(self, *roles: ServerRoles) -> bool:
        return any(self.wears(role) for role in roles)

    @property
    def role_names(self) -> list:
        return [r.name for r in ServerRoles if r.value and self.role_bits & r.value]

    @property
    def can_console(self) -> bool:
        return self.wears(ServerRoles.Console) and not self.wears(ServerRoles.Mod)


class _DbSource:
    def __init__(self, path):
        self._path = str(path)

    def connection(self):
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn


class RateCounter:
    def __init__(self, window_seconds: float = 60.0, limit: int = 10):
        self._window = window_seconds
        self._limit = limit
        self._attempts: dict = {}
        self._lock = threading.Lock()

    def allows(self, address: str) -> bool:
        now = time.monotonic()
        with self._lock:
            log = self._attempts.setdefault(address, deque())
            while log and now - log[0] > self._window:
                log.popleft()
            if len(log) >= self._limit:
                return False
            log.append(now)
            return True


class Gatekeeper:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._passwords = Jelszotar(_DbSource(settings.db_path))
        self._rate = RateCounter()
        mask = 0
        for name in settings.login_roles:
            role = getattr(ServerRoles, name, None)
            if role is not None:
                mask |= role.value
        self._entry_mask = mask
        root = hmac.new(settings.secret, b"panel-keys", hashlib.sha256).digest()
        self._signing_key = hmac.new(root, b"signing", hashlib.sha256).digest()

    @property
    def password_store(self) -> Jelszotar:
        return self._passwords


    def login(self, name: str, password: str, origin: str) -> Session:
        if not self._rate.allows(origin):
            raise LoginRefused("login.failed.throttled")
        pilot_id = self._passwords.azonosito(name)
        if pilot_id is None or not self._passwords.helyes(pilot_id, password):
            raise LoginRefused("login.failed.unknown")
        record = self._pilot_record(pilot_id)
        if record is None:
            raise LoginRefused("login.failed.unknown")
        pilot_name, role_bits = record
        if not role_bits & self._entry_mask:
            raise LoginRefused("login.failed.unknown")
        expires = int(time.time()) + self._settings.session_seconds
        return Session(pilot_id, pilot_name, role_bits, expires)

    def _pilot_record(self, pilot_id: int):
        conn = sqlite3.connect(f"file:{self._settings.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT name, roles_bits FROM pilots WHERE id=?", (pilot_id,)).fetchone()
        finally:
            conn.close()
        return None if row is None else (row["name"], int(row["roles_bits"] or 0))


    def write_ticket(self, session: Session) -> str:
        payload = json.dumps(
            {"p": session.pilot_id, "n": session.name,
             "b": session.role_bits, "e": session.expires},
            separators=(",", ":")).encode("utf-8")
        body = base64.urlsafe_b64encode(payload).rstrip(b"=")
        signature = hmac.new(self._signing_key, _SIGNING_LABEL + body, hashlib.sha256).digest()
        return (body + b"." + base64.urlsafe_b64encode(signature).rstrip(b"=")).decode("ascii")

    def read_ticket(self, ticket: str) -> Session | None:
        try:
            body_part, _, signature_part = ticket.partition(".")
            body = body_part.encode("ascii")
            got = base64.urlsafe_b64decode(signature_part + "=" * (-len(signature_part) % 4))
            want = hmac.new(self._signing_key, _SIGNING_LABEL + body, hashlib.sha256).digest()
            if not hmac.compare_digest(got, want):
                return None
            data = json.loads(base64.urlsafe_b64decode(body + b"=" * (-len(body) % 4)))
            session = Session(int(data["p"]), str(data["n"]), int(data["b"]), int(data["e"]))
        except Exception:
            return None
        if session.expires < time.time():
            return None
        return session

    def csrf_token(self, session: Session) -> str:
        base = f"{session.pilot_id}.{session.expires}".encode("utf-8")
        return hmac.new(self._signing_key, b"csrf\x00" + base, hashlib.sha256).hexdigest()[:32]
