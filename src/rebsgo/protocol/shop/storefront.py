# github.com/Shran21
from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum

from rebsgo.services import Services
from rebsgo.protocol.wire_base import BgoProtocol
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.vocabulary.pilot import ServerRoles
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.library import Catalogue
from rebsgo.gamedata.ship_parts.parts import CountableItem, ShipSystem
from rebsgo.gamedata.ship_parts.shop_ship import ShopShip
from rebsgo.gamedata.from_json.event_shop_template_reader import EventShopTemplateReader, ShopBlacklists
from rebsgo.gamedata.reading import ShipSlotType, ShopCategory
from rebsgo.gamedata.from_json.template_readers import shop_weapon_keys

log = logging.getLogger(__name__)

_event_shop_template = None
_shop_blacklists = None

_WEAPON_KEYS = shop_weapon_keys()
_CAPITAL_WEAPON_KEY_PREFIX = _WEAPON_KEYS.capital_prefix
_CARRIER_WEAPON_KEY_PREFIX = _WEAPON_KEYS.carrier_prefix
_STEALTH_WEAPON_KEY_PREFIX = _WEAPON_KEYS.stealth_prefix


def _get_event_shop_template():
    global _event_shop_template
    if _event_shop_template is None:
        _event_shop_template = EventShopTemplateReader().fetch_event_shop_template()
    return _event_shop_template


def _get_shop_blacklists():
    global _shop_blacklists
    if _shop_blacklists is None:
        _shop_blacklists = EventShopTemplateReader().fetch_shop_blacklists()
    return _shop_blacklists


class _ClientMessage(Enum):
    Items = 1
    Close = 11
    BoughtShipSaleOffer = 13
    EventShopItems = 15
    AllSales = 17

    @staticmethod
    def from_code(value: int):
        return _CM_BY_VALUE.get(value)


class _ServerMessage(Enum):
    Items = 2
    Sales = 3
    UpgradeSales = 4
    ShopPrices = 8
    BoughtShipSaleOffer = 12
    EventShopItems = 14
    EventShopAvailable = 16


_CM_BY_VALUE = {member.value: member for member in _ClientMessage}


