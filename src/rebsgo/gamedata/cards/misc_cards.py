# github.com/Shran21

from __future__ import annotations

from rebsgo.gamedata import json_helper as jh
from rebsgo.gamedata.cards.card_base import write_layout, Card
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.reading import ConsumableEffectKind, TargetBracketMode, TournamentKind, SkillFamily, AugmentActionKind, MissileExplosionView, MissileKind
from rebsgo.vocabulary.pilot import Faction
from rebsgo.gamedata.ship_parts.parts import write_ship_items, ShipItemBody
from enum import Enum


class RegulationCard(Card):
    def __init__(self, card_guid: int, ability_target_relations: dict, ability_target_types: dict,
                 target_bracket_mode=TargetBracketMode.Default, sector_map_enabled: bool = True,
                 effect_type_blacklist=None):
        super().__init__(card_guid, CardView.Regulation)
        self.ability_target_relations = ability_target_relations
        self.ability_target_types = ability_target_types
        self.target_bracket_mode = target_bracket_mode
        self.sector_map_enabled = sector_map_enabled
        self.effect_type_blacklist = effect_type_blacklist

    @classmethod
    def from_json(cls, obj: dict) -> "RegulationCard":
        raw_rel = obj.get("abilityTargetRelations") or {}
        relations = {int(k): set(v) for k, v in raw_rel.items()}
        raw_types = obj.get("abilityTargetTypes") or {}
        types = {int(k): set(v) for k, v in raw_types.items()}
        tbm = jh.as_enum_by_name(obj, "targetBracketMode", TargetBracketMode, TargetBracketMode.Default)
        sector_map_enabled = jh.as_flag(obj, "sectorMapEnabled")
        raw_blacklist = obj.get("effectTypeBlacklist")
        blacklist = None if raw_blacklist is None else [
            (ConsumableEffectKind.None_ if x == "None" else ConsumableEffectKind[x]) if isinstance(x, str)
            else list(ConsumableEffectKind)[int(x)]
            for x in raw_blacklist
        ]
        return cls(jh.as_long(obj, "cardGUID"), relations, types, tbm, sector_map_enabled, blacklist)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_byte(self.target_bracket_mode.value)
        bw.write_boolean(self.sector_map_enabled)

        keys = list(self.ability_target_relations.keys())
        bw.write_uint16(len(keys))
        for kulcs in keys:
            bw.write_uint32(kulcs)
            value1 = 0
            for ability_side in self.ability_target_relations.get(kulcs):
                value1 |= ability_side
            value2 = 0
            for ability_target in self.ability_target_types.get(kulcs):
                value2 |= ability_target
            bw.write_uint16(value1)
            bw.write_uint16(value2)

        effect_blacklist = self.effect_type_blacklist if self.effect_type_blacklist is not None else []
        bw.write_uint16(len(effect_blacklist))
        for effect in effect_blacklist:
            bw.write_byte(effect.value)

    @property
    def sector_map_on(self) -> bool:
        return self.sector_map_enabled


class ObjectStatsCard(Card):
    def __init__(self, card_guid: int, stats):
        super().__init__(card_guid, CardView.NonShipStats)
        self.stats = stats

    @classmethod
    def from_json(cls, obj: dict) -> "ObjectStatsCard":
        return cls(jh.as_long(obj, "cardGUID"), jh.as_object_stats(obj, "Stats"))

    @property
    def stats_of(self):
        return self.stats.copy()


class TournamentCard(Card):
    def __init__(self, card_guid: int, tournament_type, min_level: int, allowed_tiers):
        super().__init__(card_guid, CardView.Tournament)
        self.type = tournament_type
        self.min_level = min_level
        self.allowed_tiers = allowed_tiers

    @classmethod
    def from_json(cls, obj: dict) -> "TournamentCard":
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_enum_by_name(obj, "type", TournamentKind),
            jh.as_byte(obj, "minLevel"),
            jh.as_long_list(obj, "allowedTiers") or [],
        )

    _HUZALREND = (
        ('byte', 'type', 'value'),
        ('byte', 'min_level'),
        ('uint32_collection', 'allowed_tiers'),
    )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        write_layout(self, bw, TournamentCard._HUZALREND)


