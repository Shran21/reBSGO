# github.com/Shran21

from __future__ import annotations

from rebsgo.gamedata import json_helper as jh
from rebsgo.gamedata.cards.card_base import write_layout, Card
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.reading import AreaBracket, BackdropInfo, CameraFxInfo, DriftingNebulaInfo, FogInfo, LightInfo, MapStarInfo, ShipRole, SpotInfo, SunInfo
from rebsgo.vocabulary.pilot import Faction
from rebsgo.vocabulary.world import AreaInfoKind, AreaRule


class CameraCard(Card):
    def __init__(self, card_guid: int, default_zoom: float = 1.0, min_zoom: float = 10.0,
                 max_zoom: float = 20.0, soft_tremble_speed: float = 1.0, hard_tremble_speed: float = 1.0):
        super().__init__(card_guid, CardView.Camera)
        self.default_zoom = default_zoom
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self.soft_tremble_speed = soft_tremble_speed
        self.hard_tremble_speed = hard_tremble_speed

    @classmethod
    def from_json(cls, obj: dict) -> "CameraCard":
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_float(obj, "DefaultZoom"),
            jh.as_float(obj, "MinZoom"),
            jh.as_float(obj, "MaxZoom"),
            jh.as_float(obj, "SoftTrembleSpeed"),
            jh.as_float(obj, "HardTrembleSpeed"),
        )

    _HUZALREND = (
        ('single', 'default_zoom'),
        ('single', 'max_zoom'),
        ('single', 'min_zoom'),
        ('single', 'soft_tremble_speed'),
        ('single', 'hard_tremble_speed'),
    )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        write_layout(self, bw, CameraCard._HUZALREND)


class GalaxyMapCard(Card):
    def __init__(self, card_guid: int, stars: dict, tiers, base_scaling_multiplier: int, sector_scaling_multiplier: dict):
        super().__init__(card_guid, CardView.GalaxyMap)
        self.sector_scaling_multiplier = sector_scaling_multiplier
        if stars is None:
            raise TypeError('stars are required here')
        self.stars = stars
        self.tiers = tiers
        self.base_scaling_multiplier = base_scaling_multiplier

    @staticmethod
    def base_sector_ids(faction: Faction):
        return GalaxyMapCard.colonial_home_sectors() if faction is Faction.Colonial else GalaxyMapCard.cylon_home_sectors()

    @staticmethod
    def colonial_home() -> int:
        return 0

    @staticmethod
    def colonial_home_sectors():
        return [0, 49]

    @staticmethod
    def cylon_home() -> int:
        return 6

    @staticmethod
    def cylon_home_sectors():
        return [6, 50]

    @classmethod
    def from_json(cls, obj: dict) -> "GalaxyMapCard":
        raw_stars = obj.get("stars") or {}
        stars = {int(k): MapStarInfo.from_json(v) for k, v in raw_stars.items()}
        tiers = jh.as_int_list(obj, "tiers") or []
        base = jh.as_int(obj, "baseScalingMultiplier")
        raw_ssm = obj.get("sectorScalingMultiplier") or {}
        ssm = {int(k): int(v) for k, v in raw_ssm.items()}
        return cls(jh.as_long(obj, "cardGUID"), stars, tiers, base, ssm)

    @staticmethod
    def is_base_sector(faction: Faction, id: int) -> bool:
        base_sector_ids = GalaxyMapCard.base_sector_ids(faction)
        return base_sector_ids[0] == id or base_sector_ids[1] == id

    @staticmethod
    def is_start_sector(faction: Faction, id: int) -> bool:
        return id == GalaxyMapCard.start_sector(faction)

    def star(self, sector_id: int):
        return self.stars.get(sector_id)

    @staticmethod
    def start_sector(faction: Faction) -> int:
        return GalaxyMapCard.colonial_home() if faction is Faction.Colonial else GalaxyMapCard.cylon_home()

    def starter_sector_for_faction(self, faction: Faction):
        starter_id = GalaxyMapCard.start_sector(faction)
        return self.stars.get(starter_id)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        from rebsgo.gamedata.from_json.template_readers import sector_policy
        hidden = sector_policy().disabled
        visible = [star for star_id, star in self.stars.items()
                   if star_id not in hidden]
        bw.write_length(len(visible))
        for ertek in visible:
            bw.write_desc(ertek)
        bw.write_length(len(self.tiers))
        for tier in self.tiers:
            bw.write_uint16(tier)
        bw.write_int32(self.base_scaling_multiplier)
        bw.write_length(len(self.sector_scaling_multiplier))
        for kulcs, ertek in self.sector_scaling_multiplier.items():
            bw.write_uint32(kulcs)
            bw.write_uint32(ertek)


