# github.com/Shran21

from __future__ import annotations

from rebsgo.gamedata import json_helper as jh
from rebsgo.gamedata.cards.card_base import write_layout, Card
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.reading import FrozenPrice, Price, ShopCategory, ShopItemKind
from rebsgo.vocabulary.pilot import Faction
from rebsgo.vocabulary.world import EventGoalKind


class EventShopCard(Card):
    def __init__(self, card_guid: int, shop_name_cylon: str, shop_name_colonial: str, shop_description_cylon: str,
                 shop_description_colonial: str, hiany_uzenet: str, shop_error_cannot_buy: str,
                 esemeny_keszlet):
        super().__init__(card_guid, CardView.EventShop)
        self.shop_name_cylon = shop_name_cylon
        self.shop_name_colonial = shop_name_colonial
        self.shop_description_cylon = shop_description_cylon
        self.shop_description_colonial = shop_description_colonial
        self.shop_error_missing_ressources = hiany_uzenet
        self.shop_error_cannot_buy = shop_error_cannot_buy
        self.event_ressources = esemeny_keszlet

    @classmethod
    def from_json(cls, obj: dict) -> "EventShopCard":
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_text(obj, "shopNameCylon"),
            jh.as_text(obj, "shopNameColonial"),
            jh.as_text(obj, "shopDescriptionCylon"),
            jh.as_text(obj, "shopDescriptionColonial"),
            jh.as_text(obj, "shopErrorMissingRessources"),
            jh.as_text(obj, "shopErrorCannotBuy"),
            jh.as_long_list(obj, "eventRessources") or [],
        )

    _HUZALREND = (
        ('string', 'shop_name_cylon'),
        ('string', 'shop_name_colonial'),
        ('string', 'shop_description_cylon'),
        ('string', 'shop_description_colonial'),
        ('string', 'shop_error_missing_ressources'),
        ('string', 'shop_error_cannot_buy'),
        ('uint32_collection', 'event_ressources'),
    )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        write_layout(self, bw, EventShopCard._HUZALREND)


class GlobalBonusEventCard(Card):
    def __init__(self, card_guid: int, colonial_zaszlo: int, cylon_zaszlo: int):
        super().__init__(card_guid, CardView.GlobalBonusEvent)
        self.banner_card_colonial = colonial_zaszlo
        self.banner_card_cylon = cylon_zaszlo

    @classmethod
    def from_json(cls, obj: dict) -> "GlobalBonusEventCard":
        return cls(jh.as_long(obj, "cardGUID"), jh.as_long(obj, "bannerCardColonial"),
                   jh.as_long(obj, "bannerCardCylon"))

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_boolean(False)
        bw.write_uint32(self.banner_card_colonial)
        bw.write_uint32(self.banner_card_cylon)


class SectorEventCard(Card):
    def __init__(self, card_guid: int, name_cylon: str, name_colonial: str, description_cylon: str,
                 description_colonial: str, task_type, is_elite: bool, radius: float):
        super().__init__(card_guid, CardView.SectorEvent)
        self.name_cylon = name_cylon
        self.name_colonial = name_colonial
        self.description_cylon = description_cylon
        self.description_colonial = description_colonial
        self.task_type = task_type
        self.is_elite = is_elite
        self.radius = radius

    @classmethod
    def from_json(cls, obj: dict) -> "SectorEventCard":
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_text(obj, "nameCylon"),
            jh.as_text(obj, "nameColonial"),
            jh.as_text(obj, "descriptionCylon"),
            jh.as_text(obj, "descriptionColonial"),
            jh.as_enum_by_name(obj, "taskType", EventGoalKind),
            jh.as_flag(obj, "isElite"),
            jh.as_float(obj, "radius"),
        )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_string(self.name_cylon)
        bw.write_string(self.name_colonial)
        bw.write_string(self.description_cylon)
        bw.write_string(self.description_colonial)
        bw.write_byte(self.task_type.value)
        bw.write_boolean(False)
        bw.write_single(self.radius)


