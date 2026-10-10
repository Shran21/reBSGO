# github.com/Shran21
from __future__ import annotations

from rebsgo.protocol.arena.duel_wire import ArenaProtocol
from rebsgo.protocol.card_feed import CatalogueProtocol
from rebsgo.protocol.community.social_wire import CommunityProtocol
from rebsgo.protocol.debug.console_commands import DebugProtocol
from rebsgo.protocol.dialog.npc_talk import DialogProtocol
from rebsgo.protocol.feedback.ui_nudges import FeedbackProtocol
from rebsgo.protocol.game.space_commands import GameProtocol
from rebsgo.protocol.login import LoginProtocol
from rebsgo.protocol.notification import NotificationProtocol
from rebsgo.protocol.pilot.pilot_link import PlayerProtocol
from rebsgo.protocol.ranking import RankingProtocol
from rebsgo.protocol.room.station_rooms import RoomProtocol
from rebsgo.protocol.scene.scene_flow import SceneProtocol
from rebsgo.protocol.setting.preferences_wire import SettingProtocol
from rebsgo.protocol.shop.storefront import ShopProtocol
from rebsgo.protocol.story import StoryProtocol
from rebsgo.protocol.watching.stat_stream import SubscribeProtocol
from rebsgo.protocol.timing.clock_sync import SyncProtocol
from rebsgo.protocol.starmap import UniverseProtocol
from rebsgo.protocol.wheel import WofProtocol
from rebsgo.protocol.zone import ZoneProtocol
from rebsgo.helpers.locks import ReadWriteLock, Zarhato


class ProtocolDesk(Zarhato):
    def __init__(self, ctx, sector_book, data_store, kapu, csapat_nyilvantarto,
                 guild_registry, pilot_roster, level_curve, bontas_figyelo,
                 character_services, nemitas, kuldetes_frissito, visszaterito):
        self._ctx = ctx
        self._level_curve = level_curve
        self._sector_book = sector_book
        self._protocols = {}
        self._data_store = data_store
        self._party_registry = csapat_nyilvantarto
        self._guild_registry = guild_registry
        self._pilot_roster = pilot_roster
        self._character_services = character_services
        self._read_write_lock = ReadWriteLock()
        self._chat_access_blocker = nemitas
        self._refund_processor = visszaterito
        self._kapu = kapu
        self._mission_updater = kuldetes_frissito
        self._connection_closed_subscriber = bontas_figyelo
        self._user = None

        self._register_protocol(
            LoginProtocol(
                ctx,
                kapu,
                data_store,
                pilot_roster,
                self,
                bontas_figyelo,
                kuldetes_frissito))

    def protocol_of(self, protocol_id):
        if protocol_id is None:
            raise TypeError("a protocol_id is required")
        with self._olvasva:
            bgo_protocol = self._protocols.get(protocol_id)
            if bgo_protocol is None:
                raise KeyError(f'no protocol answers to {protocol_id}')
            return bgo_protocol

    _MEGNYITANDOK = (
        (PlayerProtocol, ('_ctx', '_pilot_roster', '_guild_registry',
                          '_character_services', '_data_store', '_level_curve')),
        (SyncProtocol, ('_ctx',)),
        (SceneProtocol, ('_ctx',)),
        (SettingProtocol, ('_ctx',)),
        (CatalogueProtocol, ('_ctx',)),
        (ShopProtocol, ('_ctx',)),
        (CommunityProtocol, ('_ctx', '_pilot_roster', '_party_registry',
                             '_guild_registry', '_chat_access_blocker', '_data_store')),
        (FeedbackProtocol, ('_ctx',)),
        (GameProtocol, ('_ctx', '_pilot_roster', '_sector_book')),
        (RoomProtocol, ('_ctx',)),
        (DialogProtocol, ('_ctx',)),
        (WofProtocol, ('_ctx',)),
        (UniverseProtocol, ('_ctx',)),
        (DebugProtocol, ('_ctx', '_pilot_roster', '_sector_book',
                         '_chat_access_blocker', '_refund_processor')),
        (SubscribeProtocol, ('_pilot_roster', '_ctx')),
        (RankingProtocol, ('_ctx',)),
        (ArenaProtocol, ('_ctx',)),
        (NotificationProtocol, ('_ctx',)),
        (StoryProtocol, ('_ctx',)),
        (ZoneProtocol, ('_ctx',)),
    )

    def login_done(self, user) -> None:
        with self._irva:
            self._user = user
            for fajta, kellekek in self._MEGNYITANDOK:
                self._register_protocol(
                    fajta(*(getattr(self, nev) for nev in kellekek)))

    def _register_protocol(self, bgo_protocol) -> None:
        if bgo_protocol.protocol_id_of() not in self._protocols:
            self._protocols[bgo_protocol.protocol_id_of()] = bgo_protocol
            bgo_protocol.seed_user(self._user)

    def all_protocols(self):
        return self._protocols.values()

    def restore_registry(self, user) -> None:
        with self._irva:
            self._user = user
            for bgo_protocol in user.protocol_desk.all_protocols():
                self._register_protocol(bgo_protocol)

    def on_gone(self) -> None:
        with self._irva:
            for ertek in self._protocols.values():
                ertek.on_gone()