class RoomCard(Card):
    def __init__(self, card_guid: int, view: CardView, music: str, doors, npcs):
        super().__init__(card_guid, view)
        self.music = music
        self.doors = doors
        self.npcs = npcs

    @classmethod
    def from_json(cls, obj: dict) -> "RoomCard":
        raw_doors = obj.get("doors")
        doors = None if raw_doors is None else [RoomCard.RoomDoor.from_json(d) for d in raw_doors]
        raw_npcs = obj.get("NPCs")
        npcs = None if raw_npcs is None else [RoomCard.Dweller.from_json(n) for n in raw_npcs]
        view = CardView.from_code(jh.as_int(obj, "cardView"))
        return cls(jh.as_long(obj, "cardGUID"), view, jh.as_text(obj, "music"), doors, npcs)

    _HUZALREND = (
        ('desc_array', 'doors'),
        ('desc_array', 'npcs'),
        ('string', 'music'),
    )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        write_layout(self, bw, RoomCard._HUZALREND)

    class RoomDoor:
        def __init__(self, door: str, szoba_guid: int):
            self.door = door
            self.room_guid = szoba_guid

        @classmethod
        def from_json(cls, obj: dict) -> "RoomCard.RoomDoor":
            return cls(jh.as_text(obj, "Door"), jh.as_long(obj, "roomGUID"))

        _HUZALREND = (
            ('string', 'door'),
            ('uint32', 'room_guid'),
        )

        def to_wire(self, bw) -> None:
            write_layout(self, bw, RoomCard.RoomDoor._HUZALREND)

    class Dweller:
        def __init__(self, npc: str, bot_guid: int):
            self.npc = npc
            self.npc_guid = bot_guid

        @classmethod
        def from_json(cls, obj: dict) -> "RoomCard.Dweller":
            return cls(jh.as_text(obj, "NPC"), jh.as_long(obj, "NPCGUID"))

        _HUZALREND = (
            ('string', 'npc'),
            ('uint32', 'npc_guid'),
        )

        def to_wire(self, bw) -> None:
            write_layout(self, bw, RoomCard.Dweller._HUZALREND)


class SectorCard(Card):
    def __init__(self, card_guid: int, width: float, height: float, length: float, rulebook_guid: int,
                 ambient_color, fog_color, fog_density: int, dust_color, dust_density: int, nebula_desc,
                 stars_desc, stars_mult_desc, csillag_valtozat, moving_nebula_descs, light_descs, sun_descs,
                 global_fog_desc, camera_fx_desc, required_assets):
        super().__init__(card_guid, CardView.Sector)
        self.width = width
        self.height = height
        self.length = length
        self.regulation_card_guid = rulebook_guid
        self.ambient_color = ambient_color
        self.fog_color = fog_color
        self.fog_density = fog_density
        self.dust_color = dust_color
        self.dust_density = dust_density
        self.nebula_desc = nebula_desc
        self.stars_desc = stars_desc
        self.stars_mult_desc = stars_mult_desc
        self.stars_variant_desc = csillag_valtozat
        self.moving_nebula_descs = moving_nebula_descs
        self.light_descs = light_descs
        self.sun_descs = sun_descs
        self.global_fog_desc = global_fog_desc
        self.camera_fx_desc = camera_fx_desc
        self.required_assets = required_assets

    @classmethod
    def from_json(cls, obj: dict) -> "SectorCard":
        def bg(key):
            v = obj.get(key)
            return None if v is None else BackdropInfo.from_json(v)

        def desc_array(key, desc_cls):
            v = obj.get(key)
            return None if v is None else [desc_cls.from_json(x) for x in v]

        nebula_obj = obj.get("globalFogDesc")
        cam_obj = obj.get("cameraFxDesc")
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_float(obj, "width"),
            jh.as_float(obj, "height"),
            jh.as_float(obj, "length"),
            jh.as_long(obj, "regulationCardGuid"),
            jh.get_color(obj, "ambientColor"),
            jh.get_color(obj, "fogColor"),
            jh.as_int(obj, "fogDensity"),
            jh.get_color(obj, "dustColor"),
            jh.as_int(obj, "dustDensity"),
            bg("nebulaDesc"),
            bg("starsDesc"),
            bg("starsMultDesc"),
            bg("StarsVarianceDesc"),
            desc_array("movingNebulaDescs", DriftingNebulaInfo),
            desc_array("lightDescs", LightInfo),
            desc_array("sunDescs", SunInfo),
            None if nebula_obj is None else FogInfo.from_json(nebula_obj),
            None if cam_obj is None else CameraFxInfo.from_json(cam_obj),
            jh.as_text_list(obj, "requiredAssets", []),
        )

    _HUZALREND = (
        ('single', 'width'),
        ('single', 'height'),
        ('single', 'length'),
        ('uint32', 'regulation_card_guid'),
        ('color', 'ambient_color'),
        ('color', 'fog_color'),
        ('int32', 'fog_density'),
        ('color', 'dust_color'),
        ('int32', 'dust_density'),
        ('desc', 'nebula_desc'),
        ('desc', 'stars_desc'),
        ('desc', 'stars_mult_desc'),
        ('desc', 'stars_variant_desc'),
        ('desc_array', 'moving_nebula_descs'),
        ('desc_array', 'light_descs'),
        ('desc_array', 'sun_descs'),
        ('desc', 'global_fog_desc'),
        ('desc', 'camera_fx_desc'),
        ('string_array', 'required_assets'),
    )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        write_layout(self, bw, SectorCard._HUZALREND)


