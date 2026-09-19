# github.com/Shran21
from __future__ import annotations

from enum import Enum


class CardView(Enum):
    GUI = 1
    ShipSystem = 2
    ShipConsumable = 3
    World = 4
    Global = 5
    ShipAbility = 6
    Counter = 7
    Skill = 8
    Ship = 10
    Sector = 11
    Starter = 13
    Room = 14
    Assignment = 0x10
    Reward = 18
    Title = 19
    Duty = 20
    AvatarCatalogue = 21
    Module = 22
    Price = 23
    Missile = 24
    ShipList = 25
    StickerList = 26
    Movement = 28
    Owner = 29
    GalaxyMap = 30
    Camera = 0x1F
    MailTemplate = 0x20
    StarterPack = 34
    ShipPaint = 35
    Regulation = 36
    ShipSale = 37
    SectorEvent = 38
    Tournament = 39
    MapPart = 40
    MapPartSet = 41
    ShipLight = 42
    EventShop = 43
    GlobalBonusEvent = 44
    Banner = 45
    ConversionCampaign = 46
    Zone = 47
    NonShipStats = 48

    @classmethod
    def from_code(cls, uzenet_kod: int) -> "CardView | None":
        return _BY_VALUE.get(uzenet_kod)

_BY_VALUE = {c.value: c for c in CardView}
