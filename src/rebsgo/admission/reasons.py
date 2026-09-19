# github.com/Shran21

from __future__ import annotations

UNKNOWN_PATH = "unknown-path"
METHOD_NOT_ALLOWED = "method-not-allowed"
BAD_REQUEST = "bad-request"
MISSING_NAME = "missing-name"
MISSING_PASSWORD = "missing-password"

RATE_LIMITED = "rate-limited"
BUSY = "busy"
SERVER_ERROR = "server-error"

BAD_CREDENTIALS = "bad-credentials"
BANNED = "banned"
MAINTENANCE = "maintenance"
ALREADY_ONLINE = "already-online"

REGISTRATION_CLOSED = "registration-closed"
NAME_RULES = "name-rules"
PASSWORD_RULES = "password-rules"
NAME_TAKEN = "name-taken"

TICKET_MALFORMED = "ticket-malformed"
TICKET_EXPIRED = "ticket-expired"
TICKET_UNKNOWN = "ticket-unknown"
TICKET_SPENT = "ticket-spent"
TICKET_OUTSTANDING = "ticket-outstanding"
TICKET_OTHER_PILOT = "ticket-other-pilot"
TICKET_OTHER_HOST = "ticket-other-host"


class RefusedWithReason(Exception):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


def reason_of(hiba: BaseException, default: str = SERVER_ERROR) -> str:
    return getattr(hiba, "reason", None) or default
