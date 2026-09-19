# github.com/Shran21
from __future__ import annotations

import logging

from rebsgo.vocabulary.pilot import OldShipRole
from rebsgo.gamedata.from_json.game_data_loader import GameDataLoader
from rebsgo.gamedata.reading import ShipRole
from rebsgo import paths

log = logging.getLogger(__name__)

_DEFAULT_CARRIER_SHIP_GUIDS = frozenset((
    10002032,
    10002127,
    10000617,
    10000618,
))
_DEFAULT_DOCK_RANGE = 1000.0
_DEFAULT_ALLOWED_DOCK_SHIP_ROLES = frozenset((ShipRole.Fighter,))
_DEFAULT_ALLOWED_DOCK_SHIP_DEPRECATED_ROLES = frozenset((OldShipRole.Fighter,))
_DEFAULT_ALLOWED_DOCK_SHIP_TIERS = frozenset((1,))


class CarrierModeConfig:
    def __init__(self, carrier_ship_guids, dock_range: float, party_only: bool,
                 require_fortified_for_anchor: bool, repair_enabled: bool,
                 allowed_dock_ship_roles=None, allowed_dock_ship_deprecated_roles=None,
                 allowed_dock_ship_tiers=None, transponder_party_only: bool = False):
        self._carrier_ship_guids = frozenset(int(guid) for guid in carrier_ship_guids)
        self._dock_range = float(dock_range)
        self._party_only = bool(party_only)
        self._transponder_party_only = bool(transponder_party_only)
        self._require_fortified_for_anchor = bool(require_fortified_for_anchor)
        self._repair_enabled = bool(repair_enabled)
        self._allowed_dock_ship_roles = frozenset(
            _DEFAULT_ALLOWED_DOCK_SHIP_ROLES if allowed_dock_ship_roles is None else allowed_dock_ship_roles)
        self._allowed_dock_ship_deprecated_roles = frozenset(
            _DEFAULT_ALLOWED_DOCK_SHIP_DEPRECATED_ROLES
            if allowed_dock_ship_deprecated_roles is None else allowed_dock_ship_deprecated_roles)
        self._allowed_dock_ship_tiers = frozenset(
            _DEFAULT_ALLOWED_DOCK_SHIP_TIERS if allowed_dock_ship_tiers is None
            else (int(tier) for tier in allowed_dock_ship_tiers))

    @property
    def carrier_ship_guids(self):
        return self._carrier_ship_guids

    @property
    def dock_range(self) -> float:
        return self._dock_range

    @property
    def party_only(self) -> bool:
        return self._party_only

    def transponder_party_only(self) -> bool:
        return self._transponder_party_only

    @property
    def require_fortified_for_anchor(self) -> bool:
        return self._require_fortified_for_anchor

    @property
    def repair_enabled(self) -> bool:
        return self._repair_enabled

    @property
    def allowed_dock_ship_roles(self):
        return self._allowed_dock_ship_roles

    @property
    def allowed_dock_ship_deprecated_roles(self):
        return self._allowed_dock_ship_deprecated_roles

    @property
    def allowed_dock_ship_tiers(self):
        return self._allowed_dock_ship_tiers

    @staticmethod
    def default() -> "CarrierModeConfig":
        return CarrierModeConfig(_DEFAULT_CARRIER_SHIP_GUIDS, _DEFAULT_DOCK_RANGE, True, True, True)


def _read_enum_set(raw_values, enum_cls, field_name: str):
    parsed = set()
    if raw_values is None:
        return None
    if not isinstance(raw_values, list):
        log.warning("Carrier base mode field %s should be a list; using empty set", field_name)
        return parsed
    for raw_value in raw_values:
        try:
            if isinstance(raw_value, enum_cls):
                parsed.add(raw_value)
            elif isinstance(raw_value, str):
                parsed.add(enum_cls[raw_value])
            else:
                parsed.add(enum_cls(raw_value))
        except Exception:
            log.warning("Ignoring unknown carrier base mode %s value: %s", field_name, raw_value)
    return parsed


class CarrierModeTemplateReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Carrier")

    def fetch(self) -> CarrierModeConfig:
        for utvonal in self.file_paths():
            if utvonal.name != "base_mode.json":
                continue
            try:
                obj = self.read_json(utvonal)
                if obj is None:
                    continue
                return CarrierModeConfig(
                    obj.get("carrierShipGuids", _DEFAULT_CARRIER_SHIP_GUIDS),
                    obj.get("dockRange", _DEFAULT_DOCK_RANGE),
                    obj.get("partyOnly", True),
                    obj.get("requireFortifiedForAnchor", True),
                    obj.get("repairEnabled", True),
                    _read_enum_set(obj.get("allowedDockShipRoles"), ShipRole, "allowedDockShipRoles"),
                    _read_enum_set(
                        obj.get("allowedDockShipDeprecatedRoles"),
                        OldShipRole,
                        "allowedDockShipDeprecatedRoles"),
                    obj.get("allowedDockShipTiers"),
                    obj.get("transponderPartyOnly", False),
                )
            except Exception:
                log.exception("Could not parse carrier base mode config file %s; using defaults", utvonal)
                return CarrierModeConfig.default()
        log.warning("No Carrier/base_mode.json found; using default carrier base mode config")
        return CarrierModeConfig.default()
