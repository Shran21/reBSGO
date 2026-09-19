# github.com/Shran21

from __future__ import annotations

import logging
from rebsgo.protocol.messages import PilotReply
from rebsgo.gamedata.ship_parts.parts import CountableItem, ItemType, ShipConsumable, ShipSystem
from rebsgo.helpers.locks import ReadWriteLock, Zarhato
from rebsgo.helpers.log_tags import tag
from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.helpers.gathering import TwoWayMap, Ownable
import datetime
from enum import Enum
from rebsgo.wire.bytes.stamp import Stamp
from rebsgo.services import Services
from rebsgo.pilots.state.pilot_bits import ShipAbility
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.library import Catalogue
from rebsgo.gamedata.reading import ShipSlotType
from rebsgo.wire.bytes.incoming import Incoming
from abc import abstractmethod


log = logging.getLogger(__name__)


class MailBox(TwoWayMap, Outgoing):
    def __init__(self, items: dict[int, Mail] | None = None):
        super().__init__({} if items is None else items)

    def to_wire(self, bw) -> None:
        bw.write_desc_collection(self._items.values())


class MailState(Enum):
    Normal = 0
    Unread = 1


class ShipSlots:
    def __init__(self, slots: dict[int, ShipSlot] | None = None):
        self._slots: dict[int, ShipSlot] = {} if slots is None else slots

    @property
    def pairs(self):
        return self._slots.items()

    def avionic_slot(self):
        for rekesz in self._slots.values():
            ss = rekesz.ship_system
            if ss is not None and ss.ship_system_card is not None \
                    and ss.ship_system_card.ship_slot_type == ShipSlotType.avionics:
                return rekesz
        return None

    def paint_slot(self):
        for rekesz in self._slots.values():
            ss = rekesz.ship_system
            if ss is not None and ss.ship_system_card is not None \
                    and ss.ship_system_card.ship_slot_type == ShipSlotType.ship_paint:
                return rekesz
        return None

    def slot(self, slot_id: int):
        return self._slots.get(slot_id)

    def take_slot(self, ship_slot: ShipSlot) -> None:
        self._slots[ship_slot.ship_system.server_id] = ship_slot

    def values(self):
        return self._slots.values()


class StorageName(Incoming):
    def __init__(self, container_type: StorageKind):
        self._container_type = container_type

    @property
    def container_type(self) -> StorageKind:
        return self._container_type


class Storage(Outgoing):
    def __init__(self, container_id: StorageName):
        if container_id is None:
            raise TypeError('a container id is required')
        self.container_id = container_id

    def place_in_container(self, container_id: StorageName) -> None:
        self.container_id = container_id

    @abstractmethod
    def by_id(self, id: int):
        ...

    @abstractmethod
    def all_items_ids(self) -> set:
        ...

    @abstractmethod
    def take_item(self, item_id: int):
        ...

    @abstractmethod
    def add_ship_item(self, ship_item):
        ...


def container_of(br, player):
    i_container_id = container_id_from_wire(br)
    fajta = i_container_id.container_type

    if (mezo := _sajat_tarolok().get(fajta)) is not None:
        return getattr(player, mezo)
    if fajta == StorageKind.ShipSlot:
        ship = player.hangar_of().by_server_id(i_container_id.ship_id)
        slot = ship.ship_slots.slot(i_container_id.slot_id)
        slot.place_in_container(i_container_id)
        return slot
    if fajta == StorageKind.Mail:
        mail_container_id = MailName()
        mail_container_id.read(br)
        mail = player.mail_box.by_id(mail_container_id.mail_id)
        if mail is None:
            raise ValueError('mail absent')
        return mail.mail_container
    raise RuntimeError(f'no container backs this kind: {i_container_id}')


def container_id_from_wire(br):
    container_type = StorageKind.from_code(br.read_byte())
    container_id = None
    if container_type == StorageKind.Hold:
        container_id = HoldName()
    elif container_type == StorageKind.Locker:
        container_id = LockerName()
    elif container_type == StorageKind.Mail:
        container_id = MailName()
    elif container_type == StorageKind.ShipSlot:
        container_id = SlotName()
    elif container_type == StorageKind.BlackHole:
        container_id = BlackHoleName()
    elif container_type == StorageKind.Shop:
        container_id = ShopName()
    elif container_type == StorageKind.EventShop:
        container_id = EventShopName()
    if container_id is None:
        raise ValueError(f'no container kind matches {container_type}')
    container_id.read(br)
    return container_id


