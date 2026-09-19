# github.com/Shran21

from __future__ import annotations

from dataclasses import dataclass

from rebsgo.gamedata import json_helper as jh
from rebsgo.gamedata.object_templates import deserialize_space_object
from rebsgo.vocabulary.pilot import Faction, ResourceKind
import os


class CargoSectorDesc:
    def __init__(self, switched_on: bool, keses_mp: int, debris_count: int, debris_guids,
                 cargo_guid: int, cargo_max_count: int, cargo_spawn_chance: float,
                 spawn_radius: float, spawn_height: float):
        self._activated = switched_on
        self._delay_seconds = keses_mp
        self._debris_count = debris_count
        self._debris_guids = list(debris_guids) if debris_guids is not None else []
        self._cargo_guid = cargo_guid
        self._cargo_max_count = cargo_max_count
        self._cargo_spawn_chance = cargo_spawn_chance
        self._spawn_radius = spawn_radius
        self._spawn_height = spawn_height

    @classmethod
    def from_json(cls, obj: dict) -> "CargoSectorDesc":
        return cls(
            jh.as_flag(obj, "activated"),
            jh.as_int(obj, "delaySeconds", 30),
            jh.as_int(obj, "debrisCount"),
            jh.as_long_list(obj, "debrisGuids") or [],
            jh.as_long(obj, "cargoGuid"),
            jh.as_int(obj, "cargoMaxCount"),
            jh.as_float(obj, "cargoSpawnChance"),
            jh.as_float(obj, "spawnRadius", 7000.0),
            jh.as_float(obj, "spawnHeight", 300.0),
        )

    @property
    def activated(self) -> bool:
        return self._activated

    @property
    def delay_seconds(self) -> int:
        return self._delay_seconds

    @property
    def debris_count(self) -> int:
        return self._debris_count

    @property
    def debris_guids(self):
        return self._debris_guids

    @property
    def cargo_guid(self) -> int:
        return self._cargo_guid

    @property
    def cargo_max_count(self) -> int:
        return self._cargo_max_count

    @property
    def cargo_spawn_chance(self) -> float:
        return self._cargo_spawn_chance

    @property
    def spawn_radius(self) -> float:
        return self._spawn_radius

    @property
    def spawn_height(self) -> float:
        return self._spawn_height


@dataclass(slots=True, eq=False)
class CometInfo:
    delay_seconds: int
    activated: bool
    comet_counter: int
    comet_guid: int = 800000601
    height_band: tuple = (3000, 7000)

    @classmethod
    def from_json(cls, obj: dict) -> "CometInfo":
        sav = obj.get("cometHeight") or [3000, 7000]
        return cls(jh.as_long(obj, "delaySeconds"), jh.as_flag(obj, "activated"),
                   jh.as_int(obj, "cometCounter"),
                   jh.as_long(obj, "cometGuid") or 800000601,
                   (int(sav[0]), int(sav[1])))


