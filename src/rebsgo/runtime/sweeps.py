# github.com/Shran21

from __future__ import annotations

import logging
import threading
from rebsgo.protocol.pilot.pilot_replies import PilotReplies
from datetime import datetime, timezone
from rebsgo.wire.bytes.stamp import Stamp


log = logging.getLogger(__name__)


class AssignmentSweep:
    _SEND_DELAY_SECONDS = 1.0
    _UPDATE_IN_PROGRESS = object()

    def __init__(self, pilot_roster, pilot_wire, utemezo):
        self._pilot_roster = pilot_roster
        self._pilot_wire = pilot_wire
        self._users_update_started = {}
        self._executor_service = utemezo
        self._lock = threading.Lock()
        log.info("AssignmentSweep initialization finished")

    def update_required(self, user_id: int) -> None:
        with self._lock:
            if user_id in self._users_update_started:
                return
            self._users_update_started[user_id] = AssignmentSweep._UPDATE_IN_PROGRESS

        user = self._pilot_roster.by_id(user_id)
        if user is not None:
            mission_book = user.pilot_of().tally_desk.mission_book

            def _send_missions():
                try:
                    user.send(self._pilot_wire.missions(mission_book))
                except Exception:
                    log.exception("Error in AssignmentSweep")
                finally:
                    self._users_update_started.pop(user_id, None)

            self._executor_service.after(self._SEND_DELAY_SECONDS, _send_missions)
        else:
            self._users_update_started.pop(user_id, None)


class BoostSweep:
    def __init__(self, pilot_roster):
        self._pilot_roster = pilot_roster
        self._pilot_wire = PilotReplies()

    def run(self) -> None:
        for user in self._pilot_roster.user_list(lambda u: u.is_connected()):
            removed_ids = user.pilot_of().factors.drop_expired()

            if len(removed_ids) != 0:
                removed_ids_bw = self._pilot_wire.remove_factor_ids(removed_ids)
                send_result = user.send(removed_ids_bw)


class _FactorExpiry:

    def __init__(self, user, factor, pilot_wire):
        self._user = user
        self._factor = factor
        self._pilot_wire = pilot_wire

    def __call__(self) -> None:
        self._user.pilot_of().factors.remove_item(self._factor.server_id)
        self._user.send(self._pilot_wire.remove_factor_ids([self._factor.server_id]))


class BoostExpiry:
    def __init__(self, utemezo_szal, pilot_wire, pilot_roster):
        self._scheduler = utemezo_szal
        self._pilot_wire = pilot_wire
        self._pilot_roster = pilot_roster

    def notify_factor_started(self, user_id: int, factor) -> None:
        user = self._pilot_roster.by_id(user_id)
        if user is None:
            log.info("BoostExpiry but playerID %s is not present", user_id)
            return
        lejarat = _FactorExpiry(user, factor, self._pilot_wire)
        hatra = (factor.end_time - datetime.now(timezone.utc)).total_seconds()
        self._scheduler.after(hatra, lejarat)

    def shutdown(self) -> None:
        self._scheduler.shutdown()
        if not self._scheduler.wait_until_stopped(0.2):
            self._scheduler.halt()


class IdleSweep:
    def __init__(self, pilot_roster, data_store, minutes_offline_before_kick: int, csapat_nyilvantarto=None):
        self._pilot_roster = pilot_roster
        self._data_store = data_store
        self._minutes_offline_before_kick = minutes_offline_before_kick
        self._party_registry = csapat_nyilvantarto
        self._lock = threading.Lock()

    def run(self) -> None:
        users_to_kick = []
        now = Stamp.now()
        for user in self._pilot_roster.values():
            if (connection := user.connection()) is not None:
                continue

            last_logout = user.pilot_of().last_logout
            if last_logout is None:
                log.error('a seat with no logout time on it - nothing to measure idleness against')
                continue
            duration = last_logout.duration(now)
            offline_minutes = int(duration.total_seconds() // 60)
            offline_long_enough = offline_minutes >= self._minutes_offline_before_kick
            if offline_long_enough:
                users_to_kick.append(user)

        for user in users_to_kick:
            self._let_go(user)

    def release(self, user_id: int) -> str:
        # A pilot who has left is held here until the sweep lets go of them,
        # and is written back from memory then - or handed that copy back if
        # they return - so a row written meanwhile by the panel would be lost.
        # The panel has them let go at once, before it writes.
        user = self._pilot_roster.by_id(user_id)
        if user is None:
            return "not_held"
        if user.connection() is not None:
            return "online"
        if self._let_go(user):
            return "released"
        return "online" if user.connection() is not None else "not_held"

    def _let_go(self, user) -> bool:
        with self._lock:
            if (user.connection() is not None
                    or self._pilot_roster.by_id(user.pilot_of().user_id_of()) is not user):
                return False
            if self._party_registry is not None:
                self._party_registry.remove_user_and_notify(user)
            self._data_store.store_pilot(user.pilot_of())
            self._pilot_roster.remove(user)
            return True


class TallySweep:
    def __init__(self, pilot_roster, pilot_wire):
        self._pilot_roster = pilot_roster
        self._pilot_wire = pilot_wire

    def run(self) -> None:
        usr_lst = self._pilot_roster.user_list(lambda user: user.is_connected())
        if len(usr_lst) == 0:
            return

        for user in usr_lst:
            player = user.pilot_of()
            counters = player.tally_desk.counters()
            if counters.require_update:
                user.send(self._pilot_wire.counters(counters))


class PeriodicSave:
    _SAVE_GAP_SECONDS = 2 * 60.0

    def __init__(self, pilotak, data_store):
        self._users = pilotak
        self._data_store = data_store

    def run(self) -> None:
        users_online = [user.pilot_of() for user in self._users.user_list(lambda u: u.is_connected())]

        if len(users_online) == 0:
            return

        self._data_store.store_pilots(users_online)

    def _get_requires_update(self, now, last, user) -> bool:
        requires_update = (now - last).total_seconds() > self._SAVE_GAP_SECONDS
        if requires_update:
            self._data_store.store_pilot(user.pilot_of())
            user.last_account_safe = now
        return requires_update
