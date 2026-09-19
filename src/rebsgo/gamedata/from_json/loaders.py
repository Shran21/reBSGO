# github.com/Shran21

from __future__ import annotations

from rebsgo.gamedata.assignments import AssignmentSpec
from rebsgo.gamedata.from_json.game_data_loader import GameDataLoader
from rebsgo import paths
from rebsgo.gamedata.decoding.loot_spec_parser import loot_spec_from_json
from rebsgo.gamedata import lenient_json
from rebsgo.gamedata.areas import AreaSpec
from rebsgo.gamedata.collider_specs import AlignedBoxPlan, CapsulePlan, ShapeKind, MeshPlan, SpherePlan
from rebsgo.gamedata.ship_setups import ShipSetupSpec, take_all
from types import MappingProxyType
from rebsgo.gamedata.upgrades import AugmentExperienceSpec, AugmentBoostSpec, AugmentLootSpec, AugmentTeleportSpec


class AssignmentLoader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Mission")

    def mission_templates(self) -> dict:
        mission_templates: dict[int, object] = {}
        for utvonal in self.file_paths():
            parsed = self.read_json(utvonal)
            if parsed is None:
                continue
            for element in parsed:
                mission_template = AssignmentSpec.from_json(element)
                elozo = mission_templates.get(mission_template.id())
                mission_templates[mission_template.id()] = mission_template
                if elozo is not None:
                    raise RuntimeError(
                        f'AssignmentSpec reader: mission card {elozo.id()} appears twice')
        return mission_templates


class DropLoader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Loot")

    def loot_templates(self) -> dict:
        loot_templates: dict[int, object] = {}
        for utvonal in self.file_paths():
            parsed = self.read_json(utvonal)
            if parsed is None:
                continue
            for element in parsed:
                loot_template = loot_spec_from_json(element)
                elozo = loot_templates.get(loot_template.id)
                loot_templates[loot_template.id] = loot_template
                if elozo is not None:
                    raise RuntimeError("Double Entry in LootSpecs!!!")
        return loot_templates


class AreaLoader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Zone")

    def zone_template(self) -> list:
        templates: list = []
        for utvonal in self.file_paths():
            all_text = self.raw_text(utvonal)
            if all_text is None:
                continue
            sablon = AreaSpec.from_json(lenient_json.loads(all_text))
            templates.append(sablon)
        return templates


class ColliderLoader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Collider")

    def collider_plans(self) -> list:
        eredmeny = []
        for utvonal in self.file_paths():
            parsed = self.read_json(utvonal)
            if parsed is None:
                continue
            eredmeny.append(self._deserialize(parsed))
        return eredmeny

    TERVEK = {
        ShapeKind.AABB: AlignedBoxPlan,
        ShapeKind.Mesh: MeshPlan,
        ShapeKind.Sphere: SpherePlan,
        ShapeKind.Capsule: CapsulePlan,
    }

    @classmethod
    def _deserialize(cls, obj: dict):
        terv = cls.TERVEK.get(ShapeKind[obj["type"]])
        return None if terv is None else terv.from_json(obj)


class ShipSetupLoader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "ShipConfig")

    def load_now(self) -> None:
        ship_config_templates = []
        for utvonal in self.file_paths():
            parsed = self.read_json(utvonal)
            if parsed is None:
                continue
            for element in parsed:
                ship_config_templates.append(ShipSetupSpec.from_json(element))
        take_all(ship_config_templates)


class UpgradeLoader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Augment")

    def all_augment_templates(self) -> dict:
        augment_template_map: dict[int, object] = {}
        merged = []
        for utvonal in self.file_paths():
            parsed = self.read_json(utvonal)
            if parsed is None:
                continue
            merged.extend(parsed)
        for element in merged:
            sablon = self._deserialize(element)
            augment_template_map[sablon.associated_item_guid] = sablon
        return MappingProxyType(augment_template_map)

    @staticmethod
    def _deserialize(obj: dict):
        nyers = obj["augmentActionType"]
        if nyers == "GrantExperience":
            return AugmentExperienceSpec.from_json(obj)
        if nyers == "LootItem":
            return AugmentLootSpec.from_json(obj)
        if nyers == "Teleport":
            return AugmentTeleportSpec.from_json(obj)
        if nyers == "None":
            return AugmentBoostSpec.from_json(obj)
        raise RuntimeError('nothing implements this')
