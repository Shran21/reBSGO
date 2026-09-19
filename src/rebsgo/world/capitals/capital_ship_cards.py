# github.com/Shran21
from __future__ import annotations

from rebsgo.services import Services
from rebsgo.world.capitals.capital_roster import COLONIAL_CAPITAL_GUID, CYLON_CAPITAL_GUID, is_capital_guid
from rebsgo.gamedata.from_json.template_readers import module_bindings
from rebsgo.gamedata.reading import AbilityActionKind
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.library import Catalogue


CAPITAL_SHIP_CARD_VIEWS = (
    CardView.Ship,
    CardView.GUI,
    CardView.Price,
    CardView.Camera,
    CardView.World,
    CardView.Owner,
    CardView.Movement,
    CardView.ShipLight,
)

CAPITAL_MODULE_CARD_GUIDS_BY_SHIP = {
    guid: module_bindings(AbilityActionKind).capital_guids()
    for guid in (COLONIAL_CAPITAL_GUID, CYLON_CAPITAL_GUID)
}


def _card_key(card_guid: int, view: CardView) -> tuple[int, CardView]:
    return card_guid, view


def _append_card_buffer(buffers: list, catalogue_protocol, catalogue, card_guid: int, view: CardView,
                        seen_keys: set | None = None) -> None:
    if seen_keys is not None:
        kulcs = _card_key(card_guid, view)
        if kulcs in seen_keys:
            return
        seen_keys.add(kulcs)
    kartya = catalogue.card_of(card_guid, view)
    if kartya is None:
        return
    write_card = getattr(catalogue_protocol, "write_card_cached", None)
    if write_card is None:
        write_card = catalogue_protocol.write_card
    if (bw := write_card(kartya)) is not None:
        buffers.append(bw)


def build_capital_ship_card_buffers(user, ship_guid: int, seen_keys: set | None = None) -> list:
    if user is None or not is_capital_guid(ship_guid):
        return []

    catalogue_protocol = user.protocol_of(ProtocolID.Catalogue)
    if catalogue_protocol is None:
        return []

    catalogue = Services.get(Catalogue)
    buffers = []
    for view in CAPITAL_SHIP_CARD_VIEWS:
        _append_card_buffer(buffers, catalogue_protocol, catalogue, ship_guid, view, seen_keys)
    for module_guid in CAPITAL_MODULE_CARD_GUIDS_BY_SHIP.get(ship_guid, ()):
        _append_card_buffer(buffers, catalogue_protocol, catalogue, module_guid, CardView.Module, seen_keys)
    return buffers


def send_capital_ship_cards(user, ship_guid: int) -> bool:
    buffers = build_capital_ship_card_buffers(user, ship_guid)
    if buffers:
        user.send(buffers)
    return bool(buffers)


def send_capital_ship_cards_for_guids(user, hull_guids) -> bool:
    sent = False
    for ship_guid in hull_guids or ():
        sent = send_capital_ship_cards(user, ship_guid) or sent
    return sent


def build_ship_module_binding_card_buffers(user, space_object, seen_keys: set | None = None) -> list:
    if user is None or space_object is None:
        return []
    get_bindings = getattr(space_object, "bindings_of", None)
    if get_bindings is None:
        return []
    bindings = get_bindings()
    if bindings is None:
        return []
    module_guids = {b.module_guid for b in bindings.module_binding_list}
    if not module_guids:
        return []
    catalogue_protocol = user.protocol_of(ProtocolID.Catalogue)
    if catalogue_protocol is None:
        return []
    catalogue = Services.get(Catalogue)
    buffers = []
    for module_guid in sorted(module_guids):
        _append_card_buffer(buffers, catalogue_protocol, catalogue, module_guid, CardView.Module, seen_keys)
    return buffers


def send_ship_module_binding_cards(user, space_object) -> bool:
    buffers = build_ship_module_binding_card_buffers(user, space_object)
    if buffers:
        user.send(buffers)
    return bool(buffers)
