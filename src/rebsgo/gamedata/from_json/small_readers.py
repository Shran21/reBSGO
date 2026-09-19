# github.com/Shran21

from __future__ import annotations

import logging
from rebsgo.gamedata.from_json.game_data_loader import GameDataLoader
from rebsgo import paths


log = logging.getLogger(__name__)

_DEFAULT_STEALTH_DETECTION_VISUAL_RADIUS = 250.0


class StealthConfig:
    def __init__(self, stealth_detection_visual_radius: float):
        self._stealth_detection_visual_radius = stealth_detection_visual_radius

    @property
    def stealth_detection_visual_radius(self) -> float:
        return self._stealth_detection_visual_radius

    @staticmethod
    def default() -> "StealthConfig":
        return StealthConfig(_DEFAULT_STEALTH_DETECTION_VISUAL_RADIUS)


class StealthConfigReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Stealth")

    def fetch(self) -> StealthConfig:
        for utvonal in self.file_paths():
            if utvonal.name != "stealth_config.json":
                continue
            try:
                obj = self.read_json(utvonal)
                if obj is None:
                    continue
                return StealthConfig(float(obj.get(
                    "stealthDetectionVisualRadius",
                    _DEFAULT_STEALTH_DETECTION_VISUAL_RADIUS)))
            except Exception:
                log.exception("Could not parse stealth config file %s; using defaults", utvonal)
                return StealthConfig.default()
        log.warning("No stealth_config.json found; using default stealth detection visual radius")
        return StealthConfig.default()

log = logging.getLogger(__name__)


class ModuleDecoyConfig:
    def __init__(self, enabled: bool, decoy_module_guid: int, registered_prefabs: set[str]):
        self._enabled = enabled
        self._decoy_module_guid = decoy_module_guid
        self._registered_prefabs = {p.lower() for p in registered_prefabs}

    @property
    def decoy_module_guid(self) -> int:
        return self._decoy_module_guid

    def should_apply(self, prefab_name: str | None) -> bool:
        if not self._enabled or self._decoy_module_guid == 0 or not prefab_name:
            return False
        return prefab_name.lower() not in self._registered_prefabs

    @staticmethod
    def disabled() -> "ModuleDecoyConfig":
        return ModuleDecoyConfig(False, 0, set())


class ModuleDecoyReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Modules")

    def fetch(self) -> ModuleDecoyConfig:
        for utvonal in self.file_paths():
            if utvonal.name != "module_decoy.json":
                continue
            try:
                obj = self.read_json(utvonal)
                if obj is None:
                    continue
                config = ModuleDecoyConfig(
                    bool(obj.get("enabled", True)),
                    int(obj.get("decoyModuleGuid", 0)),
                    set(obj.get("registeredPrefabs", [])))
                log.info("Loaded module decoy config: guid=%s, %d registered prefabs excluded",
                         obj.get("decoyModuleGuid"), len(obj.get("registeredPrefabs", [])))
                return config
            except Exception:
                log.exception("Could not parse module decoy config %s; decoy disabled", utvonal)
                return ModuleDecoyConfig.disabled()
        log.info("No module_decoy.json found; turret visibility decoy is disabled")
        return ModuleDecoyConfig.disabled()

_module_decoy_config: ModuleDecoyConfig | None = None


def get_module_decoy_config() -> ModuleDecoyConfig:
    global _module_decoy_config
    if _module_decoy_config is None:
        _module_decoy_config = ModuleDecoyReader().fetch()
    return _module_decoy_config

log = logging.getLogger(__name__)


class DefaultModelPaintFallbacks:
    def __init__(self, by_ship_object_key: dict[int, int]):
        self._by_ship_object_key = dict(by_ship_object_key)

    def paint_card_guid(self, ship_object_key: int) -> int | None:
        return self._by_ship_object_key.get(ship_object_key)

    @staticmethod
    def empty() -> "DefaultModelPaintFallbacks":
        return DefaultModelPaintFallbacks({})


class DefaultModelPaintFallbackReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Paint")

    def fetch(self) -> DefaultModelPaintFallbacks:
        for utvonal in self.file_paths():
            if utvonal.name != "default_model_paints.json":
                continue
            parsed = self.read_json(utvonal)
            if parsed is None:
                continue
            by_ship_object_key = {}
            for element in parsed:
                if not bool(element.get("enabled", True)):
                    continue
                ship_object_key = int(element["shipObjectKey"])
                paint_card_guid = int(element["paintCardGuid"])
                by_ship_object_key[ship_object_key] = paint_card_guid
            log.info("Loaded %d default-model paint fallback entries", len(by_ship_object_key))
            return DefaultModelPaintFallbacks(by_ship_object_key)
        log.info("No default_model_paints.json found; default-model paint fallback is disabled")
        return DefaultModelPaintFallbacks.empty()

log = logging.getLogger(__name__)


class ShipLoadoutConfig:
    def __init__(self, loadouts: dict[int, list[tuple[int, int]]]):
        self._loadouts = loadouts

    def loadout_for(self, ship_guid: int) -> list[tuple[int, int]]:
        return self._loadouts.get(ship_guid, [])

    @property
    def empty(self) -> bool:
        return not self._loadouts


class ShipLoadoutTemplateReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "ShipLoadouts")

    def fetch(self) -> ShipLoadoutConfig:
        loadouts: dict[int, list[tuple[int, int]]] = {}
        for utvonal in self.file_paths():
            if utvonal.suffix.lower() != ".json":
                continue
            try:
                obj = self.read_json(utvonal)
            except Exception:
                log.exception("Could not parse ship loadout file %s", utvonal)
                continue
            if obj is None:
                continue
            for bejegyzes in obj.get("loadouts", []):
                ship_guid = int(bejegyzes["shipGuid"])
                slots = [(int(s["slotId"]), int(s["systemGuid"])) for s in bejegyzes.get("slots", [])]
                loadouts[ship_guid] = slots
        if loadouts:
            log.info("Loaded %s default ship loadout(s): %s", len(loadouts), sorted(loadouts.keys()))
        return ShipLoadoutConfig(loadouts)
