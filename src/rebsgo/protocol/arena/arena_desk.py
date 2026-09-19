# github.com/Shran21
from __future__ import annotations

import datetime
import logging

from rebsgo.gamedata.from_json.template_readers import arena_terms

from rebsgo.protocol.arena.arena_match import ArenaMatch
from rebsgo.protocol.arena.arena_replies import ArenaReplies
from rebsgo.protocol.messages import ArenaReply
from rebsgo.helpers.locks import ReentrantLock

log = logging.getLogger(__name__)

_QUEUE_CONFIG = {
    1: (ArenaReply.Arena1vs1CheckedIn, 2),
    2: (ArenaReply.Arena3vs3MixedCheckedIn, 6),
    3: (ArenaReply.Arena3vs3MixedRandomCheckedIn, 6),
    4: (ArenaReply.ArenaDuelCheckedIn, 2),
}

_DEFAULT_CONFIG = {"arenaSectorId": 9001, "arenaSceneBaseSectorId": 18,
                   "duelDurationSeconds": 900, "respawnDelaySeconds": 8,
                   "spawnWaitSeconds": 30, "returnDelaySeconds": 4,
                   "matchQueueId": 1, "duelInviteTtlSeconds": 30}


def _load_config() -> dict:
    cfg = dict(_DEFAULT_CONFIG)
    cfg.update(arena_terms())
    return cfg


_TERMS = _load_config()
_MATCH_QUEUE_ID = _TERMS["matchQueueId"]
_DUEL_INVITE_TTL_SECONDS = _TERMS["duelInviteTtlSeconds"]


class ArenaDesk:
    def __init__(self, sector_book=None, pilot_roster=None):
        self._writer = ArenaReplies()
        self._queues: dict[int, list] = {queue_id: [] for queue_id in _QUEUE_CONFIG}
        self._lock = ReentrantLock()
        self._sector_book = sector_book
        self._pilot_roster = pilot_roster
        self._config = _load_config()
        self._matches_by_player: dict[int, ArenaMatch] = {}
        self._pending_invites: dict[int, object] = {}

    def check_in(self, user, queue_id: int) -> None:
        config = _QUEUE_CONFIG.get(queue_id)
        if config is None:
            return
        ack_message, needed = config

        matched = None
        with self._lock:
            self._remove_from_all_locked(user)
            queue = self._queues[queue_id]
            queue.append(user)
            queue_size = len(queue)
            if queue_size >= needed:
                matched = [queue.pop(0) for _ in range(needed)]

        user.send(self._writer.simple(ack_message))
        log.info("Arena check-in user=%s queue=%s size=%s/%s",
                 user.user_log(), queue_id, queue_size, needed)
        if matched:
            for matched_user in matched:
                matched_user.send(self._writer.arena_party_found)
            log.info("Arena match found queue=%s players=%s", queue_id,
                     [u.pilot_of().user_id_of() for u in matched])
            if queue_id == _MATCH_QUEUE_ID:
                self._start_match(matched)

    def duel_invite(self, challenger, target_player_id: int) -> None:
        challenger.send(self._writer.simple(ArenaReply.ArenaDuelCheckedIn))
        celpont = self._pilot_roster.by_id(target_player_id) if self._pilot_roster is not None else None
        challenger_id = challenger.pilot_of().user_id_of()
        if celpont is None or target_player_id == challenger_id:
            challenger.send(self._writer.arena_failed(challenger_id, 0))
            return
        expiry = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) \
            + datetime.timedelta(seconds=_DUEL_INVITE_TTL_SECONDS)
        with self._lock:
            self._pending_invites[target_player_id] = challenger
        celpont.send(self._writer.arena_duel_invite_slave(challenger_id, expiry))
        log.info("Arena duel invite from %s to %s", challenger_id, target_player_id)

    def invite_ok(self, user) -> None:
        uid = user.pilot_of().user_id_of()
        with self._lock:
            challenger = self._pending_invites.pop(uid, None)
        if challenger is None:
            return
        if not challenger.is_connected():
            user.send(self._writer.arena_failed(uid, 0))
            return
        self._start_match([challenger, user])

    def _start_match(self, pilotak) -> None:
        if self._sector_book is None:
            log.error("arena: no sector registry, cannot start duel")
            return
        egyezes = ArenaMatch(self._config, self._sector_book, self._writer, self._pilot_roster)
        try:
            if not egyezes.start(pilotak):
                return
        except Exception:
            log.exception("arena: failed to start duel")
            return
        with self._lock:
            for user in pilotak:
                self._matches_by_player[user.pilot_of().user_id_of()] = egyezes

    def cancel_check_in(self, user) -> None:
        with self._lock:
            self._remove_from_all_locked(user)

    def on_gone(self, user) -> None:
        pid = user.pilot_of().user_id_of()
        with self._lock:
            self._remove_from_all_locked(user)
            egyezes = self._matches_by_player.pop(pid, None)
        if egyezes is not None:
            egyezes.on_player_disconnect(pid)

    def _remove_from_all_locked(self, user) -> None:
        for queue in self._queues.values():
            if user in queue:
                queue.remove(user)
        pid = user.pilot_of().user_id_of()
        challenger = self._pending_invites.pop(pid, None)
        if challenger is not None and challenger is not user and challenger.is_connected():
            challenger.send(self._writer.arena_closed)
        for target_id, ch in list(self._pending_invites.items()):
            if ch is user:
                del self._pending_invites[target_id]
                celpont = self._pilot_roster.by_id(target_id) if self._pilot_roster is not None else None
                if celpont is not None and celpont.is_connected():
                    celpont.send(self._writer.arena_closed)
