# github.com/Shran21
from __future__ import annotations

from rebsgo.pilots.state.holdings.storages import BlackHole, EventShop, Hold, Locker, Mail, ShipSlot, Shop

import logging

from rebsgo.pilots.state.holdings.walks.storage_walk import StorageWalk, vezet_ide
from rebsgo.gamedata.ship_parts.parts import CountableItem
from rebsgo.journal import hivasi_lanc

log = logging.getLogger(__name__)


class EventShopWalk(StorageWalk):
    def __init__(self, user, transfer_request=None, dice=None):
        super().__init__(user, transfer_request, dice)
        self._from_event_shop = user.pilot_of().event_shop

    @vezet_ide(Hold)
    def _to_hold(self, hold) -> None:
        log.info('event-shop item into the hold')
        try:
            item_to_buy = self._from_event_shop.by_id(self.transfer_request.item_id)
            buy_count = self.transfer_request.count()
            buy_container = self.user.pilot_of().hold
            buy_price = self.purchase_price(item_to_buy, buy_container, buy_count)

            if buy_price is None:
                log.warning('event-shop purchase of %s x%s does not add up',
                            item_to_buy.card_guid_of(), buy_count)
                return

            log.info('event-shop sold %s x%s for %s', item_to_buy, buy_count, buy_price)

            self.take_payment(buy_price, buy_container, buy_count)
            item_to_buy = item_to_buy.copy()
            if isinstance(item_to_buy, CountableItem):
                item_to_buy.update_count(buy_count)

            self.add_ship_item(item_to_buy, hold)
        except ValueError as hibas_ertek:
            log.error(hivasi_lanc(hibas_ertek))

    @vezet_ide(Locker)
    def _to_locker(self, locker) -> None:
        self._nem_ide()
        log.warning('event-shop item heading to {}, pilot={}'.format(
            locker.container_id.container_type, self.user.user_log()))

    @vezet_ide(ShipSlot)
    def _into_slot(self, ship_slot) -> None:
        self._nem_ide()
        log.warning('event-shop item heading to {}, pilot={}'.format(
            ship_slot.container_id.container_type, self.user.user_log()))

    @vezet_ide(Shop)
    def _to_shop(self, shop) -> None:
        self._nem_ide()
        log.warning('event-shop item heading to {}, pilot={}'.format(
            shop.container_id.container_type, self.user.user_log()))

    @vezet_ide(Mail.MailStorage)
    def _to_mail(self, mail_container) -> None:
        self._nem_ide()
        log.warning('event-shop item heading to {}, pilot={}'.format(
            mail_container.container_id.container_type, self.user.user_log()))

    @vezet_ide(BlackHole)
    def _to_black_hole(self, black_hole) -> None:
        self._nem_ide()

    @vezet_ide(EventShop)
    def _to_event_shop(self, event_shop) -> None:
        self._nem_ide()