class DebrisFieldDesc:
    def __init__(self, switched_on, keses_mp, field_count, field_radius, cluster_radius,
                 cluster_height, piles_per_cluster, wrecks_per_cluster, fragments_per_cluster,
                 walls_per_cluster, containers_per_cluster, container_spawn_chance,
                 pile_guids=None, wreck_guids=None, fragment_guids=None, wall_guids=None,
                 cargo_guid=None):
        self._activated = switched_on
        self._delay_seconds = keses_mp
        self._field_count = max(1, field_count)
        self._field_radius = field_radius
        self._cluster_radius = cluster_radius
        self._cluster_height = cluster_height
        self._piles_per_cluster = piles_per_cluster
        self._wrecks_per_cluster = wrecks_per_cluster
        self._fragments_per_cluster = fragments_per_cluster
        self._walls_per_cluster = walls_per_cluster
        self._containers_per_cluster = containers_per_cluster
        self._container_spawn_chance = container_spawn_chance
        from rebsgo.gamedata.from_json.template_readers import debris_card_pools
        keszletek = debris_card_pools()
        self._pile_guids = list(pile_guids) if pile_guids else list(keszletek.piles)
        self._wreck_guids = list(wreck_guids) if wreck_guids else list(keszletek.wrecks)
        self._fragment_guids = list(fragment_guids) if fragment_guids else list(keszletek.fragments)
        self._wall_guids = list(wall_guids) if wall_guids else list(keszletek.walls)
        self._cargo_guid = cargo_guid if cargo_guid else keszletek.cargo

    @classmethod
    def from_json(cls, obj: dict) -> "DebrisFieldDesc":
        return cls(
            jh.as_flag(obj, "activated"),
            jh.as_int(obj, "delaySeconds", 30),
            jh.as_int(obj, "fieldCount", 1),
            jh.as_float(obj, "fieldRadius", 7000.0),
            jh.as_float(obj, "clusterRadius", 1500.0),
            jh.as_float(obj, "clusterHeight", 300.0),
            jh.as_int(obj, "pilesPerCluster", 0),
            jh.as_int(obj, "wrecksPerCluster", 0),
            jh.as_int(obj, "fragmentsPerCluster", 0),
            jh.as_int(obj, "wallsPerCluster", 0),
            jh.as_int(obj, "containersPerCluster", 0),
            jh.as_float(obj, "containerSpawnChance", 0.3),
            jh.as_long_list(obj, "pileGuids"),
            jh.as_long_list(obj, "wreckGuids"),
            jh.as_long_list(obj, "fragmentGuids"),
            jh.as_long_list(obj, "wallGuids"),
            jh.as_long(obj, "cargoGuid") or None,
        )

    @property
    def activated(self) -> bool: return self._activated
    @property
    def delay_seconds(self) -> int: return self._delay_seconds
    @property
    def field_count(self) -> int: return self._field_count
    @property
    def field_radius(self) -> float: return self._field_radius
    @property
    def cluster_radius(self) -> float: return self._cluster_radius
    @property
    def cluster_height(self) -> float: return self._cluster_height
    @property
    def piles_per_cluster(self) -> int: return self._piles_per_cluster
    @property
    def wrecks_per_cluster(self) -> int: return self._wrecks_per_cluster
    @property
    def fragments_per_cluster(self) -> int: return self._fragments_per_cluster
    @property
    def walls_per_cluster(self) -> int: return self._walls_per_cluster
    @property
    def containers_per_cluster(self) -> int: return self._containers_per_cluster
    @property
    def container_spawn_chance(self) -> float: return self._container_spawn_chance
    @property
    def pile_guids(self): return self._pile_guids
    @property
    def wreck_guids(self): return self._wreck_guids
    @property
    def fragment_guids(self): return self._fragment_guids
    @property
    def wall_guids(self): return self._wall_guids
    @property
    def cargo_guid(self) -> int: return self._cargo_guid


@dataclass(slots=True, eq=False)
class ResourceCeiling:
    min_red_percentage: object
    max_tylium_percentage: object
    max_titanium_percentage: object
    max_water_percentage: object

    @classmethod
    def from_json(cls, obj: dict) -> "ResourceCeiling":
        return cls(jh.as_float(obj, "minRedPercentage"), jh.as_float(obj, "maxTyliumPercentage"),
                   jh.as_float(obj, "maxTitaniumPercentage"), jh.as_float(obj, "maxWaterPercentage"))


class LootByNpc:
    def __init__(self, bot_guid: int, loot_id: int, faction, count: int):
        self._npc_guid = bot_guid
        self._loot_id = loot_id
        self._faction = faction
        self._count = count

    @classmethod
    def from_json(cls, obj: dict) -> "LootByNpc":
        loot_id = obj.get("lootID")
        if loot_id is None:
            loot_id = obj.get("lootId")
        return cls(
            jh.as_long(obj, "npcGUID"),
            0 if loot_id is None else int(loot_id),
            jh.as_enum_by_name(obj, "faction", Faction),
            jh.as_int(obj, "count"),
        )

    @property
    def npc_guid(self) -> int:
        return self._npc_guid

    @property
    def loot_id(self) -> int:
        return self._loot_id

    def faction(self) -> Faction:
        return self._faction

    def count(self) -> int:
        return 1 if self._count == 0 else self._count


class NpcSpawnSpec:
    def __init__(self, guid: int, loot_id: int, count: int, owner_guid=None, gear_level: int = 1):
        self._guid = guid
        self._loot_id = loot_id
        self._count = count
        self._owner_guid = owner_guid
        self._gear_level = gear_level

    @classmethod
    def from_json(cls, obj: dict) -> "NpcSpawnSpec":
        return cls(jh.as_long(obj, "guid"), jh.as_long(obj, "lootId"), jh.as_int(obj, "count"),
                   jh.as_long(obj, "ownerGuid") or None, jh.as_int(obj, "gearLevel") or 1)

    @property
    def guid(self) -> int:
        return self._guid

    @property
    def loot_id(self) -> int:
        return self._loot_id

    def count(self) -> int:
        return self._count

    @property
    def owner_guid(self):
        return self._owner_guid

    @property
    def gear_level(self) -> int:
        return self._gear_level


