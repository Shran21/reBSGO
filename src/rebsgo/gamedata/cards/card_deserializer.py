# github.com/Shran21
from __future__ import annotations

from rebsgo.gamedata.cards.ui_cards import AvatarCatalogueCard, BannerCard, GuiCard, MailTemplateCard, StickerListCard, TitleCard
from rebsgo.gamedata.cards.world_cards import CameraCard, GalaxyMapCard, RoomCard, SectorCard, WorldCard, ZoneCard
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.cards.misc_cards import CounterCard, DutyCard, GlobalCard, MissileCard, MissionCard, ModuleCard, MovementCard, ObjectStatsCard, OwnerCard, RegulationCard, RewardCard, SkillCard, TournamentCard
from rebsgo.gamedata.cards.shop_cards import EventShopCard, GlobalBonusEventCard, SectorEventCard, ShopItemCard, SpecialOfferCard, StarterCard, StarterKitCard
from rebsgo.gamedata.cards.ship_cards import ShipAbilityCard, ShipCard, ShipCardBrief, ShipConsumableCard, ShipListCard, ShipSaleCard, ShipSystemCard, ShipSystemPaintCard

_VIEW_TO_CLASS = {
    CardView.GUI: GuiCard,
    CardView.ShipSystem: ShipSystemCard,
    CardView.ShipConsumable: ShipConsumableCard,
    CardView.World: WorldCard,
    CardView.Global: GlobalCard,
    CardView.ShipAbility: ShipAbilityCard,
    CardView.Counter: CounterCard,
    CardView.Skill: SkillCard,
    CardView.Ship: ShipCard,
    CardView.Sector: SectorCard,
    CardView.Starter: StarterCard,
    CardView.Room: RoomCard,
    CardView.Assignment: MissionCard,
    CardView.Reward: RewardCard,
    CardView.Title: TitleCard,
    CardView.Duty: DutyCard,
    CardView.AvatarCatalogue: AvatarCatalogueCard,
    CardView.Module: ModuleCard,
    CardView.Price: ShopItemCard,
    CardView.Missile: MissileCard,
    CardView.ShipList: ShipListCard,
    CardView.StickerList: StickerListCard,
    CardView.Movement: MovementCard,
    CardView.Owner: OwnerCard,
    CardView.GalaxyMap: GalaxyMapCard,
    CardView.Camera: CameraCard,
    CardView.MailTemplate: MailTemplateCard,
    CardView.StarterPack: StarterKitCard,
    CardView.ShipPaint: ShipSystemPaintCard,
    CardView.Regulation: RegulationCard,
    CardView.ShipSale: ShipSaleCard,
    CardView.SectorEvent: SectorEventCard,
    CardView.Tournament: TournamentCard,
    CardView.ShipLight: ShipCardBrief,
    CardView.EventShop: EventShopCard,
    CardView.GlobalBonusEvent: GlobalBonusEventCard,
    CardView.Banner: BannerCard,
    CardView.ConversionCampaign: SpecialOfferCard,
    CardView.Zone: ZoneCard,
    CardView.NonShipStats: ObjectStatsCard,
}


def deserialize_card(obj: dict):
    card_view = CardView.from_code(int(obj["cardView"]))
    cls = _VIEW_TO_CLASS.get(card_view)
    if cls is None:
        return None
    return cls.from_json(obj)
