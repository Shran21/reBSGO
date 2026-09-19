# github.com/Shran21
from __future__ import annotations

import logging
from enum import Enum

from rebsgo.protocol.wire_base import BgoProtocol
from rebsgo.protocol.protocol_id import ProtocolID

log = logging.getLogger(__name__)


def _tag(sorozat, value: int):
    tagok = list(sorozat)
    return tagok[value] if 0 <= value < len(tagok) else None


class _ClientMessage(Enum):
    UiElementShown = 0
    UiElementHidden = 1

    @staticmethod
    def from_code(value: int):
        return _tag(_ClientMessage, value)


class _UiElementId(Enum):
    ShopWindow = 0
    RepairWindow = 1
    ShipShop = 2
    ShipCustomizationWindow = 3
    HangarWindow = 4
    ChangeAmmoMenu = 5
    InflightShop = 6

    @staticmethod
    def from_code(value: int):
        return _tag(_UiElementId, value)


class FeedbackProtocol(BgoProtocol):
    def __init__(self, ctx):
        super().__init__(ProtocolID.Feedback, ctx)

    def read_message(self, msg_type: int, br) -> None:
        client_message = _ClientMessage.from_code(msg_type)
        if client_message is None:
            log.error('%s reported a window event nobody knows about: %s',
                      self.user().user_log_simple, msg_type)
            return

        ui_element_id = _UiElementId.from_code(br.read_uint16())

        log.debug('feedback channel: %s %s', client_message, ui_element_id)

        if ui_element_id in (_UiElementId.HangarWindow, _UiElementId.RepairWindow):
            player = self.user().pilot_of()
            hangar_ship = player.hangar_of().active_ship()
            player_protocol = self.user().protocol_of(ProtocolID.Pilot)
            self.user().send(player_protocol.replies.ship_info_durability(hangar_ship))
            self.user().send(player_protocol.replies.ship_slots(hangar_ship))
