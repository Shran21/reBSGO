# github.com/Shran21
from __future__ import annotations

from rebsgo.vocabulary.pilot import OldShipRole
from rebsgo.gamedata.from_json.carrier_mode_template_reader import (
    CarrierModeConfig,
    CarrierModeTemplateReader,
)
from rebsgo.gamedata.reading import AbilityActionKind, ShipRole

_config = None


def get_carrier_mode_config() -> CarrierModeConfig:
    global _config
    if _config is None:
        _config = CarrierModeTemplateReader().fetch()
    return _config


def is_carrier_ship_card(ship_card) -> bool:
    if ship_card is None:
        return False
    config = get_carrier_mode_config()
    if ship_card.card_guid_of() in config.carrier_ship_guids:
        return True
    roles = ship_card.ship_roles or []
    return ShipRole.Carrier in roles or ship_card.ship_role_deprecated == OldShipRole.Carrier


def can_ship_dock_at_carrier(ship_card) -> bool:
    if ship_card is None:
        return False
    config = get_carrier_mode_config()
    kapuk = (config.allowed_dock_ship_tiers,
             config.allowed_dock_ship_roles,
             config.allowed_dock_ship_deprecated_roles)
    if not any(kapuk):
        return True
    engedett_tier, engedett_szerep, engedett_regi = kapuk
    return (ship_card.tier in engedett_tier
            or any(szerep in engedett_szerep for szerep in (ship_card.ship_roles or []))
            or ship_card.ship_role_deprecated in engedett_regi)


def is_carrier_space_object(space_object) -> bool:
    if space_object is None or not hasattr(space_object, "ship_card_of"):
        return False
    return is_carrier_ship_card(space_object.ship_card_of())


def is_fortify_ability(ability) -> bool:
    if ability is None or ability.ship_ability_card is None:
        return False
    return ability.ship_ability_card.ability_action_type == AbilityActionKind.Fortify