class WorldCard(Card):
    def __init__(self, card_guid: int, prefab_name: str, lod_count: int, radius: float, spots,
                 system_map_texture: str, frame_index: int, secondary_frame_index: int,
                 celozhato: bool, keret_hatotavon_belul: bool, force_show_on_map: bool):
        super().__init__(card_guid, CardView.World)
        self.prefab_name = prefab_name
        self.lod_count = lod_count
        self.radius = radius
        self.spots = spots
        self.system_map_textures = system_map_texture
        self.frame_index = frame_index
        self.secondary_frame_index = secondary_frame_index
        self.target_able = celozhato
        self.show_brackets_when_in_range = keret_hatotavon_belul
        self.force_show_on_map = force_show_on_map

    @classmethod
    def from_json(cls, obj: dict) -> "WorldCard":
        card_guid = _read_long(obj, "cardGUID", "cardGuid")
        prefab_name = _read_string(obj, "prefabName", "PrefabName")
        lod_count = _read_int_fallback(obj, "lodCount", "LODCount", 0) & 0xFF
        radius = _read_float_fallback(obj, "radius", "Radius", 0.0)
        spots = _read_spots(obj)
        system_map_texture = _read_string_prefer_upper(obj, "systemMapTexture", "SystemMapTexture")
        frame_index = _read_int_fallback(obj, "frameIndex", "FrameIndex", 0) & 0xFF
        secondary_frame_index = _read_int_fallback(obj, "secondaryFrameIndex", "SecondaryFrameIndex", 0) & 0xFF
        targetable = _read_bool_prefer_upper(obj, "targetable", "Targetable", False)
        show_bracket = _read_bool_prefer_upper(obj, "showBracketWhenInRange", "ShowBracketWhenInRange", False)
        force_show = _read_bool_prefer_upper(obj, "forceShowOnMap", "ForceShowOnMap", False)
        return cls(card_guid, prefab_name, lod_count, radius, spots, system_map_texture,
                   frame_index, secondary_frame_index, targetable, show_bracket, force_show)

    _HUZALREND = (
        ('string', 'prefab_name'),
        ('byte', 'lod_count'),
        ('single', 'radius'),
        ('desc_array', 'spots'),
        ('string', 'system_map_textures'),
        ('byte', 'frame_index'),
        ('byte', 'secondary_frame_index'),
        ('boolean', 'target_able'),
        ('boolean', 'show_brackets_when_in_range'),
        ('boolean', 'force_show_on_map'),
    )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        write_layout(self, bw, WorldCard._HUZALREND)

    def spot(self, object_point_server_hash: int):
        if self.spots is None or len(self.spots) == 0:
            return None
        for spot in self.spots:
            if spot.object_point_server_hash == object_point_server_hash:
                return spot
        return None

    @property
    def is_target_able(self) -> bool:
        return self.target_able

    @property
    def brackets_within_range(self) -> bool:
        return self.show_brackets_when_in_range

    @property
    def always_on_map(self) -> bool:
        return self.force_show_on_map

    def radius_of(self) -> float:
        return self.radius


def _num(el):
    return el if isinstance(el, (int, float)) and not isinstance(el, bool) else None


def _read_long(obj, lower, upper) -> int:
    v = _num(obj.get(lower))
    if v is not None:
        return int(v)
    v = _num(obj.get(upper))
    return int(v) if v is not None else 0


def _read_int_fallback(obj, lower, upper, fallback) -> int:
    v = _num(obj.get(lower))
    if v is not None:
        return int(v)
    v = _num(obj.get(upper))
    return int(v) if v is not None else fallback


def _read_float_fallback(obj, lower, upper, fallback) -> float:
    from rebsgo.helpers.floats import f32

    v = _num(obj.get(lower))
    if v is not None:
        return f32(v)
    v = _num(obj.get(upper))
    return f32(v) if v is not None else f32(fallback)