class BlackHoleName(StorageName):
    def __init__(self):
        super().__init__(StorageKind.BlackHole)

    def read(self, br) -> None:
        pass


class EventShopName(StorageName):
    def __init__(self):
        super().__init__(StorageKind.EventShop)

    def read(self, br) -> None:
        pass


class HoldName(StorageName):
    def __init__(self):
        super().__init__(StorageKind.Hold)

    def read(self, br) -> None:
        pass


class LockerName(StorageName):
    def __init__(self):
        super().__init__(StorageKind.Locker)

    def read(self, br) -> None:
        pass


class MailName(StorageName):
    def __init__(self):
        super().__init__(StorageKind.Mail)
        self._mail_id = 0

    def read(self, br) -> None:
        self._mail_id = br.read_uint16()

    @property
    def mail_id(self) -> int:
        return self._mail_id


class ShopName(StorageName):
    def __init__(self):
        super().__init__(StorageKind.Shop)

    def read(self, br) -> None:
        pass


class SlotName(StorageName):
    def __init__(self, ship_id: int = 0, slot_id: int = 0):
        super().__init__(StorageKind.ShipSlot)
        self._ship_id = ship_id
        self._slot_id = slot_id

    def read(self, br) -> None:
        self._ship_id = br.read_uint16()
        self._slot_id = br.read_uint16()

    @property
    def ship_id(self) -> int:
        return self._ship_id

    @property
    def slot_id(self) -> int:
        return self._slot_id

    def __str__(self) -> str:
        return f'<slot {self._slot_id} of ship {self._ship_id}>' 


class BlackHole(Storage):
    def __init__(self):
        super().__init__(BlackHoleName())

    def by_id(self, id: int):
        raise RuntimeError("IllegalCallerException")

    def all_items_ids(self) -> set:
        raise RuntimeError("IllegalCallerException")

    def take_item(self, item_id: int):
        raise RuntimeError("IllegalCallerException")

    def add_ship_item(self, ship_item):
        ship_item.server_id = 0
        return ship_item


    def to_wire(self, bw) -> None:
        log.error('black hole serialization: nothing implements it')


class ItemBag(Storage, Zarhato):
    def __init__(self, container_id, items, user_id):
        super().__init__(container_id)
        self.items: dict[int, object] = {}
        tag("userID", str(user_id))
        self._read_write_lock = ReadWriteLock()
        if items is None:
            raise TypeError('an item list is required')
        self.add_ship_items(items)

    @classmethod
    def of_empty(cls, container_id, user_id):
        return cls(container_id, [], user_id)

    def add_ship_item(self, ship_item):
        with self._irva:
            try:
                if isinstance(ship_item, CountableItem):
                    if ship_item.count() == 0:
                        return ship_item

                existing_countable = None
                if (ship_item.item_type == ItemType.Countable and isinstance(ship_item, CountableItem)):
                    existing_countable = self.holds_stack_of(ship_item.card_guid_of())
                if existing_countable is not None:
                    if self.container_id.container_type != StorageKind.Shop:
                        log.debug('item %s placed into %s, stack grows by %s', ship_item.card_guid_of(),
                                 self.container_id.container_type, ship_item.count())
                    log.debug('stack %s already present holding %s', existing_countable.card_guid_of(),
                             existing_countable.count())
                    existing_countable.grow_count(ship_item.count())
                    log.debug('stack %s now holds %s', existing_countable.card_guid_of(),
                             existing_countable.count())
                    return existing_countable
                else:
                    log.debug('item %s placed into %s', ship_item, self.container_id.container_type)
                    server_id = self._get_free_server_id()
                    ship_item.server_id = server_id
                    self.items[server_id] = ship_item
                    return ship_item
            except Exception as ex:
                log.error("In add_ship_item %s", ship_item.card_guid_of())
                return None

    def add_ship_items(self, items) -> None:
        for tetel in items:
            self.add_ship_item(tetel)

    def take_item(self, item_id: int):
        with self._irva:
            return self.items.pop(item_id, None)

    def wipe_ship_items(self) -> None:
        with self._irva:
            self.items.clear()

    def _get_free_server_id(self) -> int:
        for i in range(_MAX_SERVER_ID):
            if i not in self.items:
                return i
        raise RuntimeError('id space exhausted; cannot add')

    def holds_item(self, ship_item) -> bool:
        with self._olvasva:
            return ship_item in self.items.values()

    def holds_stack_of(self, keresett):
        guid = (keresett.card_guid_of() if isinstance(keresett, CountableItem)
                else keresett)
        ship_item = self.by_guid(guid)
        if ship_item is None:
            return None
        if isinstance(ship_item, CountableItem):
            return ship_item
        return None

    def by_guid(self, guid: int):
        with self._olvasva:
            for tetel in self.items.values():
                if tetel.card_guid_of() == guid:
                    return tetel
            return None

    def all_items_ids(self) -> set:
        with self._olvasva:
            return set(self.items.keys())

    @property
    def all_ship_items(self) -> list:
        return list(self.items.values())

    def by_id(self, id: int):
        with self._olvasva:
            return self.items.get(id)

    def to_wire(self, bw) -> None:
        with self._olvasva:
            bw.write_length(len(self.items))
            for ertek in self.items.values():
                bw.write_desc(ertek)


