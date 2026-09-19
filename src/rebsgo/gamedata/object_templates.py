# github.com/Shran21

from __future__ import annotations

from abc import ABC
from rebsgo.geometry.primitives.transform import Transform
from rebsgo.gamedata import json_helper as jh
from rebsgo.vocabulary.pilot import Faction
from rebsgo.vocabulary.world import ArrivalCause, ObjectKind


class WorldObjectSpec(ABC):
    def __init__(self, object_guid: int, space_entity_type, creating_cause, respawn_time: int,
                 spawns_at_once: bool, zsakmany_ids):
        self.object_guid = object_guid
        self.space_entity_type = space_entity_type
        self.creating_cause = creating_cause
        self.respawn_time = respawn_time
        self.is_instant_in_sector_ = spawns_at_once
        self.loot_template_ids = zsakmany_ids

    @staticmethod
    def _fill_base(obj: dict, target: "WorldObjectSpec") -> None:
        target.object_guid = jh.as_long(obj, "objectGUID")
        target.space_entity_type = jh.as_enum_by_name(obj, "spaceEntityType", ObjectKind)
        target.creating_cause = jh.as_enum_by_name(obj, "creatingCause", ArrivalCause)
        target.respawn_time = jh.as_int(obj, "respawnTime")
        target.is_instant_in_sector_ = jh.as_flag(obj, "isInstantInSector")
        target.loot_template_ids = jh.as_long_list(obj, "lootTemplateIds")

    def respawn_after(self, poras_mp: int) -> None:
        self.respawn_time = poras_mp

    @property
    def spawns_at_once(self) -> bool:
        return self.is_instant_in_sector_


class AsteroidSpec(WorldObjectSpec):
    def __init__(self, object_guid, space_entity_type, creating_cause, respawn_time, spawns_at_once,
                 position, rotation, radius, rotation_speed, zsakmany_ids=None):
        super().__init__(object_guid, space_entity_type, creating_cause, respawn_time, spawns_at_once,
                         [] if zsakmany_ids is None else zsakmany_ids)
        self.position = position
        self.rotation = rotation
        self.radius = radius
        self.rotation_speed = rotation_speed

    @classmethod
    def from_json(cls, obj: dict) -> "AsteroidSpec":
        t = cls.__new__(cls)
        WorldObjectSpec._fill_base(obj, t)
        t.position = jh.get_vector3(obj, "position")
        t.rotation = jh.euler3(obj, "rotation")
        t.radius = jh.as_float(obj, "radius")
        t.rotation_speed = jh.as_float(obj, "rotationSpeed")
        return t

    def transform_of(self) -> Transform:
        return Transform(self.position, self.rotation, True)

    def position_of(self):
        return self.position

    def rotation_of(self):
        return self.rotation

    def radius_of(self) -> float:
        return self.radius


class BotSpec(WorldObjectSpec):
    def __init__(self, object_guid, space_entity_type, creating_cause, respawn_time, spawns_at_once,
                 zsakmany_ids, kiugras_utani_mp, jumps_out_when_fighting_spec, lifespan_seconds, spawn_box,
                 owner_guid=None, gear_level=1):
        super().__init__(object_guid, space_entity_type, creating_cause, respawn_time, spawns_at_once, zsakmany_ids)
        self.respawn_time_jump_out = kiugras_utani_mp
        self.jumps_out_when_fighting_spec = jumps_out_when_fighting_spec
        self.lifespan_seconds = lifespan_seconds
        self.spawn_box = spawn_box
        self.owner_guid = owner_guid
        self.gear_level = gear_level

    @classmethod
    def from_json(cls, obj: dict) -> "BotSpec":
        t = cls.__new__(cls)
        WorldObjectSpec._fill_base(obj, t)
        t.respawn_time_jump_out = jh.as_long(obj, "respawnTimeJumpOut")
        t.jumps_out_when_fighting_spec = jh.as_flag(obj, "jumpOutIfInCombat")
        t.lifespan_seconds = jh.as_long(obj, "lifeTimeSeconds")
        t.spawn_box = jh.aabb_from(obj.get("spawnBox"))
        t.owner_guid = jh.as_long(obj, "ownerGuid") or None
        t.gear_level = jh.as_int(obj, "gearLevel") or 1
        return t

    @property
    def jumps_out_when_fighting(self) -> bool:
        return self.jumps_out_when_fighting_spec


