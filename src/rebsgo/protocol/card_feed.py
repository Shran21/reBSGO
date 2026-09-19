# github.com/Shran21
from __future__ import annotations

import logging
from copy import copy

from rebsgo.protocol.wire_base import BgoProtocol
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.vocabulary.world import WellKnownCard
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.cards.ship_cards import ShipCard, ShipCardBrief

log = logging.getLogger(__name__)

_SHIP_OBJECT_KEY_ALIAS_VIEWS = {
    CardView.GUI,
    CardView.World,
    CardView.Price,
    CardView.Movement,
    CardView.Owner,
    CardView.Camera,
    CardView.Ship,
    CardView.ShipLight,
}


class CatalogueProtocol(BgoProtocol):
    def __init__(self, ctx):
        super().__init__(ProtocolID.Catalogue, ctx)
        self._catalogue = ctx.catalogue

        ship_lst_colo = self._catalogue.card_of(WellKnownCard.ShipListCardColonial.value, CardView.ShipList)
        ship_lst_cylo = self._catalogue.card_of(WellKnownCard.ShipListCardCylon.value, CardView.ShipList)
        if ship_lst_colo is None or ship_lst_cylo is None:
            raise TypeError('ship-list cards absent; catalogue boot halts')

    def read_message(self, msg_type: int, br) -> None:
        if msg_type != 1:
            log.error('{}catalogue met a message kind it does not know: {}'.format(self.user().user_log(), msg_type))
            return

        read_len = br.read_uint16()
        for _i in range(read_len):
            guid = br.read_uint32()
            raw_view = br.read_uint16()
            if raw_view == 0:
                log.warning('card view zero is not a view')
            view = CardView.from_code(raw_view)
            if view is None:
                raise OSError(f'card view unresolvable, dropping the link; value {raw_view}')

            bw = self._catalogue.replies(guid, view)
            user_send_flag = True
            if bw is None:
                kartya = self.card_of(raw_view, guid)
                if kartya is not None:
                    try:
                        bw = self.write_card(kartya)
                    except Exception as card_write_error:
                        log.error("Skipping card guid=%s view=%s, serialization failed: %s",
                                  guid, raw_view, card_write_error)
                        user_send_flag = False
                    else:
                        self._catalogue.register_writer(guid, CardView.from_code(raw_view), bw)
                else:
                    log.error('a card we do not have stays unsent: {} {} asked by {}'.format(
                        guid, raw_view, self.user().user_log() if self.user() else '?'))
                    user_send_flag = False
            if user_send_flag and self.user() is not None:
                self.user().send(bw)

    def card_of(self, card_view: int, card_guid: int):
        view = CardView.from_code(card_view)
        if view is None:
            return None

        fetched_card = self._catalogue.card_of(card_guid, view)
        if fetched_card is None and view == CardView.ShipLight:
            if (ship_card := self._catalogue.card_of(card_guid, CardView.Ship)) is not None:
                ship_card_light = ShipCardBrief(
                    card_guid,
                    ship_card.ship_object_key,
                    ship_card.tier,
                    ship_card.ship_roles,
                    ship_card.ship_role_deprecated)
                self._catalogue.take_card(ship_card_light)
                return ship_card_light

        if fetched_card is None:
            fetched_card = self._fetch_card_by_ship_object_key(card_guid, view)

        if fetched_card is None:
            return fetched_card

        if isinstance(fetched_card, ShipCard):
            return self._ship_card_filter(fetched_card)
        return fetched_card

    def _fetch_card_by_ship_object_key(self, ship_object_key: int, view: CardView):
        if view not in _SHIP_OBJECT_KEY_ALIAS_VIEWS:
            return None
        ship_card = self._find_ship_card_by_object_key(ship_object_key)
        if ship_card is None:
            return None

        if (keszito := self._SAJAT_ALNEVEK.get(view)) is not None:
            return keszito(self, ship_object_key, ship_card)

        fetched_card = self._catalogue.card_of(ship_card.card_guid_of(), view)
        if fetched_card is None:
            return None
        return self._alias_card(ship_object_key, fetched_card)

    _SAJAT_ALNEVEK = {
        CardView.Ship:
            lambda self, kulcs, kartya: self._alias_ship_card(kulcs, kartya),
        CardView.ShipLight:
            lambda self, kulcs, kartya: ShipCardBrief(
                kulcs, kartya.ship_object_key, kartya.tier,
                kartya.ship_roles, kartya.ship_role_deprecated),
    }

    def _find_ship_card_by_object_key(self, ship_object_key: int):
        get_by_object_key = getattr(self._catalogue, "ship_cards_by_object_key", None)
        ship_cards = (get_by_object_key(ship_object_key) if get_by_object_key is not None
                      else self._catalogue.all_cards_of_view(CardView.Ship))
        jeloltek = [
            card for card in ship_cards
            if isinstance(card, ShipCard)
            and card.ship_object_key == ship_object_key
            and self._ship_card_filter(card) is not None
        ]
        if not jeloltek:
            return None

        jeloltek.sort(key=lambda card: (card.level != 1, card.level, card.card_guid_of()))
        return jeloltek[0]

    def _fetch_ship_card_by_object_key(self, ship_object_key: int):
        ship_card = self._find_ship_card_by_object_key(ship_object_key)
        if ship_card is None:
            return None
        return self._alias_ship_card(ship_object_key, ship_card)

    @staticmethod
    def _alias_card(card_guid: int, card):
        alias = copy(card)
        alias.card_guid = card_guid
        return alias

    @staticmethod
    def _alias_ship_card(card_guid: int, ship_card: ShipCard) -> ShipCard:
        return ShipCard(
            card_guid,
            ship_card.ship_object_key,
            ship_card.level,
            ship_card.hangar_id,
            ship_card.max_level,
            ship_card.level_requirement,
            ship_card.durability,
            ship_card.tier,
            ship_card.ship_roles,
            ship_card.ship_role_deprecated,
            ship_card.paperdoll_ui_layoutfile,
            ship_card.ship_slot_cards,
            ship_card.cubits_only_repair,
            ship_card.variant_hangar_ids,
            ship_card.parent_hangar_id,
            ship_card.stats_of,
            ship_card.faction,
            ship_card.immutable_slots,
            ship_card.next_ship_card_guid,
        )

    def _ship_card_filter(self, ship_card):
        if ship_card.hangar_id != -1:
            return ship_card
        return None

    def write_card(self, card):
        bw = self.new_message()
        bw.write_uint16(2)
        bw.write_desc(card)
        return bw

    def write_card_cached(self, card):
        if card is None:
            return None
        bw = self._catalogue.replies(card.card_guid_of(), card.card_view)
        if bw is not None:
            return bw
        bw = self.write_card(card)
        self._catalogue.register_writer(card.card_guid_of(), card.card_view, bw)
        return bw