@dataclass(slots=True, eq=False)
class OutpostProgressSpec:
    pts_drain_per_second: object
    pts_asteroid_killed_with_ressources: object
    pts_npc_killed: object
    pts_player_killed: object
    pts_mining_ship_income: object

    @classmethod
    def from_json(cls, obj: dict) -> "OutpostProgressSpec":
        return cls(jh.as_int(obj, "ptsDrainPerSecond"), jh.as_int(obj, "ptsAsteroidKilledWithRessources"),
                   jh.as_int(obj, "ptsNpcKilled"), jh.as_int(obj, "ptsPlayerKilled"),
                   jh.as_int(obj, "ptsMiningShipIncome"))


class SpawnAreaSpec:
    def __init__(self, id: int, corner_a, corner_b, direction, faction):
        self._id = id
        self._corner_a = corner_a
        self._corner_b = corner_b
        self._direction = direction
        self._faction = faction

    @classmethod
    def from_json(cls, obj: dict) -> "SpawnAreaSpec":
        return cls(
            jh.as_int(obj, "id"),
            jh.get_vector3(obj, "a"),
            jh.get_vector3(obj, "b"),
            jh.euler3(obj, "direction"),
            jh.as_enum_by_name(obj, "faction", Faction),
        )

    def id(self) -> int:
        return self._id

    def corner_a(self):
        return self._corner_a

    def corner_b(self):
        return self._corner_b

    def direction(self):
        return self._direction

    def faction(self) -> Faction:
        return self._faction


@dataclass(slots=True, eq=False)
class ResourceSpec:
    resource_type: object
    chance: int
    hp_to_resource_factor: float
    variation: float

    @classmethod
    def from_json(cls, obj: dict) -> "ResourceSpec":
        return cls(jh.as_enum_by_name(obj, "resourceType", ResourceKind), jh.as_int(obj, "chance"),
                   jh.as_float(obj, "hpToResourceFactor"), jh.as_float(obj, "variation"))


@dataclass(slots=True, eq=False)
class AsteroidInfo:
    respawn_time: int
    respawn_resource_time: int
    hp_interval: object
    max_resource_desc: object
    resource_entries: object

    @classmethod
    def from_json(cls, obj: dict) -> "AsteroidInfo":
        raw_mrd = obj.get("maxResourceDesc")
        raw_re = obj.get("resourceEntries")
        return cls(
            jh.as_int(obj, "respawnTime"),
            jh.as_int(obj, "respawnResourceTime"),
            jh.as_int_list(obj, "hpIntervall"),
            None if raw_mrd is None else ResourceCeiling.from_json(raw_mrd),
            None if raw_re is None else [ResourceSpec.from_json(x) for x in raw_re],
        )


class BotSpawnSpec:
    def __init__(self, keltohely, lifespan_seconds: int, ujraeledes_mp: int, halal_utani_mp: int,
                 faction, bot_keltesek):
        self._spawn_area = keltohely
        self._life_time_seconds = lifespan_seconds
        self._respawn_time_seconds = ujraeledes_mp
        self._respawn_time_death = halal_utani_mp
        self._faction = faction
        self._npc_spawn_entries = bot_keltesek

    @classmethod
    def from_json(cls, obj: dict) -> "BotSpawnSpec":
        nyers = obj.get("npcSpawnEntries")
        npc_spawn_entries = None if nyers is None else [NpcSpawnSpec.from_json(x) for x in nyers]
        return cls(
            jh.aabb_from(obj.get("spawnArea")),
            jh.as_long(obj, "lifeTimeSeconds"),
            jh.as_long(obj, "respawnTimeSeconds"),
            jh.as_long(obj, "respawnTimeDeath"),
            jh.as_enum_by_name(obj, "faction", Faction),
            npc_spawn_entries,
        )

    @property
    def spawn_area(self):
        return self._spawn_area

    @property
    def lifespan_seconds(self) -> int:
        return self._life_time_seconds

    @property
    def respawn_time_seconds(self) -> int:
        return self._respawn_time_seconds

    @property
    def respawn_time_death(self) -> int:
        return self._respawn_time_death

    def faction(self) -> Faction:
        return self._faction

    @property
    def npc_spawn_entries(self):
        return self._npc_spawn_entries


