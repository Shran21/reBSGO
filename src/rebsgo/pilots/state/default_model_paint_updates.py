# github.com/Shran21
from __future__ import annotations

import functools

import logging
from dataclasses import dataclass, field

from rebsgo.services import Services
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.library import Catalogue
from rebsgo.gamedata.ship_parts.parts import ShipSystem
from rebsgo.gamedata.from_json.small_readers import DefaultModelPaintFallbackReader
from rebsgo.gamedata.reading import ShipSlotType

log = logging.getLogger(__name__)

_default_model_paint_fallbacks = None


@dataclass
class DefaultModelPaintUpdates:
    changed_slots: bool = False
    removed_from_locker: list[tuple[object, int]] = field(default_factory=list)
    added_to_locker: list[tuple[object, object]] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.changed_slots or bool(self.removed_from_locker) or bool(self.added_to_locker)


def normalize_default_model_paints(player, hangar_ship=None) -> DefaultModelPaintUpdates:
    updates = DefaultModelPaintUpdates()
    locker = player.locker
    catalogue = Services.get(Catalogue)
    ships = [hangar_ship] if hangar_ship is not None else player.hangar_of().all_hangar_ships()

    for ship in ships:
        if ship is None:
            continue
        _normalize_ship_default_model_paint(catalogue, locker, ship, updates)

    return updates


def _normalize_ship_default_model_paint(catalogue, locker, ship, updates: DefaultModelPaintUpdates) -> None:
    ship_card = ship.ship_card_of()
    ship_object_key = ship_card.ship_object_key
    paint_card_guid = _get_default_model_paint_fallbacks().paint_card_guid(ship_object_key)
    if paint_card_guid is None:
        return
    if not _is_valid_default_model_paint(catalogue, ship_object_key, paint_card_guid):
        return

    paint_slot = _find_paint_slot_by_slot_card(ship)
    if paint_slot is None:
        log.warning(
            "Default-model paint skipped; no ship_paint slot on shipServerId=%s shipCard=%s shipObjectKey=%s "
            "paintCard=%s",
            ship.server_id, ship_card.card_guid_of(), ship_object_key, paint_card_guid)
        return

    current_system = paint_slot.ship_system
    current_guid = 0 if current_system is None else current_system.card_guid_of()
    if current_guid == paint_card_guid:
        return

    if current_guid != 0:
        _ensure_default_paint_in_locker(locker, paint_card_guid, ship, updates)
        return

    default_paint_item = locker.by_guid(paint_card_guid)
    if isinstance(default_paint_item, ShipSystem):
        locker.take_item(default_paint_item.server_id)
        updates.removed_from_locker.append((locker, default_paint_item.server_id))
    else:
        default_paint_item = ShipSystem.from_guid(paint_card_guid)

    paint_slot.add_ship_item(default_paint_item)
    updates.changed_slots = True


def _ensure_default_paint_in_locker(locker, paint_card_guid: int, ship, updates: DefaultModelPaintUpdates) -> None:
    if locker.by_guid(paint_card_guid) is not None:
        return

    default_paint_item = locker.add_ship_item(ShipSystem.from_guid(paint_card_guid))
    if default_paint_item is None:
        return

    updates.added_to_locker.append((locker, default_paint_item))


def _find_paint_slot_by_slot_card(ship):
    for rekesz in ship.ship_slots.values():
        slot_card = rekesz.ship_slot_card()
        if slot_card is None:
            continue
        if slot_card.ship_slot_type == ShipSlotType.ship_paint:
            return rekesz
    return None


class _FestekAdatok:
    def __init__(self, catalogue, ship_object_key: int, paint_card_guid: int):
        self._catalogue = catalogue
        self.hajo = ship_object_key
        self.guid = paint_card_guid

    @functools.cached_property
    def festek(self):
        return self._catalogue.card_of(self.guid, CardView.ShipPaint)

    @functools.cached_property
    def rendszer(self):
        return self._catalogue.card_of(self.guid, CardView.ShipSystem)

    @functools.cached_property
    def hova_valo(self):
        hajo_kartya = self._catalogue.card_of(self.festek.ship_card_guid, CardView.Ship)
        return None if hajo_kartya is None else hajo_kartya.ship_object_key


_FESTEK_FELTETELEI = (
    (lambda a: a.festek is not None,
     lambda a: "nincs ilyen festék-kártya"),
    (lambda a: a.festek.uses_default_model,
     lambda a: "a festék nem az alapmodellre való"),
    (lambda a: a.hova_valo == a.hajo,
     lambda a: f"másik hajóé (az övé: {a.hova_valo})"),
    (lambda a: a.rendszer is not None,
     lambda a: "nincs hozzá rendszerkártya"),
    (lambda a: a.rendszer.ship_slot_type == ShipSlotType.ship_paint,
     lambda a: f"nem festék-rekeszbe való, hanem ide: {a.rendszer.ship_slot_type}"),
    (lambda a: not a.rendszer.object_key_barred(a.hajo),
     lambda a: "a rendszerkártya kizárja erről a hajóról"),
)


def _is_valid_default_model_paint(catalogue, ship_object_key: int, paint_card_guid: int) -> bool:
    adatok = _FestekAdatok(catalogue, ship_object_key, paint_card_guid)
    for teljesul, indoklas in _FESTEK_FELTETELEI:
        if teljesul(adatok):
            continue
        log.warning('default-model paint rejected (paint=%s, hull=%s): %s',
                    paint_card_guid, ship_object_key, indoklas(adatok))
        return False
    return True


def _get_default_model_paint_fallbacks():
    global _default_model_paint_fallbacks
    if _default_model_paint_fallbacks is None:
        _default_model_paint_fallbacks = DefaultModelPaintFallbackReader().fetch()
    return _default_model_paint_fallbacks
