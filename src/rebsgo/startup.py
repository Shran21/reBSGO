# github.com/Shran21
from __future__ import annotations

import atexit
import logging

from rebsgo.gamedata.upgrades import remember_augment_templates
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.assignments import seed_missions
from rebsgo.gamedata.ship_setups import free_ids
from rebsgo.gamedata.from_json.loaders import UpgradeLoader, AssignmentLoader, ShipSetupLoader
from rebsgo.vocabulary.world import WellKnownCard
from rebsgo.journal import hivasi_lanc

log = logging.getLogger(__name__)


def _async_exit(code: int) -> None:
    log.error("async exit requested (code {})".format(code))


class Startup:
    def __init__(self, chat_api, chat_server, login_server_listener, collider_plans,
                 server_settings, game_server, catalogue, sector_book):
        self._chat_api = chat_api
        self._chat_server = chat_server
        self._login_server_listener = login_server_listener
        self._collider_templates = collider_plans
        self._server_settings = server_settings
        self._game_server = game_server
        self._catalogue = catalogue
        self._sector_book = sector_book
        self.stopped = False

    def on_start_up(self, indulo_esemeny=None) -> None:
        try:
            self.vilag_felepitese()
        except Exception as ex:
            stack_trace = hivasi_lanc(ex)
            log.error('boot sequence fell over: %s\n%s', ex, stack_trace)
            _async_exit(-1)

    def on_stop(self, ev=None) -> None:
        import time
        import threading
        log.warning('shutting down {} (across {} threads)'.format(int(time.time() * 1000), threading.current_thread().name))

    def pre_destroy(self) -> None:
        self.on_shutdown()

    def on_shutdown(self) -> None:
        if self.stopped:
            log.info('the shutdown is already under way')
            return
        self.stopped = True

        sorrend = (("the login door", self._login_server_listener.stop),
                   ("the chat backend", self._chat_server.stop),
                   ("the game world", self._game_server.shutdown_process))
        for mit, lezar in sorrend:
            log.info("closing %s", mit)
            lezar()
        log.info("the server is down, all of it")

    def vilag_felepitese(self) -> None:
        ship_config_reader = ShipSetupLoader()
        ship_config_reader.load_now()
        free_config_ids = free_ids()
        log.info('ship-config ids still unused: {}'.format(free_config_ids))
        log.info('loading assignment templates')
        try:
            seed_missions(AssignmentLoader().mission_templates())
        except RuntimeError as ex:
            log.error("ERROR IN SETUP AssignmentSpecs! {}".format(str(ex)))
            _async_exit(-1)

        log.info('assignment templates loaded')

        world_cards = self._catalogue.all_cards_of_view(CardView.World)

        unique_names = set()
        for world_card in world_cards:
            unique_names.add(world_card.prefab_name)
        self._collider_templates.stand_in_asteroid_colliders(unique_names)

        map_card = self._catalogue.card_of(WellKnownCard.GalaxyMap, CardView.GalaxyMap)
        if map_card is None:
            log.error('the galaxy map card is nowhere to be found')
            _async_exit(-1)

        augment_template_reader = UpgradeLoader()
        augment_template_map = augment_template_reader.all_augment_templates()
        remember_augment_templates(augment_template_map)

        self._login_server_listener.start()

        self._chat_server.start()

        try:
            if self._server_settings.chat_backend_wanted:
                self._chat_api.start()
        except Exception:
            log.exception("the chat backend would not start")

        log.info('bringing the server up...')
        self._game_server.start()
        self._sector_book.start_all_sectors()
        log.info('server is up')

        atexit.register(self.on_shutdown)