class ShopProtocol(BgoProtocol):
    def __init__(self, ctx):
        super().__init__(ProtocolID.Shop, ctx)
        self._catalogue = Services.get(Catalogue)
        if self.ctx.server_config.starter_params.testing_mode:
            blacklists = ShopBlacklists.empty()
        else:
            blacklists = _get_shop_blacklists()
        self._ship_black_list = set(blacklists.ship_guids)
        self._consumable_blacklist = set(blacklists.consumable_guids)
        self._system_black_list = set(blacklists.system_guids)
        self._shop = None
        self._event_shop = None

    def seed_user(self, user) -> None:
        super().seed_user(user)
        self._shop = self._build_shop()
        self._build_event_shop()

    def read_message(self, msg_type: int, br) -> None:
        client_message = _ClientMessage.from_code(msg_type)
        if client_message is None:
            return

        log.debug('inbound message: %s', client_message)

        if client_message == _ClientMessage.EventShopItems:
            log.debug('shipping the event-shop stock out')
            self.user().send(self.event_shop_items(self._event_shop))
        elif client_message == _ClientMessage.Close:
            log.error('%sshop close: nothing implements it', self.user().pilot_of().player_log)
        elif client_message == _ClientMessage.AllSales:
            self.user().send(self._push_sales())
            self.user().send(self._push_upgrade_sales())
        elif client_message == _ClientMessage.Items:
            try:
                self.user().send(self._push_shop_items(self._shop))
            except ValueError:
                log.exception("the shop handler fell over")
            self.user().send(self.push_event_shop(_get_event_shop_template().card_guid, True))
        else:
            log.error('%sshop path without an implementation %s', self.user().user_log(),
                      client_message)

    def _build_event_shop(self) -> None:
        player = self.user().pilot_of()
        self._event_shop = player.event_shop
        self._event_shop.wipe_ship_items()

        tetelek = []

        sablon = _get_event_shop_template()
        forgatas = list(sablon.system_items)
        if sablon.include_all_paints:
            paint_guids = sorted(
                kartya.card_guid_of()
                for kartya in self._catalogue.all_cards_of_view(CardView.ShipPaint)
                if (kartya.card_guid_of() not in self._system_black_list
                    and self._catalogue.card_of(kartya.card_guid_of(), CardView.ShipSystem) is not None))
            darab = sablon.rotation_count or len(paint_guids)
            if sablon.rotate_daily and paint_guids:
                kezdet = (datetime.now(timezone.utc).timetuple().tm_yday * darab) % len(paint_guids)
                forgatas.extend(paint_guids[(kezdet + i) % len(paint_guids)]
                                for i in range(min(darab, len(paint_guids))))
            else:
                forgatas.extend(paint_guids[:darab])
        for system_guid in forgatas:
            try:
                tetelek.append(ShipSystem.from_guid(system_guid))
            except ValueError as e:
                log.warning("Skipping event shop system guid=%s: %s", system_guid, e)
        for card_guid, darab in sablon.countable_items:
            tetelek.append(CountableItem.from_guid(card_guid, darab))

        self._event_shop.add_ship_items(tetelek)

    @staticmethod
    def _shop_sort_key(price_card):
        return (price_card.sorting_weight or 0, tuple(price_card.sorting_names or []))

    def _build_shop(self):
        player = self.user().pilot_of()
        shop = player.shop
        shop.wipe_ship_items()

        all_system_cards = self._catalogue.all_cards_of_view(CardView.ShipSystem)
        all_associated_price_cards = self._catalogue.all_cards_of_view(CardView.Price)

        pending = []

        for kartya in all_associated_price_cards:
            buy_price = kartya.buy_price
            if buy_price.empty:
                continue

            if kartya.shop_category == ShopCategory.Ship:
                if kartya.card_guid_of() not in self._ship_black_list:
                    pending.append((self._shop_sort_key(kartya), ShopShip(kartya.card_guid_of(), 0)))
            if (kartya.shop_category == ShopCategory.Consumable
                or kartya.shop_category == ShopCategory.Resource
                or kartya.shop_category == ShopCategory.Augment):
                if kartya.card_guid_of() not in self._consumable_blacklist:
                    pending.append((self._shop_sort_key(kartya),
                                    CountableItem.from_guid(kartya.card_guid_of(), 1)))

        for sys_card in all_system_cards:
            if sys_card.card_guid_of() in self._system_black_list:
                continue

            existing_price_card = self._catalogue.card_of(sys_card.card_guid_of(), CardView.Price)
            if existing_price_card is None:
                continue

            if (sys_card.card_guid_of() == 225
                and not self.user().pilot_of().bgo_admin_roles.holds_any_role(
                        ServerRoles.Developer, ServerRoles.CommunityManager)):
                continue

            gui_card = self._catalogue.card_of(sys_card.card_guid_of(), CardView.GUI)
            key = gui_card.key if gui_card is not None else ""
            sort_key = self._shop_sort_key(existing_price_card)

            if key.startswith(_CAPITAL_WEAPON_KEY_PREFIX):
                pending.append((sort_key, ShipSystem.from_guid(sys_card.card_guid_of())))
                continue

            if sys_card.ship_slot_type in (ShipSlotType.gun, ShipSlotType.launcher,
                                           ShipSlotType.defensive_weapon):
                if ((key.startswith(_CARRIER_WEAPON_KEY_PREFIX) or key.startswith(_STEALTH_WEAPON_KEY_PREFIX))
                    and sys_card.level == 1):
                    pending.append((sort_key, ShipSystem.from_guid(sys_card.card_guid_of())))
                continue

            if sys_card.level == 1 or sys_card.ship_slot_type == ShipSlotType.avionics:
                if (sys_card.ship_slot_type == ShipSlotType.avionics
                    and self.owned_in_hold_locker_or_slot(sys_card.card_guid_of(), self.user())):
                    continue

                pending.append((sort_key, ShipSystem.from_guid(sys_card.card_guid_of())))
            if self.ctx.server_config.starter_params.testing_mode:
                if sys_card.level == 10:
                    pending.append((sort_key, ShipSystem.from_guid(sys_card.card_guid_of())))
                if sys_card.level == 15:
                    pending.append((sort_key, ShipSystem.from_guid(sys_card.card_guid_of())))

        pending.sort(key=lambda entry: entry[0])
        for _sort_key, tetel in pending:
            shop.add_ship_item(tetel)
        return shop

    def owned_in_hold_locker_or_slot(self, targy_guid: int, user) -> bool:
        jatekos = self.user().pilot_of()
        if any(tarolo.by_guid(targy_guid) is not None
               for tarolo in (jatekos.hold, jatekos.locker)):
            return True
        return any(rekesz.ship_system is not None
                   and rekesz.ship_system.card_guid_of() == targy_guid
                   for hajo in jatekos.hangar_of().all_hangar_ships()
                   for rekesz in hajo.ship_slots.values())

    def _push_sales(self):
        bw = self.new_message()
        bw.write_msg_type(_ServerMessage.Sales.value)
        bw.write_length(0)
        return bw

    def _push_shop_items(self, shop):
        bw = self.new_message()
        bw.write_msg_type(_ServerMessage.Items.value)
        bw.write_desc(shop)
        return bw

    def _push_upgrade_sales(self):
        bw = self.new_message()
        bw.write_msg_type(_ServerMessage.UpgradeSales.value)
        bw.write_length(0)
        return bw

    def event_shop_items(self, event_shop):
        bw = self.new_message()
        bw.write_msg_type(_ServerMessage.EventShopItems.value)
        bw.write_desc(event_shop)
        return bw

    def push_event_shop(self, card_guid: int, bekapcsolva: bool):
        bw = self.new_message()
        bw.write_msg_type(_ServerMessage.EventShopAvailable.value)
        bw.write_guid(card_guid)
        bw.write_boolean(bekapcsolva)
        return bw
