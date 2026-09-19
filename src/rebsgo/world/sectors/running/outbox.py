# github.com/Shran21
from __future__ import annotations

import logging

from rebsgo.services import Services
from rebsgo.world.capitals.capital_ship_cards import (
    build_capital_ship_card_buffers,
    build_ship_module_binding_card_buffers,
)
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.protocol_book_replies import game_replies
from rebsgo.vocabulary.world import DepartureCause, ObjectKind
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.library import Catalogue
from rebsgo.helpers.rolling_latency_stats import (
    ENABLED as GUARDRAILS_ENABLED,
    SENDER_BROADCAST_PREFREEZE_ENABLED,
    SECTOR_ENTRY_OBJECT_WARN_COUNT,
    SECTOR_ENTRY_PACKET_WARN_COUNT,
    SECTOR_TIMER_WARN_INTERVAL_MS,
    elapsed_ms,
    now_ms,
    should_warn_count,
    should_warn_interval,
)

log = logging.getLogger(__name__)

JUMP_BEACON_CARD_VIEWS = (
    CardView.Ship,
    CardView.Price,
    CardView.World,
    CardView.Owner,
    CardView.GUI,
    CardView.Movement,
    CardView.ShipLight,
)


class _EntryPayloadStream:
    def __init__(self, sender, objektumok, user):
        self._sender = sender
        self._user = user
        self._started_ms = now_ms() if GUARDRAILS_ENABLED else 0.0
        self._space_objects = sender._prepare_entry_space_objects(objektumok, user)
        self._joining_player_id = sender._joining_player_id(user)
        self._should_purge_stale_objects = user is not None and user.was_sent_space_objects
        self._seen_card_keys = set()
        self._index = 0
        self._done = False
        self._stats = {
            "sector": sender._sector_id,
            "user_id": self._joining_player_id,
            "objects": len(self._space_objects),
            "purged": 0,
            "card_packets": 0,
            "who_is_packets": 0,
            "state_packets": 0,
            "movement_packets": 0,
            "payload_packets": 0,
            "elapsed_ms": 0.0,
            "chunks": 0,
            "remaining_objects": len(self._space_objects),
        }
        if user is not None:
            user.mark_sent_space_objects()

    def send_next(self, max_objects: int | None = None) -> bool:
        if self._done:
            return True
        if self._index >= len(self._space_objects):
            self._finish()
            return True

        if max_objects is None or max_objects <= 0:
            vege = len(self._space_objects)
        else:
            vege = min(len(self._space_objects), self._index + max_objects)
        darabka = self._space_objects[self._index:vege]
        counts = self._sender._send_entry_payload_chunk(
            darabka,
            self._user,
            self._joining_player_id,
            self._should_purge_stale_objects,
            self._seen_card_keys,
        )
        self._index = vege
        self._stats["purged"] += counts["purged"]
        self._stats["card_packets"] += counts["card_packets"]
        self._stats["who_is_packets"] += counts["who_is_packets"]
        self._stats["state_packets"] += counts["state_packets"]
        self._stats["movement_packets"] += counts["movement_packets"]
        self._stats["payload_packets"] += counts["payload_packets"]
        self._stats["chunks"] += 1
        self._stats["remaining_objects"] = len(self._space_objects) - self._index
        if self._index >= len(self._space_objects):
            self._finish()
            return True
        self._sender._record_entry_payload_stats(self._stats)
        return False

    def drain_all(self) -> None:
        while not self.send_next(0):
            pass

    @property
    def finished(self) -> bool:
        return self._done

    def user(self):
        return self._user

    def _finish(self) -> None:
        if GUARDRAILS_ENABLED:
            self._stats["elapsed_ms"] = elapsed_ms(self._started_ms)
        self._stats["remaining_objects"] = 0
        self._done = True
        self._sender._record_entry_payload_stats(self._stats)
        self._sender._warn_entry_payload_if_needed(self._stats)


