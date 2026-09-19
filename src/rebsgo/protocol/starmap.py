# github.com/Shran21

from __future__ import annotations

from enum import Enum
from rebsgo.protocol.wire_base import BgoProtocol
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.reply_base import ReplyBase
import logging


class GalaxyChange(Enum):
    Rcp = 1
    ConquestLocation = 2
    ConquestPrice = 3
    SectorOutpostPoints = 4
    SectorMiningShips = 5
    SectorPvPKills = 6
    SectorDynamicMissions = 7
    SectorOutpostState = 8
    SectorBeaconState = 9
    SectorJumpTargetTransponders = 10
    SectorPlayerSlots = 11

    @staticmethod
    def from_code(value: int):
        return _galaxy_change_BY_VALUE.get(value)
_galaxy_change_BY_VALUE = {member.value: member for member in GalaxyChange}


class ServerMessage(Enum):
    Update = 7

    @property
    def int_value(self) -> int:
        return self._value_

    def to_wire(self, bw) -> None:
        bw.write_msg_type(self._value_)

    @classmethod
    def from_code(cls, value: int) -> "ServerMessage | None":
        return _server_message_BY_VALUE.get(value)
_server_message_BY_VALUE = {member.value: member for member in ServerMessage}


log = logging.getLogger(__name__)


class _ClientMessage(Enum):
    SubscribeGalaxyMap = 5
    UnsubscribeGalaxyMap = 6

    @staticmethod
    def from_code(value: int):
        return _CM_BY_VALUE.get(value)
_CM_BY_VALUE = {member.value: member for member in _ClientMessage}


class UniverseProtocol(BgoProtocol):
    def __init__(self, ctx):
        super().__init__(ProtocolID.Universe, ctx)
        self._id = 0
        self._faction = None

    def seed_user(self, user) -> None:
        super().seed_user(user)
        self._faction = self.user().pilot_of().faction

    def read_message(self, msg_type: int, br) -> None:
        client_message = _ClientMessage.from_code(msg_type)
        if client_message is None:
            return

        self._id = self.user().pilot_of().user_id_of()

        if client_message == _ClientMessage.SubscribeGalaxyMap:
            self.ctx.galaxy.watch_with(self)
        elif client_message == _ClientMessage.UnsubscribeGalaxyMap:
            self.ctx.galaxy.remove_subscriber(self)

    def on_gone(self) -> None:
        super().on_gone()
        self.ctx.galaxy.remove_subscriber(self)

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)

    @property
    def id(self) -> int:
        return self._id

    @property
    def faction(self):
        return self._faction

    def map_changed(self, terkep_valaszok) -> None:
        if self.user() is None or not self.user().is_connected():
            log.info('dropping a star-map watcher whose pilot is no longer around')
            self.ctx.galaxy.remove_subscriber(self)
            return

        self.user().send(terkep_valaszok)


class StarmapReplies(ReplyBase):
    UZENETEK = {
        "updates": (ServerMessage.Update.value, [('desc_collection', 'galaxy_map_updates')]),
    }

    def __init__(self):
        super().__init__(ProtocolID.Universe)

    def update(self, galaxy_map_update):
        return self.updates([galaxy_map_update])