def _str_val(el):
    if el is None:
        return None
    if isinstance(el, bool):
        return str(el).lower()
    if isinstance(el, (str, int, float)):
        return str(el)
    return None


def _read_string(obj, lower, upper):
    lower_v = _str_val(obj.get(lower))
    if lower_v is not None and lower_v.strip() != "":
        return lower_v
    upper_v = _str_val(obj.get(upper))
    return upper_v if upper_v is not None else lower_v


def _read_string_prefer_upper(obj, lower, upper):
    lower_v = _str_val(obj.get(lower))
    upper_v = _str_val(obj.get(upper))
    if (lower_v is None or lower_v.strip() == "") and upper_v is not None:
        return upper_v
    if upper_v is not None and lower_v is not None and upper_v != lower_v:
        return upper_v
    return lower_v if lower_v is not None else upper_v


def _bool_val(el):
    return el if isinstance(el, bool) else None


def _read_bool_prefer_upper(obj, lower, upper, fallback) -> bool:
    lower_v = _bool_val(obj.get(lower))
    upper_v = _bool_val(obj.get(upper))
    if lower_v is None and upper_v is not None:
        return upper_v
    if upper_v is not None and (lower_v is None or (lower_v == fallback and upper_v != fallback)):
        return upper_v
    return lower_v if lower_v is not None else (upper_v if upper_v is not None else fallback)


def _read_spots(obj):
    lower = obj.get("spots")
    upper = obj.get("Spots")
    lower = lower if isinstance(lower, list) else None
    upper = upper if isinstance(upper, list) else None
    if lower is None and upper is None:
        return None
    lower_spots = None if lower is None else [SpotInfo.from_json(s) for s in lower]
    upper_spots = None if upper is None else [SpotInfo.from_json(s) for s in upper]
    if (lower_spots is None or len(lower_spots) == 0) and (upper_spots is not None and len(upper_spots) != 0):
        return upper_spots
    return lower_spots if lower_spots is not None else upper_spots


class ZoneCard(Card):
    def __init__(self, card_guid: int, json_key: str, terulet_ikon: str, terulet_kep: str,
                 terulet_kep_cylon: str, zone_info_type, min_level: int, max_level: int,
                 can_join_with_party: bool, tier_white_list, ship_black_list, roles_black_list, plugins, keret_sorok):
        super().__init__(card_guid, CardView.Zone)
        self.json_key = json_key
        self.zone_icon_file_name = terulet_ikon
        self.zone_image_file_name = terulet_kep
        self.zone_image_cylon_file_name = terulet_kep_cylon
        self.zone_info_type = zone_info_type
        self.min_level = min_level
        self.max_level = max_level
        self.can_join_with_party = can_join_with_party
        self.tier_white_list = tier_white_list
        self.ship_black_list = ship_black_list
        self.roles_black_list = roles_black_list
        self.plugins = plugins
        self.bracket_infos = keret_sorok

    @classmethod
    def from_json(cls, obj: dict) -> "ZoneCard":
        raw_brackets = obj.get("BracketInfo")
        brackets = None if raw_brackets is None else [AreaBracket.from_json(b) for b in raw_brackets]
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_text(obj, "jsonKey"),
            jh.as_text(obj, "zoneIconFileName"),
            jh.as_text(obj, "zoneImageFileName"),
            jh.as_text(obj, "zoneImageCylonFileName"),
            jh.as_enum_by_name(obj, "zoneInfoType", AreaInfoKind),
            jh.as_short(obj, "minLevel"),
            jh.as_short(obj, "maxLevel"),
            jh.as_flag(obj, "canJoinWithParty"),
            jh.as_int_list(obj, "tierWhiteList") or [],
            jh.as_long_list(obj, "shipBlackList") or [],
            jh.as_enum_list(obj, "rolesBlackList", ShipRole) or [],
            jh.as_enum_list(obj, "Plugins", AreaRule) or [],
            brackets,
        )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_string(self.json_key)
        bw.write_string(self.zone_icon_file_name)
        bw.write_string(self.zone_image_file_name)
        bw.write_string(self.zone_image_cylon_file_name)
        bw.write_byte(self.zone_info_type.value)
        bw.write_int16(self.min_level)
        bw.write_int16(self.max_level)
        bw.write_boolean(self.can_join_with_party)

        bw.write_uint16(len(self.tier_white_list))
        for tier in self.tier_white_list:
            bw.write_byte(tier)

        bw.write_uint32_collection(self.ship_black_list)
        bw.write_desc_collection(self.roles_black_list)
        bw.write_desc_collection(self.plugins)
        bw.write_desc_collection(self.bracket_infos)
