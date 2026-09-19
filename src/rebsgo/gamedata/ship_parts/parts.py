# github.com/Shran21

from __future__ import annotations

from abc import abstractmethod
from rebsgo.helpers.gathering import Ownable
from rebsgo.geometry.maths.maths import Maths
from rebsgo.vocabulary.sorszamos_enum import SorszamosEnum
import datetime as _dt
from rebsgo.helpers.floats import FLOAT_MAX_VALUE


class ShipItem(Ownable):
    def __init__(self, card_guid, item_type: ItemType, server_id: int):
        if hasattr(card_guid, "card_guid_of"):
            card_guid = card_guid.card_guid_of()
        self.card_guid = card_guid
        self.item_type = item_type
        self._server_id = server_id

    def to_wire(self, bw) -> None:
        bw.write_uint16(self._server_id)
        bw.write_byte(self.item_type.value)
        if self.item_type is not ItemType.None_:
            bw.write_uint32(self.card_guid)

    @abstractmethod
    def copy(self) -> "ShipItem":
        ...

    @property
    def server_id(self) -> int:
        return self._server_id

    @server_id.setter
    def server_id(self, server_id: int) -> None:
        self._server_id = server_id

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self.card_guid == other.card_guid and self.item_type == other.item_type

    def __hash__(self) -> int:
        return hash((self.card_guid, self.item_type))

    def __repr__(self) -> str:
        return (f'<{self.item_type} #{self._server_id}, card {self.card_guid}>')

    def card_guid_of(self) -> int:
        return self.card_guid


class ShipItemBody:
    @staticmethod
    def to_wire(bw, arg) -> None:
        if arg is None or isinstance(arg, list):
            if arg is None:
                bw.write_length(0)
                return
            count = sum(1 for tetel in arg if tetel is not None)
            bw.write_length(count)
            for tetel in arg:
                if tetel is None:
                    continue
                ShipItemBody.to_wire(bw, tetel)
            return
        bw.write_byte(arg.item_type.value)
        if arg.item_type is not ItemType.None_:
            bw.write_uint32(arg.card_guid_of())
        if isinstance(arg, CountableItem):
            bw.write_uint32(arg.count())
        elif isinstance(arg, ShipSystem):
            bw.write_single(arg.durability)
            bw.write_double(arg.time_of_last_use)

    @staticmethod
    def write_none(bw) -> None:
        bw.write_byte(ItemType.None_.value)


class ShipConsumable:
    def __init__(self, item_countable: CountableItem, ship_consumable_card):
        self._item_countable = item_countable
        self._ship_consumable_card = ship_consumable_card

    @property
    def item_countable(self) -> CountableItem:
        return self._item_countable

    @property
    def ship_consumable_card(self):
        return self._ship_consumable_card


MAX_VALUE = 4294967295
MIN_VALUE = 0


class CountableItem(ShipItem):

    def __init__(self, card_guid: int, count: int, server_id: int):
        super().__init__(card_guid, ItemType.Countable, server_id)
        if count < 0:
            raise ValueError('count below zero makes no sense')
        self._count = 0
        self.update_count(count)

    @staticmethod
    def from_guid(guid, count) -> "CountableItem":
        from rebsgo.vocabulary.pilot import ResourceKind

        if isinstance(guid, ResourceKind):
            guid = guid.guid
        return CountableItem(guid, int(count), 0)

    @staticmethod
    def stand_in() -> "CountableItem":
        return CountableItem.from_guid(0, 0)

    def copy(self) -> "CountableItem":
        return CountableItem(self.card_guid, self.count(), self.server_id)

    def update_count(self, uj_darab: int) -> None:
        self._count = Maths.clamp_safe(uj_darab, MIN_VALUE, MAX_VALUE)

    def grow_count(self, novekmeny: int) -> None:
        if novekmeny < 0:
            return
        self.update_count(self._count + novekmeny)

    def shrink_count(self, levonas: int) -> None:
        self.update_count(self._count - levonas)

    def count(self) -> int:
        return self._count

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_uint32(self._count)

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        if not super().__eq__(other):
            return False
        return self._count == other._count

    def __hash__(self) -> int:
        return hash((super().__hash__(), self._count))

    def __repr__(self) -> str:
        return (f'<{self._count} x {self.item_type} #{self.server_id},'
                f' card {self.card_guid}>')


class ItemType(SorszamosEnum):
    None_ = 0
    System = 1
    Countable = 2
    Starter = 3
    Ship = 4


def write_ship_item(bw, ship_item: ShipItem) -> None:
    bw.write_byte(ship_item.item_type.value)
    bw.write_desc(ship_item)


def write_ship_items(bw, targy_lista) -> None:
    if targy_lista is None:
        bw.write_uint16(0)
        return
    darab = sum(1 for tetel in targy_lista if tetel is not None)
    bw.write_uint16(darab)
    for tetel in targy_lista:
        if tetel is None:
            continue
        write_ship_item(bw, tetel)