class SkillCard(Card):
    def __init__(self, card_guid: int, level: int, max_level: int, next_training_guid: int, hash_: int,
                 training_time: float, price: int, skill_group: SkillFamily, static_buff, multiply_buff,
                 kello_keszsegek: int, sort_weight: int):
        super().__init__(card_guid, CardView.Skill)
        self.level = level
        self.max_level = max_level
        self.next_skill_card_guid = next_training_guid
        self.hash = hash_
        self.training_time = training_time
        self.price = price
        self.skill_group = skill_group
        self.static_buff = static_buff
        self.multiply_buff = multiply_buff
        self.required_skill_hash = kello_keszsegek
        self.sort_weight = sort_weight

    @classmethod
    def from_json(cls, obj: dict) -> "SkillCard":
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_short(obj, "Level"),
            jh.as_short(obj, "MaxLevel"),
            jh.as_long(obj, "nextSkillCardGuid"),
            jh.as_long(obj, "Hash"),
            jh.as_float(obj, "TrainingTime"),
            jh.as_int(obj, "Price"),
            jh.as_enum_by_name(obj, "Group", SkillFamily),
            jh.as_object_stats(obj, "StaticBuff"),
            jh.as_object_stats(obj, "MultiplyBuff"),
            jh.as_long(obj, "RequireSkillHash"),
            jh.as_int(obj, "SortWeight"),
        )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_byte(self.level & 0xFF)
        bw.write_byte(self.max_level & 0xFF)
        bw.write_uint32(self.next_skill_card_guid)
        bw.write_uint32(self.hash)
        bw.write_single(self.training_time)
        bw.write_int32(self.price)
        bw.write_byte(self.skill_group.value)
        bw.write_desc(self.static_buff)
        bw.write_desc(self.multiply_buff)
        bw.write_uint32(self.required_skill_hash)
        bw.write_uint16(self.sort_weight)


class OwnerCard(Card):
    def __init__(self, card_guid: int, is_dockable: bool, dock_range: float, level: int):
        super().__init__(card_guid, CardView.Owner)
        self.is_dockable_ = is_dockable
        self.dock_range = dock_range
        self.level = level

    @classmethod
    def from_json(cls, obj: dict) -> "OwnerCard":
        return cls(jh.as_long(obj, "cardGUID"), jh.as_flag(obj, "IsDockable"),
                   jh.as_float(obj, "DockRange"), jh.as_byte(obj, "Level"))

    _HUZALREND = (
        ('boolean', 'is_dockable_'),
        ('single', 'dock_range'),
        ('byte', 'level'),
    )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        write_layout(self, bw, OwnerCard._HUZALREND)

    @property
    def is_dockable(self) -> bool:
        return self.is_dockable_


class GlobalCard(Card):
    def __init__(self, card_guid: int, titanium_repair_card: float, cubits_repair_card: float,
                 capital_ship_price: int, undock_timeout: float, referral_bonus_guid: int,
                 special_friend_bonus: dict):
        super().__init__(card_guid, CardView.Global)
        self.titanium_repair_card = titanium_repair_card
        self.cubits_repair_card = cubits_repair_card
        self.capital_ship_price = capital_ship_price
        self.undock_timeout = undock_timeout
        self.friend_bonus_reward_guid = referral_bonus_guid
        self.special_friend_bonus = special_friend_bonus

    @classmethod
    def from_json(cls, obj: dict) -> "GlobalCard":
        nyers = obj.get("specialFriendBonus")
        special = {} if nyers is None else {int(k): int(v) for k, v in nyers.items()}
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_float(obj, "TitaniumRepairCard"),
            jh.as_float(obj, "CubitsRepairCard"),
            jh.as_long(obj, "CapitalShipPrice"),
            jh.as_float(obj, "UndockTimeout"),
            jh.as_long(obj, "friendBonusRewardGuid"),
            special,
        )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_single(self.titanium_repair_card)
        bw.write_single(self.cubits_repair_card)
        bw.write_uint32(self.capital_ship_price)
        bw.write_single(self.undock_timeout)
        bw.write_guid(self.friend_bonus_reward_guid)
        bw.write_length(len(self.special_friend_bonus))
        for kulcs, ertek in self.special_friend_bonus.items():
            bw.write_byte(kulcs & 0xFF)
            bw.write_guid(ertek)

    def repair_card(self, use_cubits: bool) -> float:
        return self.cubits_repair_card if use_cubits else self.titanium_repair_card


