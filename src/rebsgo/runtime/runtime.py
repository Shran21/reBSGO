# github.com/Shran21

from __future__ import annotations

import logging

from rebsgo.runtime.server_handles import ServerHandles
from rebsgo.runtime.protocol_desk import ProtocolDesk
from rebsgo.runtime.incoming_loop import IncomingLoop
from rebsgo.runtime.presence import PresenceCrier
from rebsgo.protocol.debug.refunds import Refunds
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.helpers.dice import Dice

log = logging.getLogger(__name__)


class Runtime:
    def __init__(self, workers, server_config, galaxy, data_store, kapu,
                 csapat_nyilvantarto, guild_registry, fogado, pilot_roster, sector_book,
                 level_curve, timetable, merok, nemitas,
                 kuldetes_frissito, catalogue, beallitas):
        self._workers = workers
        self._timetable = timetable
        self._server_config = server_config
        self._galaxy = galaxy
        self._data_store = data_store
        self._kapu = kapu
        self._party_registry = csapat_nyilvantarto
        self._guild_registry = guild_registry
        self._server_listener = fogado
        self._sector_book = sector_book
        self._server_listener.on_listener_event(self)
        self._pilot_roster = pilot_roster
        self._presence = PresenceCrier(pilot_roster)
        self._level_curve = level_curve
        self._merok = merok
        self._chat_access_blocker = nemitas
        self._mission_updater = kuldetes_frissito
        self._catalogue = catalogue
        self._configuration = beallitas

    def on_new_link(self, uj_vonal) -> None:
        ctx = ServerHandles(
            uj_vonal,
            self._catalogue,
            self._server_config,
            self._timetable,
            self._merok,
            Dice(),
            self._galaxy,
            None)

        protocol_desk = ProtocolDesk(
            ctx,
            self._sector_book,
            self._data_store,
            self._kapu,
            self._party_registry,
            self._guild_registry,
            self._pilot_roster,
            self._level_curve,
            self,
            self._configuration.character_services(),
            self._chat_access_blocker,
            self._mission_updater,
            Refunds(self._catalogue))
        protocol_updater = IncomingLoop(uj_vonal, protocol_desk)
        self._workers.launch(protocol_updater.run)

    def start(self) -> None:
        self._workers.launch(self._server_listener.run)

    def shutdown_process(self) -> None:
        log.info("FrontDoor stopping...")
        self._server_listener.shutdown()
        log.info("FrontDoor stopped")

        log.info('disconnecting every pilot still inside...')
        all_online_users = self._pilot_roster.user_set(lambda u: u.is_connected())

        try:
            players_to_save = [u.pilot_of() for u in all_online_users if u.pilot_of() is not None]
            if players_to_save:
                self._data_store.store_pilots(players_to_save)
                log.info("Saved %s online players before shutdown", len(players_to_save))
        except Exception:
            log.exception("Failed to save online players on shutdown")

        for user in all_online_users:
            try:
                scene_protocol = user.protocol_of(ProtocolID.Scene)
                disconnect_bw = scene_protocol.push_disconnect()
                user.send(disconnect_bw)
            except KeyError:
                log.exception("telling a pilot about the shutdown failed")

        still_online = self._pilot_roster.user_set(lambda u: u.is_connected())
        for online_user in still_online:
            if online_user.connection() is not None:
                online_user.connection().close_connection('a pilot was still inside when shutdown ran')
        log.info('every pilot is out')

        log.info("SectorBook stopping...")
        self._sector_book.shutdown()
        log.info("SectorBook stopped")

        log.info('saving guilds...')
        self._data_store.write_guilds(self._guild_registry)
        log.info('guilds saved')

        log.info('shutdown begins')
        terminated = False
        try:
            self._workers.shutdown()
            terminated = self._workers.wait_until_stopped(5)
        except Exception as ex:
            log.info('shutdown was interrupted', exc_info=ex)
        log.info('shutdown complete {}'.format(terminated))

    def on_gone(self, user) -> None:
        ismert_user = self._pilot_roster.by_id(user.pilot_of().user_id_of())
        if ismert_user is not None:
            self._presence.left(user.pilot_of())
            user.protocol_desk.on_gone()
            self._data_store.store_pilot(user.pilot_of())