def one_item_of_guid(guid: int) -> ShipItem:
    from rebsgo.services import Services
    from rebsgo.gamedata.cards.card_view import CardView
    from rebsgo.gamedata.library import Catalogue

    kartya = Services.get(Catalogue).card_of(guid, CardView.Price)
    if kartya is None:
        raise ValueError(f'price card absent for guid {guid}')
    return ship_item_for_guid(kartya.shop_category.type, guid, 1)


def ship_item_for_guid(item_type, guid: int, count: int) -> ShipItem:
    if item_type is ItemType.System:

        return ShipSystem.from_guid(guid)
    if item_type is ItemType.Countable:
        return CountableItem.from_guid(guid, count)
    if item_type is ItemType.Ship:
        from rebsgo.gamedata.ship_parts.shop_ship import ShopShip

        return ShopShip(guid, 0)
    raise RuntimeError(f'item kind {item_type} has no implementation')


def countable_for_guid(guid: int, count: int) -> CountableItem:
    return CountableItem.from_guid(guid, count)


class StarterPack(ShipItem):
    def __init__(self, card_guid: int, server_id: int):
        super().__init__(card_guid, ItemType.Starter, server_id)

    def copy(self) -> ShipItem:
        return StarterPack(self.card_guid, self.server_id)


_UTC = _dt.timezone.utc


class ShipSystem(ShipItem):
    def __init__(self, card_guid: int, durability: float, time_of_last_use: float, server_id: int,
                 item_type: ItemType = ItemType.System):
        super().__init__(card_guid, item_type, server_id)
        self._durability = durability
        self._time_of_last_use = time_of_last_use
        self._ship_system_card = None

    def __repr__(self) -> str:
        return "<ShipSystem " + f"ship_system_card={self._ship_system_card}, item_type={self.item_type}" + ">"

    @property
    def durability(self) -> float:
        if self._ship_system_card is not None and self._ship_system_card.cannot_break:
            self.restore_durability()
        return self._durability

    @durability.setter
    def durability(self, durability: float) -> None:
        self._durability = Maths.clamp_safe(durability, 0, self._ship_system_card.durability)

    @property
    def ship_system_card(self):
        return self._ship_system_card

    @property
    def time_of_last_use(self) -> float:
        return self._time_of_last_use

    @property
    def time_of_last_use_local_date_time(self) -> _dt.datetime:
        return _dt.datetime.fromtimestamp(int(self._time_of_last_use * 1000) / 1000.0, tz=_UTC)

    @property
    def wrecked(self) -> bool:
        return self._durability == 0

    @staticmethod
    def by_server_id_(server_id: int) -> "ShipSystem":
        return ShipSystem(0, 0, 0, server_id, ItemType.None_)

    def copy(self) -> ShipItem:
        return ShipSystem.from_guid(self.card_guid)

    @staticmethod
    def from_guid(card_guid: int) -> "ShipSystem":
        from rebsgo.services import Services
        from rebsgo.gamedata.cards.card_view import CardView
        from rebsgo.gamedata.library import Catalogue

        rendszer = ShipSystem(card_guid, FLOAT_MAX_VALUE, 0, 0)
        kartya = Services.get(Catalogue).card_of(card_guid, CardView.ShipSystem)
        if kartya is None:
            raise ValueError(f'no card answers to this id {card_guid}')
        rendszer.take_system_card(kartya)
        rendszer.durability = rendszer._ship_system_card.durability
        return rendszer

    def last_upkeep_of(self) -> float:
        return getattr(self, "_time_of_last_upkeep", 0.0)

    def note_upkeep(self, seconds: float) -> None:
        self._time_of_last_upkeep = seconds

    def note_use(self, value=None) -> None:
        if value is None:
            self._time_of_last_use = _dt.datetime.now(_UTC).timestamp()
        elif isinstance(value, _dt.datetime):
            dt = value if value.tzinfo is not None else value.replace(tzinfo=_UTC)
            self._time_of_last_use = int(dt.timestamp() * 1000) * 0.001
        else:
            self._time_of_last_use = value * 0.001

    def quality(self) -> float:
        if self._ship_system_card is not None:
            return self.durability / self._ship_system_card.durability
        return 1.0

    def restore_durability(self) -> None:
        self.durability = self._ship_system_card.durability

    def take_system_card(self, ship_system_card) -> None:
        if ship_system_card is None:
            raise TypeError('a system card is required')
        self._ship_system_card = ship_system_card

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        if self.item_type is not ItemType.None_:
            bw.write_single(self._durability)
            bw.write_double(self._time_of_last_use)

    def wear_down(self, decrease_value: float) -> None:
        if self._ship_system_card is not None and self._ship_system_card.cannot_break:
            return
        if self._durability == 0:
            return
        self.durability = self._durability - decrease_value

    def _durability_gap(self) -> float:
        return self._ship_system_card.durability * (1.0 - self.quality())
