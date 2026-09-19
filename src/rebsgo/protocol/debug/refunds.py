# github.com/Shran21

from __future__ import annotations

import logging
from rebsgo.vocabulary.pilot import ResourceKind
from rebsgo.helpers.floats import f32


log = logging.getLogger(__name__)


class Refunds:
    def __init__(self, catalogue):
        self._catalogue = catalogue

    def summed_price_for_levels(self, lvl1_guid: int):
        system_price_map = self._get_all_cards_for_refund_item(lvl1_guid)
        price_map_for_each_level = self._get_all_card_prices(system_price_map)
        price_map_for_each_level_summed_to_the_level = self._get_all_card_prices_summed_up(price_map_for_each_level)
        return price_map_for_each_level_summed_to_the_level

    def _get_all_card_prices_summed_up(self, price_map_for_each_level):
        result_map = {}
        summed_value = 0.0
        for kulcs, ertek in price_map_for_each_level.items():
            summed_value = f32(summed_value + ertek)
            result_map[kulcs] = summed_value
        return result_map

    def _get_all_cards_for_refund_item(self, initial_guid: int):
        elso = self._catalogue.price_cards(initial_guid)
        system_price_cards_map = {}
        system_price_cards_map[elso.ship_system_card.level] = elso

        mostani = elso
        while mostani.usable and mostani.ship_system_card.next_card_guid != 0:
            nxt = self._catalogue.price_cards(mostani.ship_system_card.next_card_guid)
            system_price_cards_map[nxt.ship_system_card.level] = nxt
            mostani = nxt

        return system_price_cards_map

    def _get_all_card_prices(self, system_price_map):
        result_map = {}
        for price_cards in system_price_map.values():
            if price_cards.ship_system_card.next_card_guid == 0:
                continue

            shop_item_card = price_cards.shop_item_card
            cubits_price = shop_item_card.upgrade_price.for_faction(ResourceKind.Cubits.guid)
            result_map[price_cards.ship_system_card.level + 1] = cubits_price

        return result_map