class ShopItemCard(Card):
    def __init__(self, card_guid: int, shop_category, shop_item_type, tier: int, faction,
                 sorting_names, sorting_weight: int, buy_price, upgrade_price, sell_price, can_be_sold: bool):
        super().__init__(card_guid, CardView.Price)
        self.shop_category = shop_category
        self.shop_item_type = shop_item_type
        self.tier = tier
        self._faction = faction
        self.sorting_names = sorting_names
        self.sorting_weight = sorting_weight
        self._buy_price = buy_price
        self._upgrade_price = upgrade_price
        self._sell_price = sell_price
        self.can_be_sold = can_be_sold

    @classmethod
    def from_json(cls, obj: dict) -> "ShopItemCard":
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_enum_by_name(obj, "Category", ShopCategory),
            jh.as_enum_by_name(obj, "ItemType", ShopItemKind),
            jh.as_byte(obj, "Tier"),
            jh.as_enum_by_name(obj, "Faction", Faction),
            jh.as_text_list(obj, "SortingNames"),
            jh.as_int(obj, "SortingWeight"),
            jh.as_price(obj, "BuyPrice"),
            jh.as_price(obj, "UpgradePrice"),
            jh.as_price(obj, "SellPrice"),
            jh.as_flag(obj, "CanBeSold"),
        )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        safe_category = ShopCategory.Unknown if self.shop_category is None else self.shop_category
        safe_item_type = ShopItemKind.Unknown if self.shop_item_type is None else self.shop_item_type
        safe_faction = Faction.Neutral if self._faction is None else self._faction
        safe_sorting_names = [] if self.sorting_names is None else self.sorting_names

        bw.write_byte(safe_category.value)
        bw.write_byte(safe_item_type.value)
        bw.write_byte(self.tier)
        bw.write_byte(safe_faction.value)
        bw.write_string_array(safe_sorting_names)
        bw.write_uint16(self.sorting_weight)
        bw.write_desc(Price() if self._buy_price is None else self._buy_price)
        bw.write_desc(Price() if self._upgrade_price is None else self._upgrade_price)
        bw.write_desc(Price() if self._sell_price is None else self._sell_price)
        bw.write_boolean(self.can_be_sold)

    @property
    def buy_price(self) -> Price:
        return FrozenPrice(self._buy_price)

    @property
    def upgrade_price(self) -> Price:
        return FrozenPrice(self._upgrade_price)

    @property
    def sell_price(self) -> Price:
        return FrozenPrice(self._sell_price)

    @property
    def sellable(self) -> bool:
        return self.can_be_sold

    @property
    def faction(self) -> Faction:
        return self._faction


class SpecialOfferCard(Card):
    def __init__(self, card_guid: int, json_key: str, offer_icon_path: str, offer_image_path_colonial: str,
                 offer_image_path_cylon: str, item_group: int):
        super().__init__(card_guid, CardView.ConversionCampaign)
        self.json_key = json_key
        self.offer_icon_path = offer_icon_path
        self.offer_image_path_colonial = offer_image_path_colonial
        self.offer_image_path_cylon = offer_image_path_cylon
        self.item_group = item_group

    @classmethod
    def from_json(cls, obj: dict) -> "SpecialOfferCard":
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_text(obj, "jsonKey"),
            jh.as_text(obj, "offerIconPath"),
            jh.as_text(obj, "offerImagePathColonial"),
            jh.as_text(obj, "getOfferImagePathCylon"),
            jh.as_long(obj, "itemGroup"),
        )

    _HUZALREND = (
        ('string', 'json_key'),
        ('string', 'offer_icon_path'),
        ('string', 'offer_image_path_colonial'),
        ('string', 'offer_image_path_cylon'),
        ('uint32', 'item_group'),
    )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        write_layout(self, bw, SpecialOfferCard._HUZALREND)


class StarterCard(Card):
    def __init__(self, card_guid: int, faction, ship_texture: str, linked_hull_guid: int,
                 fire_power: int, tough_ness: int, speed: int, electronic_warfare: int):
        super().__init__(card_guid, CardView.Starter)
        self.faction = faction
        self.ship_texture = ship_texture
        self.connected_ship_card_guid = linked_hull_guid
        self.fire_power = fire_power
        self.tough_ness = tough_ness
        self.speed = speed
        self.electronic_warfare = electronic_warfare

    @classmethod
    def from_json(cls, obj: dict) -> "StarterCard":
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_enum_by_name(obj, "faction", Faction),
            jh.as_text(obj, "shipTexture"),
            jh.as_long(obj, "connectedShipCardGuid"),
            jh.as_byte(obj, "firePower"),
            jh.as_byte(obj, "toughNess"),
            jh.as_byte(obj, "speed"),
            jh.as_byte(obj, "electronicWarfare"),
        )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_string("")
        bw.write_string("")
        bw.write_byte(self.faction.value)
        bw.write_string(self.ship_texture)
        bw.write_guid(self.connected_ship_card_guid)
        bw.write_byte(self.fire_power)
        bw.write_byte(self.tough_ness)
        bw.write_byte(self.speed)
        bw.write_byte(self.electronic_warfare)


class StarterKitCard(Card):
    def __init__(self, card_guid: int, hull_card_guid: int, items):
        super().__init__(card_guid, CardView.StarterPack)
        self.ship_card_guid = hull_card_guid
        self.items = items

    @classmethod
    def from_json(cls, obj: dict) -> "StarterKitCard":
        return cls(jh.as_long(obj, "cardGUID"), jh.as_long(obj, "shipCardGuid"),
                   jh.as_ship_items(obj, "items"))

    def to_wire(self, bw) -> None:
        bw.write_guid(self.ship_card_guid)
        bw.write_desc_array(list(self.items) if self.items is not None else [])