class Locker(ItemBag):
    def __init__(self, user_id, items=()):
        super().__init__(LockerName(), list(items), user_id)


    def to_wire(self, bw) -> None:
        bw.write_msg_type(PilotReply.LockerItems.value)
        super().to_wire(bw)

    def __str__(self) -> str:
        return f'<locker {self.container_id}>' 


class MailStorage(ItemBag):
    def __init__(self, user_id: int, items=()):
        super().__init__(MailName(), list(items), user_id)


class ShipSlot(Storage, Zarhato):
    def __init__(self, ship_slot_container_id, ship_slot_card):
        super().__init__(ship_slot_container_id)
        self.catalogue: Catalogue = Services.get(Catalogue)
        self._ship_system = ShipSystem.by_server_id_(ship_slot_card.slot_id)
        self._read_write_lock = ReadWriteLock()
        current_consumable = CountableItem.stand_in()
        self._current_consumable = ShipConsumable(
            current_consumable,
            self.catalogue.card_or_none(current_consumable.card_guid_of(), CardView.ShipConsumable))
        self._ship_ability = None
        self._ship_slot_card = ship_slot_card

    @property
    def ship_system(self) -> ShipSystem:
        return self._ship_system

    @property
    def current_consumable(self) -> ShipConsumable:
        return self._current_consumable

    def ship_ability(self):
        return self._ship_ability

    def ship_slot_card(self):
        return self._ship_slot_card

    def to_wire(self, bw) -> None:
        with self._olvasva:
            bw.write_desc(self._ship_system)
            bw.write_guid(self._current_consumable.item_countable.card_guid_of())
            bw.write_boolean(self._is_inoperable())

    def _is_inoperable(self) -> bool:
        if self._ship_system is None or self._ship_system.card_guid_of() == 0:
            return False
        if self._ship_system.ship_system_card.ship_slot_type == ShipSlotType.ship_paint:
            return False
        quality = self._ship_system.quality()
        return quality < 0.1

    def __str__(self) -> str:
        return ("<ShipSlot " + f"ship_system={self._ship_system}, current_consumable={self._current_consumable},"
                f" inoperable={self._is_inoperable()}" + ">")

    def by_id(self, id: int):
        return self._ship_system

    def all_items_ids(self) -> set:
        with self._olvasva:
            return {self._ship_system.server_id}

    def take_item(self, item_id: int = 0):
        with self._irva:
            atmeneti = self._ship_system
            self._ship_system = ShipSystem.by_server_id_(atmeneti.server_id)
            self._current_consumable = ShipConsumable(CountableItem.stand_in(), None)
            return atmeneti

    @current_consumable.setter
    def current_consumable(self, mostani_fogyoeszkoz: CountableItem) -> None:
        with self._irva:
            self._current_consumable = ShipConsumable(
                mostani_fogyoeszkoz,
                self.catalogue.card_or_none(mostani_fogyoeszkoz.card_guid_of(), CardView.ShipConsumable))

    def add_ship_item(self, ship_item):
        if not isinstance(ship_item, ShipSystem):
            raise ValueError(f'slots take ship systems only; received {self._ship_system.server_id}')
        new_ship_system = ship_item
        with self._irva:
            server_id = self._ship_system.server_id
            self._ship_system = ShipSystem.from_guid(new_ship_system.card_guid_of())
            ability_cards = self._ship_system.ship_system_card.ship_ability_cards or []
            if len(ability_cards) > 0:
                ship_ability_card = self.catalogue.card_of(ability_cards[0], CardView.ShipAbility)
                if ship_ability_card is None:
                    raise RuntimeError('ability card absent')
                self.equip_ability(ship_ability_card)
            self._ship_system.server_id = server_id
            self._ship_system.durability = new_ship_system.durability
            return new_ship_system

    def equip_ability(self, ship_ability_card) -> None:
        with self._irva:
            self._ship_ability = ShipAbility(ship_ability_card)