@dataclass(slots=True, eq=False)
class MiningShipSetup:
    extract_per_second: int
    extract_delay: int
    price_in_cubits: int
    npc_guid_loot_ids: object
    seconds_until_npc_spawns: int
    npc_initial_spawn_delay_seconds: int
    npc_life_time_seconds: int

    @classmethod
    def from_json(cls, obj: dict) -> "MiningShipSetup":
        nyers = obj.get("npcGuidLootIds")
        npc_guid_loot_ids = None if nyers is None else [LootByNpc.from_json(x) for x in nyers]
        return cls(
            jh.as_int(obj, "extractPerSecond"),
            jh.as_int(obj, "extractDelay"),
            jh.as_int(obj, "priceInCubits"),
            npc_guid_loot_ids,
            jh.as_int(obj, "secondsUntilNpcSpawns"),
            jh.as_int(obj, "npcInitialSpawnDelaySeconds"),
            jh.as_long(obj, "npcLifeTimeSeconds"),
        )

    @property
    def cubit_price(self) -> int:
        return 100 if self._price_in_cubits == 0 else self._price_in_cubits


@dataclass(slots=True, eq=False)
class PlanetoidInfo:
    respawn_time: int
    respawn_resource_time: int
    resource_entries: object
    min_resources: int
    max_resources: int

    @classmethod
    def from_json(cls, obj: dict) -> "PlanetoidInfo":
        raw_re = obj.get("resourceEntries")
        return cls(
            jh.as_int(obj, "respawnTime"),
            jh.as_int(obj, "respawnResourceTime"),
            None if raw_re is None else [ResourceSpec.from_json(x) for x in raw_re],
            jh.as_int(obj, "minResources"),
            jh.as_int(obj, "maxResources"),
        )


def _filter_bot_spawns(bot_spawns):
    if not bot_spawns or not os.environ.get("REBSGO_NO_GRADIENT"):
        return bot_spawns
    return [b for b in bot_spawns if not (isinstance(b, dict) and b.get("_npcGradient"))]


class SectorInfo:
    def __init__(self, sector_id: int, zone_guid: int, keltohely_sablonok, objektum_sablonok, asteroid_desc,
                 planetoida_leiras, mining_ship_config, bot_kelto_sablonok, colonial_haladas,
                 cylon_haladas, comet_layout, cargo_sector_desc=None,
                 debris_field_desc=None):
        self._sector_id = sector_id
        self.zone_guid = zone_guid
        self.spawn_area_templates = keltohely_sablonok
        self.space_object_templates = objektum_sablonok
        self.asteroid_desc = asteroid_desc
        self.planetoid_desc = planetoida_leiras
        self.mining_ship_config = mining_ship_config
        self.bot_spawn_templates = bot_kelto_sablonok
        self.colonial_progress_template = colonial_haladas
        self.cylon_progress_template = cylon_haladas
        self._comet_sector_desc = comet_layout
        self._cargo_sector_desc = cargo_sector_desc
        self._debris_field_desc = debris_field_desc

    @staticmethod
    def _opt_list(raw, factory):
        return None if raw is None else [factory(x) for x in raw]

    @staticmethod
    def _opt(raw, factory):
        return None if raw is None else factory(raw)

    @classmethod
    def from_json(cls, obj: dict) -> "SectorInfo":
        return cls(
            jh.as_long(obj, "sectorID"),
            jh.as_long(obj, "zoneGUID"),
            cls._opt_list(obj.get("spawnAreaTemplates"), SpawnAreaSpec.from_json),
            cls._opt_list(obj.get("spaceObjectTemplates"), deserialize_space_object),
            cls._opt(obj.get("asteroidDesc"), AsteroidInfo.from_json),
            cls._opt(obj.get("planetoidDesc"), PlanetoidInfo.from_json),
            cls._opt(obj.get("miningShipConfig"), MiningShipSetup.from_json),
            cls._opt_list(_filter_bot_spawns(obj.get("botSpawnTemplates")), BotSpawnSpec.from_json),
            cls._opt(obj.get("colonialProgressTemplate"), OutpostProgressSpec.from_json),
            cls._opt(obj.get("cylonProgressTemplate"), OutpostProgressSpec.from_json),
            cls._opt(obj.get("cometSectorDesc"), CometInfo.from_json),
            cls._opt(obj.get("cargoSectorDesc"), CargoSectorDesc.from_json),
            cls._opt(obj.get("debrisFieldDesc"), DebrisFieldDesc.from_json),
        )

    @property
    def comet_layout(self):
        return self._comet_sector_desc if self._comet_sector_desc is not None else CometInfo(0, False, 0)

    @property
    def cargo_sector_desc(self):
        return self._cargo_sector_desc

    @property
    def debris_field_desc(self):
        return self._debris_field_desc

    @property
    def sector_id(self) -> int:
        return self._sector_id