class SectorOutbox:
    def __init__(self, pilotak, sector_id=None):
        self._users = pilotak
        self._sector_id = sector_id
        self._space_replies = game_replies()
        self._last_entry_payload_warn_ms = 0.0
        self._last_entry_payload_stats = {}

    def has_clients(self) -> bool:
        if self._users is None:
            return False
        ures = getattr(self._users, 'empty', None)
        if ures is not None:
            return not ures
        users_collection = getattr(self._users, "users_of", None)
        if users_collection is None:
            return False
        return any(True for _ in users_collection())

    def push_to_everyone(self, arg) -> None:
        if isinstance(arg, list):
            if not arg:
                return
            self._prefreeze_shared_payload(arg)
            for user_client in self._users.users_of():
                self.push_buffers_to(arg, user_client)
        else:
            self._prefreeze_shared_payload(arg)
            self.send_to_clients(arg, self._users.users())

    def send_to_clients(self, bw, vonalak) -> None:
        if isinstance(bw, list) and not bw:
            return
        self._prefreeze_shared_payload(bw)
        for user in vonalak:
            self.push_to(bw, user)

    def push_buffers_to(self, csomagok, user) -> None:
        if user is None or (isinstance(csomagok, list) and not csomagok):
            return
        user.send(csomagok)

    def push_to(self, bw, pilota) -> None:
        pilota.send(bw)

    @staticmethod
    def _prefreeze_shared_payload(payload) -> None:
        if not SENDER_BROADCAST_PREFREEZE_ENABLED:
            return
        if isinstance(payload, (list, tuple)):
            for packet in payload:
                SectorOutbox._prefreeze_packet(packet)
            return
        SectorOutbox._prefreeze_packet(payload)

    @staticmethod
    def _prefreeze_packet(packet) -> None:
        if (freeze := getattr(packet, 'frozen_bytes', None)) is not None:
            freeze()

    @staticmethod
    def _send_space_object_cards_to_user(space_object, user) -> None:
        buffers = SectorOutbox._space_object_card_buffers_for_user(space_object, user, set())
        if buffers:
            user.send(buffers)

    @staticmethod
    def _jump_beacon_card_buffers_for_user(space_object, user, seen_keys: set | None = None) -> list:
        if user is None:
            return []
        catalogue_protocol = user.protocol_of(ProtocolID.Catalogue)
        if catalogue_protocol is None:
            return []
        catalogue = Services.get(Catalogue)
        card_guid = space_object.world_card().card_guid_of()
        buffers = []
        for view in JUMP_BEACON_CARD_VIEWS:
            if seen_keys is not None:
                kulcs = (card_guid, view)
                if kulcs in seen_keys:
                    continue
                seen_keys.add(kulcs)
            if (kartya := catalogue.card_of(card_guid, view)) is not None:
                write_card = getattr(catalogue_protocol, "write_card_cached", None)
                if write_card is None:
                    write_card = catalogue_protocol.write_card
                if (bw := write_card(kartya)) is not None:
                    buffers.append(bw)
        return buffers

    def _write_who_is_for_user(self, space_object, user):
        return self._space_replies.who_is(space_object)

    @staticmethod
    def _needs_own_ship_module_refresh(space_object) -> bool:
        if space_object is None or not space_object.is_player():
            return False
        bindings = space_object.bindings_of()
        if bindings is None or not bindings.module_binding_list:
            return False
        paint_card = bindings.ship_system_paint_card
        return paint_card is None or paint_card.uses_default_model

    def refresh_own_ship_modules_after_visibility(self, space_object, user) -> None:
        if user is None or space_object is None:
            return
        player = user.pilot_of()
        if player is None or player.user_id_of() != space_object.pilot_id():
            return
        if not self._needs_own_ship_module_refresh(space_object):
            return

        setting_protocol = user.protocol_of(ProtocolID.Setting)
        if setting_protocol is None:
            return

        settings = player.settings.server_saved_user_settings
        settings.apply_render_defaults()
        self.push_to(setting_protocol.replies.settings(settings), user)

    def send_who_is_to_all(self, space_object) -> None:
        for user in self._users.users_of():
            self.push_to(self._write_who_is_for_user(space_object, user), user)

    def send_space_object_cards_to_all(self, space_object) -> None:
        for user in self._users.users_of():
            self._send_space_object_cards_to_user(space_object, user)

    def stream_objects_to(self, objektumok, user) -> None:
        self.create_space_objects_entry_stream(objektumok, user).drain_all()

    def create_space_objects_entry_stream(self, objektumok, user):
        return _EntryPayloadStream(self, objektumok, user)

    @staticmethod
    def _joining_player_id(user):
        return user.pilot_of().user_id_of() if user is not None and user.pilot_of() is not None else None

    def _prepare_entry_space_objects(self, objektumok, user) -> list:
        objektumok = list(objektumok)
        if (joining_player_id := self._joining_player_id(user)) is not None:
            objektumok.sort(
                key=lambda so: 0 if so.is_player() and so.pilot_id() == joining_player_id else 1)
        return objektumok

    def _send_entry_payload_chunk(self, objektumok, user, joining_player_id, should_purge_stale_objects,
                                  seen_card_keys: set) -> dict:
        card_bws = []
        who_is_bws = []
        state_bws = []
        movement_bws = []

        purge_ids = []

        for space_object in objektumok:
            if should_purge_stale_objects and not (
                    space_object.is_player() and space_object.pilot_id() == joining_player_id):
                purge_ids.append(space_object.id_in_space())
            card_bws.extend(self._space_object_card_buffers_for_user(space_object, user, seen_card_keys))
            who_is_bws.append(self._write_who_is_for_user(space_object, user))
            state_bws.append(
                self._space_replies.space_object_state(space_object.world_state_of()))
            mover = space_object.mover_of()
            if mover.is_moving_object and mover.frame_tick is not None:
                try:
                    bw = self._space_replies.initial_sync_move(space_object)
                    movement_bws.append(bw)
                except ValueError as hibas_ertek:
                    log.error('while pushing the full movement state', exc_info=hibas_ertek)
            else:
                if not space_object.space_entity_type.of_kind(
                        ObjectKind.Asteroid, ObjectKind.Planetoid, ObjectKind.Planet):
                    if space_object.mover_of().frame_tick is not None:
                        movement_bws.append(self._space_replies.initial_move(space_object))
                    elif space_object.space_entity_type.of_kind(
                            ObjectKind.JumpBeacon, ObjectKind.JumpBeacon):
                        movement_bws.append(self._space_replies.initial_move(space_object))

        purge_count = len(purge_ids)
        if purge_ids:
            card_bws.insert(0, self._space_replies.object_left_ids(
                purge_ids, DepartureCause.JustRemoved))
        self.push_buffers_to(card_bws, user)

        card_packet_count = len(card_bws)
        who_is_packet_count = len(who_is_bws)
        state_packet_count = len(state_bws)
        movement_packet_count = len(movement_bws)
        object_bws = who_is_bws
        object_bws.extend(state_bws)
        object_bws.extend(movement_bws)
        self.push_buffers_to(object_bws, user)
        payload_packet_count = card_packet_count + len(object_bws)
        return {
            "purged": purge_count,
            "card_packets": card_packet_count,
            "who_is_packets": who_is_packet_count,
            "state_packets": state_packet_count,
            "movement_packets": movement_packet_count,
            "payload_packets": payload_packet_count,
        }

    def _record_entry_payload_stats(self, stats: dict) -> None:
        self._last_entry_payload_stats = dict(stats)

    def _warn_entry_payload_if_needed(self, stats: dict) -> None:
        object_count = stats["objects"]
        payload_packet_count = stats["payload_packets"]
        self._last_entry_payload_stats = {
            "sector": self._sector_id,
            "user_id": stats["user_id"],
            "objects": object_count,
            "purged": stats["purged"],
            "card_packets": stats["card_packets"],
            "who_is_packets": stats["who_is_packets"],
            "state_packets": stats["state_packets"],
            "movement_packets": stats["movement_packets"],
            "payload_packets": payload_packet_count,
            "elapsed_ms": stats["elapsed_ms"],
            "chunks": stats["chunks"],
            "remaining_objects": stats["remaining_objects"],
        }
        if (GUARDRAILS_ENABLED
            and (should_warn_count(object_count, SECTOR_ENTRY_OBJECT_WARN_COUNT)
             or should_warn_count(payload_packet_count, SECTOR_ENTRY_PACKET_WARN_COUNT))
            and should_warn_interval(self._last_entry_payload_warn_ms, SECTOR_TIMER_WARN_INTERVAL_MS)):
            self._last_entry_payload_warn_ms = now_ms()
            log.warning(
                "High sector entry payload sector=%s user_id=%s objects=%s purged=%s card_packets=%s "
                "who_is_packets=%s state_packets=%s movement_packets=%s payload_packets=%s "
                "chunks=%s object_threshold=%s packet_threshold=%s elapsed_ms=%.1f",
                self._sector_id,
                stats["user_id"],
                object_count,
                stats["purged"],
                stats["card_packets"],
                stats["who_is_packets"],
                stats["state_packets"],
                stats["movement_packets"],
                payload_packet_count,
                stats["chunks"],
                SECTOR_ENTRY_OBJECT_WARN_COUNT,
                SECTOR_ENTRY_PACKET_WARN_COUNT,
                stats["elapsed_ms"],
            )

    @staticmethod
    def _space_object_card_buffers_for_user(space_object, user, seen_card_keys: set | None = None) -> list:
        buffers = []
        if user is None or space_object is None:
            return buffers
        if space_object.is_player():
            buffers.extend(build_capital_ship_card_buffers(
                user, space_object.world_card().card_guid_of(), seen_card_keys))
        if space_object.space_entity_type.of_kind(
                ObjectKind.JumpBeacon, ObjectKind.JumpBeacon):
            buffers.extend(SectorOutbox._jump_beacon_card_buffers_for_user(space_object, user, seen_card_keys))
        buffers.extend(build_ship_module_binding_card_buffers(user, space_object, seen_card_keys))
        return buffers

    def users(self):
        return self._users

    @property
    def last_entry_payload_stats(self) -> dict:
        return dict(self._last_entry_payload_stats)

    def shutdown(self) -> None:
        pass