class RewardCard(Card):
    def __init__(self, card_guid: int, experience: int, targyak, hatas: AugmentActionKind,
                 packaged_cubits: int, package_name: str, item_group: int, colonial_tetelek, cylon_tetelek):
        super().__init__(card_guid, CardView.Reward)
        self.experience = experience
        self._ship_items = targyak
        self.action = hatas
        self.packaged_cubits = packaged_cubits
        self.package_name = package_name
        self.item_group = item_group
        self.colonial_items = colonial_tetelek
        self.cylon_items = cylon_tetelek

    @classmethod
    def from_json(cls, obj: dict) -> "RewardCard":
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_int(obj, "experience"),
            jh.as_ship_items(obj, "shipItems"),
            jh.as_enum_by_name(obj, "action", AugmentActionKind),
            jh.as_long(obj, "packagedCubits"),
            jh.as_text(obj, "packageName"),
            jh.as_long(obj, "itemGroup"),
            jh.as_ship_items(obj, "colonialItems"),
            jh.as_ship_items(obj, "cylonItems"),
        )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_int32(self.experience)
        ShipItemBody.to_wire(bw, self._ship_items)
        bw.write_byte(self.action.value)
        bw.write_uint32(self.packaged_cubits)
        bw.write_string(self.package_name)
        bw.write_uint32(self.item_group)
        write_ship_items(bw, self.colonial_items)
        write_ship_items(bw, self.cylon_items)

    def ship_items_for_faction(self, faction: Faction):
        if faction is Faction.Colonial:
            return self._get_colonial_items()
        if faction is Faction.Cylon:
            return self._get_cylon_items()
        return []

    @property
    def ship_items(self):
        if self._ship_items is None:
            return []
        return [tetel.copy() for tetel in self._ship_items]

    def _get_colonial_items(self):
        if self.colonial_items is None:
            return []
        return [tetel.copy() for tetel in self.colonial_items]

    def _get_cylon_items(self):
        if self.cylon_items is None:
            return []
        return [tetel.copy() for tetel in self.cylon_items]


class MovementCard(Card):
    def __init__(self, card_guid: int, min_yaw_speed: float = 0.1, max_pitch: float = 360.0,
                 max_roll: float = 80.0, pitch_fading: float = 2.0, yaw_fading: float = 2.0,
                 roll_fading: float = 400.0):
        super().__init__(card_guid, CardView.Movement)
        self.min_yaw_speed = min_yaw_speed
        self.max_pitch = max_pitch
        self.max_roll = max_roll
        self.pitch_fading = pitch_fading
        self.yaw_fading = yaw_fading
        self.roll_fading = roll_fading

    @classmethod
    def from_json(cls, obj: dict) -> "MovementCard":
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_float(obj, "minYawSpeed"),
            jh.as_float(obj, "maxPitch"),
            jh.as_float(obj, "maxRoll"),
            jh.as_float(obj, "pitchFading"),
            jh.as_float(obj, "yawFading"),
            jh.as_float(obj, "rollFading"),
        )

    @staticmethod
    def fallback_card() -> "MovementCard":
        return MovementCard(0, 3, 55, 50, 0.3, 0.3, 0.6)

    _HUZALREND = (
        ('single', 'min_yaw_speed'),
        ('single', 'max_pitch'),
        ('single', 'max_roll'),
        ('single', 'pitch_fading'),
        ('single', 'yaw_fading'),
        ('single', 'roll_fading'),
    )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        write_layout(self, bw, MovementCard._HUZALREND)


class ModuleCard(Card):
    def __init__(self, card_guid: int, colonial_prefab: str = "", cylon_prefab: str = ""):
        super().__init__(card_guid, CardView.Module)
        self.colonial_prefab_name = colonial_prefab
        self.cylon_prefab_name = cylon_prefab

    @classmethod
    def from_json(cls, obj: dict) -> "ModuleCard":
        return cls(jh.as_long(obj, "cardGUID"), jh.as_text(obj, "ColonialPrefab"), jh.as_text(obj, "CylonPrefab"))

    _HUZALREND = (
        ('string', 'colonial_prefab_name'),
        ('string', 'cylon_prefab_name'),
    )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        write_layout(self, bw, ModuleCard._HUZALREND)


