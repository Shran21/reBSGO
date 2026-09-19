# github.com/Shran21

from __future__ import annotations

from rebsgo.pilots.state.holdings.storages import StorageKind
from rebsgo.pilots.state.holdings.walks.event_shop_walk import EventShopWalk
from rebsgo.pilots.state.holdings.walks.hold_walk import HoldWalk
from rebsgo.pilots.state.holdings.walks.locker_walk import LockerWalk
from rebsgo.pilots.state.holdings.walks.shop_walk import ShopWalk
from rebsgo.pilots.state.holdings.walks.slot_walk import SlotWalk
from rebsgo.pilots.state.holdings.walks.storage_walk import StorageWalk


_UTVONALAK = {
    StorageKind.Hold: (HoldWalk, True),
    StorageKind.Locker: (LockerWalk, True),
    StorageKind.Shop: (ShopWalk, True),
    StorageKind.EventShop: (EventShopWalk, True),
    StorageKind.ShipSlot: (SlotWalk, False),
    StorageKind.Mail: (StorageWalk, False),
}


def walker_for(container_type, user, transfer_request, dice):
    utvonal = _UTVONALAK.get(container_type)
    if utvonal is None:
        raise ValueError(f'no walk leads out of {container_type}')
    walk, kell_kocka = utvonal
    if kell_kocka:
        return walk(user, transfer_request, dice)
    return walk(user, transfer_request)