class DebrisSpec(WorldObjectSpec):
    def __init__(self, object_guid, creating_cause, respawn_time, spawns_at_once, zsakmany_ids,
                 position, rotation, scale, rotation_speed):
        super().__init__(object_guid, ObjectKind.Debris, creating_cause, respawn_time, spawns_at_once, zsakmany_ids)
        self.position = position
        self.rotation = rotation
        self.scale = scale
        self.rotation_speed = rotation_speed

    @classmethod
    def from_json(cls, obj: dict) -> "DebrisSpec":
        t = cls.__new__(cls)
        WorldObjectSpec._fill_base(obj, t)
        t.position = jh.get_vector3(obj, "position")
        t.rotation = jh.euler3(obj, "rotation")
        t.scale = jh.as_float(obj, "scale")
        t.rotation_speed = jh.as_float(obj, "rotationSpeed")
        return t

    def transform_of(self) -> Transform:
        return Transform(self.position, self.rotation, True)

    def position_of(self):
        return self.position

    def rotation_of(self):
        return self.rotation


class PlanetSpec(WorldObjectSpec):
    def __init__(self, object_guid, creating_cause, respawn_time, spawns_at_once, position, rotation,
                 scale, color, specular_color, shininess, faction=Faction.Neutral):
        super().__init__(object_guid, ObjectKind.Planet, creating_cause, respawn_time, spawns_at_once, [])
        self.position = position
        self.rotation = rotation
        self.scale = scale
        self.color = color
        self.specular_color = specular_color
        self.shininess = shininess
        self.faction = faction

    @classmethod
    def from_json(cls, obj: dict) -> "PlanetSpec":
        t = cls.__new__(cls)
        WorldObjectSpec._fill_base(obj, t)
        t.position = jh.get_vector3(obj, "position")
        t.rotation = jh.euler3(obj, "rotation")
        t.scale = jh.as_float(obj, "scale")
        t.color = jh.get_color(obj, "color")
        t.specular_color = jh.get_color(obj, "specularColor")
        t.shininess = jh.as_float(obj, "shininess")
        t.faction = jh.as_enum_by_name(obj, "faction", Faction, Faction.Neutral)
        return t

    def transform_of(self) -> Transform:
        return Transform(self.position, self.rotation, True)

    def position_of(self):
        return self.position

    def rotation_of(self):
        return self.rotation


class StaticNpcSpec(WorldObjectSpec):
    def __init__(self, object_guid, space_entity_type, creating_cause, respawn_time, spawns_at_once,
                 position, rotation, onhatotav, aggro_reach, faction, zsakmany_ids):
        super().__init__(object_guid, space_entity_type, creating_cause, respawn_time, spawns_at_once, zsakmany_ids)
        self.position = position
        self.rotation = rotation
        self.auto_aggro_distance = onhatotav
        self.aggro_reach = aggro_reach
        self._faction = faction

    @staticmethod
    def _fill_static(obj: dict, target: "StaticNpcSpec") -> None:
        WorldObjectSpec._fill_base(obj, target)
        target.position = jh.get_vector3(obj, "position")
        target.rotation = jh.euler3(obj, "rotation")
        target.auto_aggro_distance = jh.as_float(obj, "autoAggroDistance")
        target.aggro_reach = jh.as_float(obj, "maximumAggroDistance")
        target._faction = jh.as_enum_by_name(obj, "faction", Faction)

    @classmethod
    def from_json(cls, obj: dict) -> "StaticNpcSpec":
        t = cls.__new__(cls)
        StaticNpcSpec._fill_static(obj, t)
        return t

    def transform_of(self) -> Transform:
        return Transform(self.position, self.rotation, True)

    @property
    def faction(self) -> Faction:
        return self._faction


class CruiserSpec(StaticNpcSpec):
    pass


class OutpostSpec(StaticNpcSpec):
    pass


class PlanetoidSpec(AsteroidSpec):
    pass


class WeaponPlatformSpec(StaticNpcSpec):
    pass


def deserialize_space_object(obj: dict):
    entity_type = ObjectKind[obj["spaceEntityType"]] if isinstance(obj.get("spaceEntityType"), str) \
        else ObjectKind.from_value(int(obj.get("spaceEntityType")))
    mapping = {
        ObjectKind.Cruiser: CruiserSpec,
        ObjectKind.Asteroid: AsteroidSpec,
        ObjectKind.Planetoid: PlanetoidSpec,
        ObjectKind.Planet: PlanetSpec,
        ObjectKind.WeaponPlatform: WeaponPlatformSpec,
        ObjectKind.Outpost: OutpostSpec,
        ObjectKind.Debris: DebrisSpec,
    }
    cls = mapping.get(entity_type)
    if cls is None:
        return None
    return cls.from_json(obj)