class CounterCard(Card):
    def __init__(self, card_guid: int, name: str):
        super().__init__(card_guid, CardView.Counter)
        self._name = name

    @classmethod
    def from_json(cls, obj: dict) -> "CounterCard":
        return cls(jh.as_long(obj, "cardGUID"), jh.as_text(obj, "Name"))

    _HUZALREND = (
        ('string', '_name'),
    )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        write_layout(self, bw, CounterCard._HUZALREND)

    @property
    def name(self) -> str:
        return self._name


class MissionCard(Card):
    def __init__(self, card_guid: int, level: int, level_requirement: int, level_upper_limit: int,
                 reward_card_guid: int, recipient_face_guid: int, action: str):
        super().__init__(card_guid, CardView.Assignment)
        if self._outside_level_range(level):
            raise ValueError('level falls outside the allowed band')
        if self._outside_level_range(level_requirement):
            raise ValueError("level_requirement is out of level range")
        if self._outside_level_range(level_upper_limit):
            raise ValueError("level_upper_limit is out of level range")
        self.level = level
        self.level_requirement = level_requirement
        self.level_upper_limit = level_upper_limit
        self.reward_card_guid = reward_card_guid
        self.receiver_gui_card_guid = recipient_face_guid
        self.action = action

    @staticmethod
    def _outside_level_range(value: int) -> bool:
        return value < 0 or value > 255

    @classmethod
    def from_json(cls, obj: dict) -> "MissionCard":
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_int(obj, "Level"),
            jh.as_int(obj, "LevelRequirement"),
            jh.as_int(obj, "LevelUpperLimit"),
            jh.as_long(obj, "rewardCardGuid"),
            jh.as_long(obj, "receiverGuiCardGuid"),
            jh.as_text(obj, "Action"),
        )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_byte(self.level & 0xFF)
        bw.write_byte(self.level_requirement & 0xFF)
        bw.write_byte(self.level_upper_limit & 0xFF)
        bw.write_guid(self.reward_card_guid)
        bw.write_guid(self.receiver_gui_card_guid)
        bw.write_string(self.action)

    def _level_gate_passes(self, level: int) -> bool:
        return self.level_requirement == 0 or level >= self.level_requirement

    def _below_upper_limit(self, level: int) -> bool:
        return self.level_upper_limit == 0 or level <= self.level_upper_limit

    def level_between(self, mostani_szint: int) -> bool:
        return self._level_gate_passes(mostani_szint) and self._below_upper_limit(mostani_szint)


class MissileCard(Card):
    def __init__(self, card_guid: int, explosion_view, missile_type):
        super().__init__(card_guid, CardView.Missile)
        self.explosion_view = explosion_view
        self.missile_type = missile_type

    @classmethod
    def from_json(cls, obj: dict) -> "MissileCard":
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_enum_by_name(obj, "explosionView", MissileExplosionView),
            jh.as_enum_by_name(obj, "missileType", MissileKind),
        )

    _HUZALREND = (
        ('byte', 'explosion_view', 'value'),
        ('byte', 'missile_type', 'value'),
    )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        write_layout(self, bw, MissileCard._HUZALREND)


class DutyCard(Card):
    def __init__(self, card_guid: int, level: int, max_level: int, next_task_guid: int,
                 tally_card_guid: int, counter_value: int, experience: int, rank_title_guid: int):
        super().__init__(card_guid, CardView.Duty)
        self.level = level
        self.max_level = max_level
        self.next_duty_card_guid = next_task_guid
        self.counter_card_guid = tally_card_guid
        self.counter_value = counter_value
        self.experience = experience
        self.title_card_guid = rank_title_guid

    @classmethod
    def from_json(cls, obj: dict) -> "DutyCard":
        return cls(
            jh.as_long(obj, "cardGUID"),
            jh.as_byte(obj, "Level"),
            jh.as_byte(obj, "MaxLevel"),
            jh.as_long(obj, "nextDutyCardGuid"),
            jh.as_long(obj, "counterCardGuid"),
            jh.as_int(obj, "CounterValue"),
            jh.as_int(obj, "Experience"),
            jh.as_long(obj, "titleCardGuid"),
        )

    _HUZALREND = (
        ('byte', 'level'),
        ('byte', 'max_level'),
        ('guid', 'next_duty_card_guid'),
        ('guid', 'counter_card_guid'),
        ('int32', 'counter_value'),
        ('int32', 'experience'),
        ('guid', 'title_card_guid'),
    )

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        write_layout(self, bw, DutyCard._HUZALREND)