class Shop(ItemBag):
    def __init__(self, user_id, items=()):
        super().__init__(ShopName(), list(items), user_id)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)

    def __str__(self) -> str:
        return f'<shop {self.container_id}, stocking {self.items}>' 


class EventShop(ItemBag):
    def __init__(self, user_id: int):
        super().__init__(EventShopName(), [], user_id)

    def __str__(self) -> str:
        return f'<event shop {self.container_id}, stocking {self.items}>' 


class Hold(ItemBag):
    def __init__(self, user_id, items=()):
        super().__init__(HoldName(), list(items), user_id)


    def to_wire(self, bw) -> None:
        bw.write_msg_type(PilotReply.HoldItems.value)
        super().to_wire(bw)

    def __str__(self) -> str:
        return f'<hold {self.container_id}>' 


class Mail(Ownable, Outgoing):

    MailState = MailState
    MailStorage = MailStorage

    def __init__(self, server_id: int, mail_form_guid: int, mail_status: MailState,
                 received, items, parameters, user_id: int):
        self._server_id = server_id
        self._mail_template_card_guid = mail_form_guid
        self._mail_status = mail_status
        self._received = Stamp(received)
        self._mail_container = MailStorage(user_id, items)
        self._parameters = parameters

    @property
    def mail_container(self) -> MailStorage:
        return self._mail_container

    @property
    def mail_status(self) -> MailState:
        return self._mail_status

    @mail_status.setter
    def mail_status(self, mail_status: MailState) -> None:
        self._mail_status = mail_status

    @property
    def mail_template_card_guid(self) -> int:
        return self._mail_template_card_guid

    @property
    def parameters(self):
        return self._parameters

    @property
    def received(self):
        return self._received.local_date

    @property
    def server_id(self) -> int:
        return self._server_id

    @server_id.setter
    def server_id(self, free_server_id: int) -> None:
        self._server_id = free_server_id

    @classmethod
    def of_new(cls, mail_form_guid: int, targyak, user_id: int) -> "Mail":
        return cls(0, mail_form_guid, MailState.Unread,
                   datetime.datetime.now(datetime.timezone.utc), targyak, [], user_id)

    def to_wire(self, bw) -> None:
        bw.write_uint16(self._server_id)
        bw.write_guid(self._mail_template_card_guid)
        bw.write_byte(self._mail_status.value)
        bw.write_date_time(self._received.local_date)
        bw.write_desc_collection(self._mail_container.all_ship_items)
        bw.write_string_array(self._parameters)


class StorageKind(Enum):
    Hold = 1
    Locker = 2
    ShipSlot = 3
    Shop = 4
    Loot = 5
    BlackHole = 6
    Mail = 7
    EventShop = 8

    @classmethod
    def from_code(cls, value: int) -> "StorageKind | None":
        return _BY_VALUE.get(value)

_SAJAT_MEZOK = None


def _sajat_tarolok() -> dict:
    global _SAJAT_MEZOK
    if _SAJAT_MEZOK is None:
        _SAJAT_MEZOK = {
            StorageKind.Hold: "hold",
            StorageKind.Locker: "locker",
            StorageKind.Shop: "shop",
            StorageKind.EventShop: "event_shop",
            StorageKind.BlackHole: "black_hole",
        }
    return _SAJAT_MEZOK


_BY_VALUE = {member.value: member for member in StorageKind}
_MAX_SERVER_ID = 32767 * 2