class TallyCardKind(Enum):
    aesirs_killed = (80000009,)
    avengers_killed = (80000026,)
    berserkers_killed = (80000028,)
    brimirs_killed = (80000035,)
    gungnirs_killed = (80000006,)
    halberds_killed = (80000023,)
    jotunns_killed = (80000011,)
    mauls_killed = (80000007,)
    raptors_killed = (80000040,)
    rhinos_killed = (80000045,)
    vanirs_killed = (177944757,)
    viper_mk3s_killed = (80000039,)
    viper_mk7_killed = (80000027,)
    vipers_killed = (80000024,)
    arena = (80000001,)
    asteroids_scanned = (80000002,)
    asteroids_mined = (61526949,)
    debris_looted = (80000003,)
    dynamic_mission_freighter_medium_success = (65917668,)
    dynamic_mission_medium_won = (76400511,)
    dynamic_mission_freighter_easy_success = (68409156,)
    dynamic_mission_easy_won = (136028543,)
    dynamic_mission_hard_won = (138322223,)
    dynamic_mission_easy_completed = (80000050,)
    dynamic_mission_medium_completed = (80000051,)
    dynamic_mission_hard_completed = (80000052,)
    wave_alpha_finished = (80000005,)
    wave_beta_finished = (80000054,)
    wave_gamma_finished = (80000055,)
    select_faction_hax = (27529097,)
    locker_from_hax = (56576009,)
    repair_hax = (134337257,)
    locker_to_hax = (101663385,)
    select_hax = (196068009,)
    jump_hax = (205937049,)
    total_deaths = (80000047,)
    pve_deaths = (80000048,)
    pvp_deaths = (80000049,)
    pvp_action_killer = (80000008,)
    pvp_action_assist = (80000059,)
    pvp_action_buffer = (80000060,)
    pvp_action_debuffer = (80000061,)
    pvp_action_savior = (80000004,)
    enemies_killed = (48097509,)
    deflected_torpedo = (44658416,)
    titanium_mined = (80000010,)
    tylium_mined = (80000015,)
    water_mined = (80000021,)
    death_payment_popup_rules = (70669140,)
    last_water_exchange = (79210422,)
    npc_downed = (80000012,)
    pilot_downed = (80000013,)
    time_played = (80000014,)
    wof_played = (108358261,)
    mining_ships_called = (118239717,)
    patrol = (80000017,)
    mining_ships_income = (80000018,)
    missions_completed = (80000019,)
    recruits_invited = (127680069,)
    sectors_visited = (80000020,)
    mining_ships_killed = (80000022,)
    freighters_killed = (160002101,)
    tylium_burned = (161454293,)
    opposite_faction_killed = (80000025,)
    wave_delta_finished = (168197797,)
    wave_alpha = (189918754,)
    wave_gamma = (190495986,)
    wave_delta = (190675810,)
    story_missions = (197138420,)
    stationaries_killed = (80000029,)
    wave_beta = (213250338,)
    comets_killed = (110,)
    last_user_interaction_spam_check = (221726988,)
    arena_points_1x1_t1 = (80000056,)
    arena_points_1x1_t2 = (80000057,)
    arena_points_1x1_t3 = (80000058,)
    number_of_deaths_since_payment_popup = (228630769,)
    story_missions_unsubmitted = (229439477,)
    damage_done = (80000036,)
    damage_dealt = (80000037,)
    took_a_hit = (80000038,)
    ancients_killed = (233054565,)
    hack_dradis_stats_differ = (241522355,)
    hack_dradis_send_disabled = (257042837,)
    daily_login = (256499151,)
    outposts_killed = (80000053,)
    outposts_damage_dealt = (232,)
    outposts_damage_received = (233,)
    drones_killed = (80000046,)
    jump_beacons_killed = (80000062,)
    planetoids_claimed = (80000063,)
    pvp_action_avenger = (80000064,)
    arena_points_3x3_t1 = (80000065,)
    arena_points_3x3_t2 = (80000066,)
    arena_points_3x3_t3 = (80000067,)

    def __new__(cls, card_guid):
        obj = object.__new__(cls)
        obj._value_ = len(cls.__members__)
        obj.card_guid = card_guid
        return obj
