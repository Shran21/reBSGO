# github.com/Shran21

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from rebsgo.gamedata import json_helper as jh
from rebsgo.geometry.primitives.quaternion import Quaternion
from rebsgo.geometry.primitives.transform import Transform
from rebsgo.geometry.primitives.vector2 import Vector2
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.vocabulary.sorszamos_enum import SorszamosEnum
from rebsgo.vocabulary.pilot import Faction
from types import MappingProxyType
from typing import Mapping, Optional
import logging
import threading


class AbilityActionKind(SorszamosEnum):
    None_ = 0
    FireMissle = 1
    FireCannon = 2
    DropFlare = 3
    Buff = 4
    RestoreBuff = 5
    ResourceScan = 6
    Debuff = 7
    FireMining = 8
    Flak = 9
    PointDefence = 10
    DispellVirus = 11
    Follow = 12
    ManeuverFlip = 13
    Slide = 14
    ActivatePaintTheTarget = 15
    FollowFriend = 16
    ActivateJumpTargetTransponder = 17
    ToggleStealth = 18
    FireTorpedo = 19
    ToggleSystem = 20
    FireLightMissile = 21
    FireHeavyMissile = 22
    FireShotgun = 23
    FireKillCannon = 24
    FireMachineGun = 25
    Fortify = 26
    DevBuff = 27
    ShortCircuit = 28
    DropAntiStealthMine = 29
    DeflectMissile = 30
    DropMine = 31


class AugmentActionKind(Enum):
    None_ = 0
    SkillTime = 1
    Lock = 2
    SwitchFaction = 3
    Teleport = 4
    LootItem = 5

    @property
    def value_byte(self) -> int:
        return self._value_


class ConsumableEffectKind(SorszamosEnum):
    None_ = 0
    DamageKinetic = 1
    DamageExplosion = 2
    DamageNuclear = 3
    DamageShrapnel = 4
    DamageHighVelocity = 5
    DamageEmp = 6
    Heal = 7
    Recharge = 8
    Scan = 9
    Buff = 10


class Info(ABC):
    def __init__(self, name: str):
        self._name = name
        self._title = name
        self.position = Vector3.zero()
        self.rotation = Quaternion.identity()

    @abstractmethod
    def to_wire(self, bw) -> None:
        ...


class MapStarInfo:
    def __init__(self, id: int, position: Vector2, gui_index: int, star_faction: Faction,
                 colonial_threat_level: int, cylon_threat_level: int, star_guid: int,
                 can_colonial_outpost: bool, can_cylon_outpost: bool, can_colonial_jump_beacon: bool,
                 can_cylon_jump_beacon: bool, can_jump_colonial: bool, can_jump_cylon: bool):
        self._id = id
        self.position = position
        self.gui_index = gui_index
        self.star_faction = star_faction
        self.colonial_threat_level = colonial_threat_level
        self.cylon_threat_level = cylon_threat_level
        self.sector_guid = star_guid
        self.can_colonial_outpost = can_colonial_outpost
        self.can_cylon_outpost = can_cylon_outpost
        self.can_colonial_jump_beacon = can_colonial_jump_beacon
        self.can_cylon_jump_beacon = can_cylon_jump_beacon
        self.can_jump_colonial = can_jump_colonial
        self.can_jump_cylon = can_jump_cylon

    @classmethod
    def from_json(cls, obj: dict) -> "MapStarInfo":
        pos_obj = obj.get("Position")
        position = None if pos_obj is None else Vector2(jh.as_float(pos_obj, "x"), jh.as_float(pos_obj, "y"))
        raw_faction = obj.get("StarFaction")
        if isinstance(raw_faction, str):
            star_faction = Faction[raw_faction]
        elif raw_faction is None:
            star_faction = None
        else:
            star_faction = Faction.from_code(int(raw_faction))
        return cls(
            jh.as_long(obj, "Id"),
            position,
            jh.as_byte(obj, "GUIIndex"),
            star_faction,
            jh.as_int(obj, "ColonialThreatLevel"),
            jh.as_int(obj, "CylonThreatLevel"),
            jh.as_long(obj, "SectorGUID"),
            jh.as_flag(obj, "CanColonialOutpost"),
            jh.as_flag(obj, "CanCylonOutpost"),
            jh.as_flag(obj, "CanColonialJumpBeacon"),
            jh.as_flag(obj, "CanCylonJumpBeacon"),
            jh.as_flag(obj, "CanJumpColonial"),
            jh.as_flag(obj, "CanJumpCylon"),
        )

    def to_wire(self, bw) -> None:
        bw.write_uint32(self._id)
        safe_position = Vector2.zero() if self.position is None else self.position
        bw.write_vector2(safe_position)
        bw.write_byte(self.gui_index)
        safe_faction = Faction.Neutral if self.star_faction is None else self.star_faction
        bw.write_byte(safe_faction.value)
        bw.write_int16(self.colonial_threat_level)
        bw.write_int16(self.cylon_threat_level)
        bw.write_guid(self.sector_guid)
        bw.write_boolean(self.can_colonial_outpost)
        bw.write_boolean(self.can_cylon_outpost)
        bw.write_boolean(self.can_colonial_jump_beacon)
        bw.write_boolean(self.can_cylon_jump_beacon)

    def jump_open_to(self, faction: Faction) -> bool:
        return self.can_jump_colonial if faction is Faction.Colonial else self.can_jump_cylon

    @property
    def id(self) -> int:
        return self._id

    def position_of(self) -> Vector2:
        return self.position


class MissileExplosionView(Enum):
    Standard = 0
    Nuclear = 1
    NuclearMini = 2
    Torpedo = 4

    @property
    def value_byte(self) -> int:
        return self._value_


class MissileKind(Enum):
    Normal = 0
    Nuke = 1
    Torpedo = 2

    @property
    def value_byte(self) -> int:
        return self._value_


class ObjectStat(Enum):
    None_ = 0
    Accuracy = 2
    DamageHigh = 3
    DamageLow = 4
    CriticalOffense = 5
    PenetrationStrength = 6
    ArmorPiercing = 7
    DamageMining = 8
    FlareRangeBase = 9
    DrainHigh = 10
    DrainLow = 11
    Avoidance = 12
    AvoidanceFading = 13
    FirewallRating = 14
    ArmorValue = 15
    CriticalDefense = 16
    DurabilityBonus = 17
    Acceleration = 18
    PitchAcceleration = 19
    YawAcceleration = 20
    RollAcceleration = 21
    StrafeAcceleration = 22
    AccelerationMultiplierOnBoost = 23
    InertiaCompensation = 24
    Speed = 25
    BoostSpeed = 26
    StrafeMaxSpeed = 27
    PitchMaxSpeed = 28
    YawMaxSpeed = 29
    RollMaxSpeed = 30
    TurnAcceleration = 31
    TurnSpeed = 32
    MaxHullPoints = 33
    HullRecovery = 34
    MaxPowerPoints = 35
    PowerRecovery = 36
    DradisRange = 37
    MapRange = 38
    BoostCost = 39
    MiningVulnerability = 40
    FtlRange = 41
    FtlCharge = 42
    FtlCooldown = 43
    FtlCost = 44
    JumpTargetTransponderPowerPointCost = 45
    OptimalRange = 46
    MaxRange = 47
    MinRange = 48
    Angle = 49
    PowerPointCost = 50
    HullPointRestore = 51
    PowerPointRestore = 52
    Cooldown = 53
    Duration = 54
    LifeTime = 55
    MissileMaxHullPoints = 56
    MissileAcceleration = 57
    MissileSpeed = 58
    MissileTurnRate = 59
    MissileDamageHigh = 60
    MissileDamageLow = 61
    MissileCriticalOffense = 62
    MissileArmorPiercing = 63
    MissileDrainHigh = 64
    MissileDrainLow = 65
    MissileAvoidance = 66
    MissileMaxRange = 67
    MissileMinRange = 68
    MissileAngle = 69
    MissilePowerPointCost = 70
    MissileCooldown = 71
    MissileLifeTime = 72
    CannonAccuracy = 73
    CannonDamageHigh = 74
    CannonDamageLow = 75
    CannonCriticalOffense = 76
    CannonArmorPiercing = 77
    CannonDrainHigh = 78
    CannonDrainLow = 79
    CannonOptimalRange = 80
    CannonMaxRange = 81
    CannonMinRange = 82
    CannonAngle = 83
    CannonPowerPointCost = 84
    CannonCooldown = 85
    MiningAccuracy = 86
    MiningDamageHigh = 87
    MiningDamageLow = 88
    MiningCriticalOffense = 89
    MiningArmorPiercing = 90
    MiningOptimalRange = 91
    MiningMaxRange = 92
    MiningMinRange = 93
    MiningAngle = 94
    MiningPowerPointCost = 95
    MiningCooldown = 96
    FlareRange = 97
    FlarePowerPointCost = 98
    FlareCooldown = 99
    ManeuverPowerPointCost = 100
    ManeuverCooldown = 101
    BuffMaxRange = 102
    BuffMinRange = 103
    BuffAngle = 104
    BuffPowerPointCost = 105
    BuffCooldown = 106
    BuffDuration = 107
    DebuffPenetrationStrength = 108
    DebuffMaxRange = 109
    DebuffMinRange = 110
    DebuffAngle = 111
    DebuffPowerPointCost = 112
    DebuffCooldown = 113
    DebuffDuration = 114
    RestoreHullPointRestore = 115
    RestorePowerPointRestore = 116
    RestoreMaxRange = 117
    RestoreMinRange = 118
    RestoreAngle = 119
    RestorePowerPointCost = 120
    RestoreCooldown = 121
    MineMaxHullPoints = 122
    MineAvoidence = 123
    MineDamageHigh = 124
    MineDamageLow = 125
    MineCriticalOffense = 126
    MineArmorPiercing = 127
    MinePowerPointCost = 128
    MineCooldown = 129
    MineLifeTime = 130
    AoeInnerRadius = 131
    AoeOuterRadius = 132
    AoeDropoffIndex = 133
    TorpedoMaxHullPoints = 134
    TorpedoAcceleration = 135
    TorpedoSpeed = 136
    TorpedoTurnRate = 137
    TorpedoDamageHigh = 138
    TorpedoDamageLow = 139
    TorpedoCriticalOffense = 140
    TorpedoArmorPiercing = 141
    TorpedoDrainHigh = 142
    TorpedoDrainLow = 143
    TorpedoAvoidance = 144
    TorpedoMaxRange = 145
    TorpedoMinRange = 146
    TorpedoAngle = 147
    TorpedoPowerPointCost = 148
    TorpedoCooldown = 149
    TorpedoLifeTime = 150
    PpCostPerSec = 151
    Signature = 152
    Detection = 153
    DetectionInnerRadius = 154
    DetectionOuterRadius = 155
    DetectionDropoffIndex = 156
    DetectionVisualRadius = 157
    DrainResistance = 158
    LightMissileMaxHullPoints = 159
    LightMissileAcceleration = 160
    LightMissileSpeed = 161
    LightMissileTurnRate = 162
    LightMissileDamageHigh = 163
    LightMissileDamageLow = 164
    LightMissileCriticalOffense = 165
    LightMissileArmorPiercing = 166
    LightMissileDrainHigh = 167
    LightMissileDrainLow = 168
    LightMissileAvoidance = 169
    LightMissileMaxRange = 170
    LightMissileMinRange = 171
    LightMissileAngle = 172
    LightMissilePowerPointCost = 173
    LightMissileCooldown = 174
    LightMissileLifeTime = 175
    HeavyMissileMaxHullPoints = 176
    HeavyMissileAcceleration = 177
    HeavyMissileSpeed = 178
    HeavyMissileTurnRate = 179
    HeavyMissileDamageHigh = 180
    HeavyMissileDamageLow = 181
    HeavyMissileCriticalOffense = 182
    HeavyMissileArmorPiercing = 183
    HeavyMissileDrainHigh = 184
    HeavyMissileDrainLow = 185
    HeavyMissileAvoidance = 186
    HeavyMissileMaxRange = 187
    HeavyMissileMinRange = 188
    HeavyMissileAngle = 189
    HeavyMissilePowerPointCost = 190
    HeavyMissileCooldown = 191
    HeavyMissileLifeTime = 192
    ShotgunAccuracy = 193
    ShotgunDamageHigh = 194
    ShotgunDamageLow = 195
    ShotgunDrainHigh = 196
    ShotgunDrainLow = 197
    ShotgunCriticalOffense = 198
    ShotgunArmorPiercing = 199
    ShotgunOptimalRange = 200
    ShotgunMaxRange = 201
    ShotgunMinRange = 202
    ShotgunAngle = 203
    ShotgunPowerPointCost = 204
    ShotgunCooldown = 205
    KillCannonAccuracy = 206
    KillCannonDamageHigh = 207
    KillCannonDamageLow = 208
    KillCannonDrainHigh = 209
    KillCannonDrainLow = 210
    KillCannonCriticalOffense = 211
    KillCannonArmorPiercing = 212
    KillCannonOptimalRange = 213
    KillCannonMaxRange = 214
    KillCannonMinRange = 215
    KillCannonAngle = 216
    KillCannonPowerPointCost = 217
    KillCannonCooldown = 218
    MachineGunAccuracy = 219
    MachineGunDamageHigh = 220
    MachineGunDamageLow = 221
    MachineGunDrainHigh = 222
    MachineGunDrainLow = 223
    MachineGunCriticalOffense = 224
    MachineGunArmorPiercing = 225
    MachineGunOptimalRange = 226
    MachineGunMaxRange = 227
    MachineGunMinRange = 228
    MachineGunAngle = 229
    MachineGunPowerPointCost = 230
    MachineGunCooldown = 231
    MetaWeaponPowerCost = 232
    ToggleSystemPowerPointCost = 233
    ToggleSystemCooldown = 234
    ToggleSystemPowerCostPerSec = 235
    MetaPropulsion = 236
    MetaManeuverability = 237
    JumpTargetTransponderCooldown = 238
    ShortCircuitMaxRange = 239
    ShortCircuitMinRange = 240
    ShortCircuitAngle = 241
    ShortCircuitPowerPointCost = 242
    ShortCircuitCooldown = 243
    ShortCircuitDuration = 244
    ShortCircuitRepair = 245
    SmartMineMaxHullPoints = 246
    SmartMineMaxPowerPoints = 247
    SmartMineAvoidance = 248
    SmartMineArmorValue = 249
    SmartMineLifetime = 250
    SmartMineCooldown = 251
    SmartMinePowerPointCost = 252
    SmartMineMinRange = 253
    SmartMineMaxRange = 254
    SmartMineDamageHigh = 255
    SmartMineDamageLow = 256
    SmartMineArmorPiercing = 257
    SmartMineCriticialOffense = 258
    SmartMineDrainHigh = 259
    SmartMineDrainLow = 260
    SmartMinePenetrationStrength = 261
    SmartMineOptimalRange = 262
    SmartMineAccuracy = 263
    MetaWeaponCooldown = 264
    MaxVitalPoints = 265
    VitalRecovery = 266
    VitalPointRestore = 267
    DecayDamageFactor = 268
    DecayResistance = 269
    DecayHigh = 270
    DecayLow = 271
    MissileDecayHigh = 272
    MissileDecayLow = 273
    CannonDecayHigh = 274
    CannonDecayLow = 275
    TorpedoDecayHigh = 276
    TorpedoDecayLow = 277
    LightMissileDecayHigh = 278
    LightMissileDecayLow = 279
    HeavyMissileDecayHigh = 280
    HeavyMissileDecayLow = 281
    ShotgunDecayHigh = 282
    ShotgunDecayLow = 283
    KillCannonDecayHigh = 284
    KillCannonDecayLow = 285
    MachineGunDecayHigh = 286
    MachineGunDecayLow = 287
    SmartMineDecayHigh = 288
    SmartMineDecayLow = 289
    CargoHoldVolume = 290
    CargoPickupDelay = 291
    CargoDropoffDelay = 292
    CargoLootDelay = 293

    @property
    def value_short(self) -> int:
        return self._value_

    @classmethod
    def from_code(cls, value: int) -> "ObjectStat | None":
        return _object_stat_BY_VALUE.get(value)
_object_stat_BY_VALUE = {s.value: s for s in ObjectStat}


class Price:
    def __init__(self, tetelek=None):
        self._lock = threading.RLock()
        if isinstance(tetelek, Price):
            tetelek = tetelek._items
        self._items: dict[int, float] = dict(tetelek) if tetelek else {}

    def take_price(self, price: "Price", count: int = 1) -> None:
        with self._lock:
            for item_guid, ertek in price._items.items():
                count_per_count = ertek * count
                if item_guid not in self._items:
                    self._items[item_guid] = count_per_count
                else:
                    self._items[item_guid] = self._items[item_guid] + count_per_count

    def for_faction(self, targy_guid: int) -> float:
        with self._lock:
            return self._items.get(targy_guid, 0.0)

    def add_item(self, card_guid: int, count: int) -> None:
        with self._lock:
            self._items[card_guid] = float(count)

    @property
    def empty(self) -> bool:
        with self._lock:
            return len(self._items) == 0

    def to_wire(self, bw) -> None:
        with self._lock:
            size_to_write = len(self._items)
            bw.write_length(size_to_write)
            for kulcs, ertek in self._items.items():
                bw.write_guid(kulcs)
                bw.write_single(ertek)

    def items(self) -> Mapping[int, float]:
        with self._lock:
            return MappingProxyType(self._items)

    def __repr__(self) -> str:
        return "<Price " + f"items={self._items}" + ">"


class ShipAbilityAffect(Enum):
    Selected = 0
    Ignore = 1
    Area = 2
    MultiWeaponTarget = 3

    @property
    def value_byte(self) -> int:
        return self._value_


class ShipAbilityLaunch(Enum):
    None_ = 0
    Auto = 1
    Manual = 2

    @property
    def value_byte(self) -> int:
        return self._value_


class ShipAbilityTarget(Enum):
    Asteroid = 1
    Ship = 2
    Any = 4
    Missile = 8
    Planetoid = 16
    Mine = 32
    Transponder = 64
    Comet = 128

    @property
    def value_byte(self) -> int:
        return self._value_

    @classmethod
    def from_code(cls, num: int) -> "ShipAbilityTarget | None":
        return _ship_ability_target_BY_VALUE.get(num)
_ship_ability_target_BY_VALUE = {t.value: t for t in ShipAbilityTarget}


class ShipAbilityTargetTier(Enum):
    Tier1 = 1
    Tier2 = 2
    Tier3 = 4
    Tier4 = 8
    Any = 16

    @classmethod
    def from_code(cls, value: int) -> "ShipAbilityTargetTier | None":
        return _ship_ability_target_tier_BY_VALUE.get(value)
_ship_ability_target_tier_BY_VALUE = {t.value: t for t in ShipAbilityTargetTier}


class ShipConsumableOption(Enum):
    Undefined = 0
    Using = 1
    NotUsing = 2
    Optional = 3

    @property
    def value_byte(self) -> int:
        return self._value_


class ShipRole(Enum):
    Fighter = 1
    Bomber = 2
    Command = 3
    ElectronicWarfare = 4
    Engineer = 5
    Interceptor = 6
    Gunship = 7
    Picket = 8
    Destroyer = 9
    Artillery = 10
    Assault = 11
    Stealth = 12
    Carrier = 13
    Mothership = 14

    @property
    def value_byte(self) -> int:
        return self._value_

    def to_wire(self, bw) -> None:
        bw.write_byte(self._value_)


class ShipSlotType(SorszamosEnum):
    undefined = 0
    computer = 1
    engine = 2
    hull = 3
    weapon = 4
    ship_paint = 5
    avionics = 6
    launcher = 7
    defensive_weapon = 8
    gun = 9
    role = 10
    special_weapon = 11


class ShipSystemClass(Enum):
    Standart = 1
    Elite = 2

    @property
    def value_byte(self) -> int:
        return self._value_


class ShopCategory(SorszamosEnum):
    None_ = 0
    Resource = 1
    Augment = 2
    Consumable = 3
    System = 4
    StarterPack = 5
    Ship = 6
    Unknown = 7

    @property
    def value_byte(self) -> int:
        return self._value_

    @property
    def is_item_countable(self) -> bool:
        return self in (ShopCategory.Resource, ShopCategory.Augment, ShopCategory.Consumable)

    @property
    def type(self):
        from rebsgo.gamedata.ship_parts.parts import ItemType

        fajtak = {
            ShopCategory.Resource: ItemType.Countable,
            ShopCategory.Augment: ItemType.Countable,
            ShopCategory.Consumable: ItemType.Countable,
            ShopCategory.System: ItemType.System,
            ShopCategory.Ship: ItemType.Ship,
            ShopCategory.StarterPack: ItemType.Starter,
            ShopCategory.None_: ItemType.None_,
        }
        if self not in fajtak:
            raise RuntimeError(f"no item kind maps to shop category {self}")
        return fajtak[self]


class ShopItemKind(SorszamosEnum):
    None_ = 0
    Resource = 1
    Augment = 2
    Round = 3
    Flare = 4
    Mine = 5
    Missile = 6
    Power = 7
    Repair = 8
    PointDefense = 9
    Flak = 10
    Transponder = 11
    Junk = 12
    Radio = 13
    TechAnalysis = 14
    Weapon = 15
    Computer = 16
    Hull = 17
    Engine = 18
    ShipPaint = 19
    Avionics = 20
    StarterPack = 21
    Torpedo = 22
    Ship = 23
    MetalPlate = 24
    AntiCapitalMissile = 25
    RadiationControl = 26
    Unknown = 27

    @property
    def value_byte(self) -> int:
        return self._value_


class SkillFamily(Enum):
    Computer = 1
    Engine = 2
    Hull = 3
    Weapon = 4

    @property
    def value_byte(self) -> int:
        return self._value_


class SpotKind(SorszamosEnum):
    Weapon = 0
    Sticker = 1
    Mining = 2
    Door = 3

    @property
    def wire_code(self) -> int:
        return self._value_ + 1


class StatView(SorszamosEnum):
    MinRange = 0
    MaxRange = 1
    OptimalRange = 2
    Duration = 3
    Cooldown = 4
    BuffCost = 5
    Durability = 6
    Target = 7
    DMGLow = 8
    DMGHigh = 9
    Accuracy = 10
    CriticalOffense = 11
    Angle = 12
    Mining = 13
    FlareRange = 14
    RestoreBuff = 15
    RemoteBuffMultiply = 16
    StaticBuff = 17
    RestorePowerBuff = 18
    DrainLow = 19
    DrainHigh = 20
    ArmorPiercing = 21
    ArmorValue = 22
    HPRecovery = 23
    PPRecovery = 24
    Speed = 25
    TurnSpeed = 26
    TurnAcceleration = 27
    InertiaCompensation = 28
    MultiplyBuff = 29
    RemoteBuffAdd = 30
    AoERadius = 31
    BuffCostPerSecond = 32
    ToggleSystemAdd = 33
    ToggleSystemMultiply = 34
    HP = 35
    LifeTime = 36
    RestoreVitalBuff = 37


class TargetBracketMode(SorszamosEnum):
    Default = 0
    AllEnemy = 1


class TournamentKind(Enum):
    Strike = 1
    Escort = 2
    Liner = 3

    @property
    def value_byte(self) -> int:
        return self._value_


class AreaRewardRank:
    def __init__(self, rank: int, guid: int):
        self.rank = rank
        self.guid = guid

    @classmethod
    def from_json(cls, obj: dict) -> "AreaRewardRank":
        return cls(jh.as_byte(obj, "rank"), jh.as_long(obj, "guid"))

    def to_wire(self, bw) -> None:
        bw.write_byte(self.rank)
        bw.write_uint32(self.guid)


class BackdropInfo(Info):
    def __init__(self, model_name: str, color, rotation=None, position=None):
        super().__init__("Background")
        self.prefab_name = model_name
        self.color = color
        if rotation is not None:
            self.rotation = rotation
        if position is not None:
            self.position = position

    @classmethod
    def from_json(cls, obj: dict) -> "BackdropInfo":
        return cls(jh.as_text(obj, "prefabName"), jh.get_color(obj, "color"),
                   jh.get_quaternion(obj, "rotation"), jh.get_vector3(obj, "position"))

    def to_wire(self, bw) -> None:
        bw.write_string(self.prefab_name)
        bw.write_quaternion(self.rotation)
        bw.write_color(self.color)
        bw.write_vector3(self.position)


class CameraFxInfo(Info):
    def __init__(self, force_disable_bloom: bool):
        super().__init__("")
        self.force_disable_bloom = force_disable_bloom

    @classmethod
    def from_json(cls, obj: dict) -> "CameraFxInfo":
        return cls(jh.as_flag(obj, "forceDisableBloom"))

    def to_wire(self, bw) -> None:
        bw.write_boolean(self.force_disable_bloom)


class FogInfo(Info):
    def __init__(self, enabled: bool, color, density: float, start_distance: float):
        super().__init__("")
        self.enabled = enabled
        self.color = color
        self.density = density
        self.start_distance = start_distance

    @classmethod
    def from_json(cls, obj: dict) -> "FogInfo":
        return cls(jh.as_flag(obj, "enabled"), jh.get_color(obj, "color"),
                   jh.as_float(obj, "density"), jh.as_float(obj, "startDistance"))

    def to_wire(self, bw) -> None:
        bw.write_boolean(self.enabled)
        bw.write_color(self.color)
        bw.write_single(self.density)
        bw.write_single(self.start_distance)


class LightInfo(Info):
    def __init__(self, name: str, rotation, color, intensity: float):
        super().__init__(name)
        self.color = color
        self.rotation = rotation
        self.intensity = intensity

    @classmethod
    def from_json(cls, obj: dict) -> "LightInfo":
        return cls(jh.as_text(obj, "name"), jh.get_quaternion(obj, "rotation"),
                   jh.get_color(obj, "color"), jh.as_float(obj, "intensity"))

    def to_wire(self, bw) -> None:
        bw.write_quaternion(self.rotation)
        bw.write_color(self.color)
        bw.write_single(self.intensity)


class DriftingNebulaInfo(Info):
    @classmethod
    def from_json(cls, obj: dict) -> "DriftingNebulaInfo":
        return cls(
            jh.as_text(obj, "matSuffix"),
            jh.as_text(obj, "modelName"),
            jh.get_quaternion(obj, "rotation"),
            jh.get_vector3(obj, "position"),
            jh.get_vector3(obj, "scale"),
            jh.get_vector2(obj, "textureOffset"),
            jh.get_vector2(obj, "textureScale"),
            jh.get_color(obj, "color"),
        )

    def __init__(self, mat_suffix: str, model_name: str, rotation, position, scale,
                 texture_offset, texture_scale, color):
        super().__init__("MovingNebula")
        self.mat_suffix = mat_suffix
        self.model_name = model_name
        self.scale = scale
        self.texture_offset = texture_offset
        self.texture_scale = texture_scale
        self.color = color
        self.position = position
        self.rotation = rotation

    def to_wire(self, bw) -> None:
        bw.write_string(self.mat_suffix)
        bw.write_string(self.model_name)
        bw.write_quaternion(self.rotation)
        bw.write_vector3(self.position)
        bw.write_vector3(self.scale)
        bw.write_vector2(self.texture_offset)
        bw.write_vector2(self.texture_scale)
        bw.write_color(self.color)


log = logging.getLogger(__name__)
_STATS_ALLOWED_TO_BE_ADDED_WHEN_MISSING = frozenset((
    ObjectStat.CriticalOffense,
    ObjectStat.DrainResistance,
))


class ObjectStats:
    def __init__(self, stats: Optional[dict] = None):
        if isinstance(stats, ObjectStats):
            self.stats = dict(stats.all_stats)
        elif stats is None:
            self.stats = {}
        else:
            self.stats = stats

    def __repr__(self) -> str:
        return "ObjectStats(" + f"stats={self.stats}" + ")"

    @property
    def all_stats(self) -> dict:
        return self.stats

    def wipe(self) -> None:
        self.stats.clear()

    def to_wire(self, bw) -> None:
        bw.write_length(len(self.stats))
        for kulcs, value in self.stats.items():
            bw.write_uint16(kulcs.value)
            bw.write_single(value)

    def take_stats(self, stats: "ObjectStats") -> None:
        self.stats.update(stats.all_stats)

    def stat(self, object_stat: ObjectStat) -> Optional[float]:
        return self.stats.get(object_stat)

    @staticmethod
    def stats_multiply_bonus(stats: "ObjectStats", szorzok: "ObjectStats") -> "ObjectStats":
        return_stats = ObjectStats()
        mapped_multipliers = ObjectStats.as_stats(szorzok)
        for mult_key, mult_value in mapped_multipliers.all_stats.items():
            if stats.holds_stat(mult_key):
                new_value = stats.stat(mult_key) * mult_value
                delta_value = new_value - stats.stat(mult_key)
                return_stats.set_stat(mult_key, delta_value)
        return return_stats

    def stat_or_default(self, object_stat: ObjectStat, alapertelmezett: float = 0.0) -> float:
        return self.stats.get(object_stat, alapertelmezett)

    def set_stat(self, object_stat: ObjectStat, new_value: float) -> None:
        self.stats[object_stat] = new_value

    @staticmethod
    def scale_where_bonus_applies(bonusz_statok: "ObjectStats", alany: "ObjectStats") -> "ObjectStats":
        eredmeny = ObjectStats()
        to_apply_on_stats = alany.all_stats
        if to_apply_on_stats is None:
            return eredmeny
        for kulcs, ertek in bonusz_statok.all_stats.items():
            if kulcs in to_apply_on_stats:
                eredmeny.set_stat(kulcs, to_apply_on_stats[kulcs] * ertek)
        return eredmeny

    @staticmethod
    def scale_into(object_stats: "ObjectStats", alany: "ObjectStats") -> None:
        to_apply_on_stats = alany.all_stats
        if to_apply_on_stats is None:
            return
        for kulcs, ertek in object_stats.all_stats.items():
            if kulcs in to_apply_on_stats:
                to_apply_on_stats[kulcs] = to_apply_on_stats[kulcs] * ertek

    def merge_in(self, other: "ObjectStats") -> None:
        self.stats.update(other.all_stats)

    def holds_stat(self, key: ObjectStat) -> bool:
        return key in self.stats

    def drop_stat(self, stat: ObjectStat) -> None:
        self.stats.pop(stat, None)

    def copy(self) -> "ObjectStats":
        return ObjectStats(dict(self.stats))

    @staticmethod
    def as_stats(object_stats: "ObjectStats") -> "ObjectStats":
        eredmeny = ObjectStats()
        for kulcs, ertek in object_stats.all_stats.items():
            for cel in _SZETBONTAS.get(kulcs, (kulcs,)):
                eredmeny.set_stat(cel, ertek)
        return eredmeny

    @staticmethod
    def add_into(hozzaadando_statok: "ObjectStats", alany: "ObjectStats") -> None:
        to_apply_on_stats = alany.all_stats
        if to_apply_on_stats is None:
            return
        for kulcs, ertek in hozzaadando_statok.all_stats.items():
            if ObjectStat.TurnSpeed in to_apply_on_stats:
                log.error("Inside ObjectStats: contains turn_speed but not map")
            if kulcs in to_apply_on_stats:
                to_apply_on_stats[kulcs] = to_apply_on_stats[kulcs] + ertek
            elif kulcs in _STATS_ALLOWED_TO_BE_ADDED_WHEN_MISSING:
                to_apply_on_stats[kulcs] = ertek


class ShipImmutableSlot:
    def __init__(self, slot_id: int, object_point_server_hash: int, system_type: ShipSlotType,
                 rendszerkulcs_guid: int, system_level: int, fogyoeszkoz_guid: int):
        self.slot_id = slot_id
        self.object_point_server_hash = object_point_server_hash
        self.system_type = system_type
        self.system_key_guid = rendszerkulcs_guid
        self.system_level = system_level
        self.consumable_key_guid = fogyoeszkoz_guid

    @classmethod
    def from_json(cls, obj: dict) -> "ShipImmutableSlot":
        raw_type = obj.get("SystemType")
        if isinstance(raw_type, str):
            system_type = ShipSlotType[raw_type]
        elif raw_type is None:
            system_type = None
        else:
            system_type = ShipSlotType.from_code(int(raw_type))
        return cls(
            jh.as_int(obj, "SlotId"),
            jh.as_int(obj, "ObjectPointServerHash"),
            system_type,
            jh.as_long(obj, "SystemKey"),
            jh.as_long(obj, "SystemLevel"),
            jh.as_long(obj, "ConsumableKey"),
        )

    def to_wire(self, bw) -> None:
        bw.write_uint16(self.slot_id)
        bw.write_uint16(self.object_point_server_hash)
        bw.write_byte(self.system_type.value)
        bw.write_guid(self.system_key_guid)
        bw.write_uint32(self.system_level)
        bw.write_guid(self.consumable_key_guid)


class SpotInfo:
    def __init__(self, object_point_server_hash: int, object_point_name: str, spot_type: SpotKind,
                 local_position: Vector3, local_rotation: Quaternion):
        self.object_point_server_hash = object_point_server_hash
        self.object_point_name = object_point_name
        self._type = spot_type
        self.local_position = local_position
        self.local_rotation = local_rotation
        self._transform_cached = None

    @classmethod
    def from_json(cls, obj: dict) -> "SpotInfo":
        return cls(
            _read_int(obj, "objectPointServerHash", "ObjectPointServerHash"),
            _read_string(obj, "objectPointName", "ObjectPointName"),
            _read_spot_type(obj, "type", "Type"),
            _read_vector(obj, "localPosition", "LocalPosition"),
            _read_quaternion(obj, "localRotation", "LocalRotation"),
        )

    def to_wire(self, bw) -> None:
        bw.write_uint16(self.object_point_server_hash)
        bw.write_string(self.object_point_name)
        bw.write_byte(self._type.wire_code)
        bw.write_vector3(self.local_position)
        bw.write_quaternion(self.local_rotation)

    def local_transform(self) -> Transform:
        if self._transform_cached is None:
            self._transform_cached = Transform(self.local_position, self.local_rotation)
        return self._transform_cached

    def __repr__(self) -> str:
        return ("<SpotInfo " + f"object_point_server_hash={self.object_point_server_hash}, "
                f"object_point_name='{self.object_point_name}', type={self._type}, "
                f"local_position={self.local_position}, local_rotation={self.local_rotation}" + ">")

    @property
    def type(self) -> SpotKind:
        return self._type

_SZETBONTAS = {
    ObjectStat.TurnSpeed: (ObjectStat.PitchMaxSpeed, ObjectStat.YawMaxSpeed),
    ObjectStat.TurnAcceleration: (ObjectStat.PitchAcceleration, ObjectStat.YawAcceleration),
    ObjectStat.PowerPointRestore: (ObjectStat.PowerRecovery,),
}


def _read_int_value(el):
    if el is None or isinstance(el, bool):
        return None
    if isinstance(el, (int, float)):
        return int(el)
    return None


def _read_int(obj, also_kulcs, felso_kulcs) -> int:
    lower = _read_int_value(obj.get(also_kulcs))
    upper = _read_int_value(obj.get(felso_kulcs))
    if lower is not None and lower > 0:
        return lower
    if upper is not None:
        return upper
    return lower if lower is not None else 0


def _read_string_value(el):
    if el is None:
        return None
    if isinstance(el, (str, int, float, bool)):
        return str(el) if not isinstance(el, bool) else str(el).lower()
    return None


def _read_string(obj, also_kulcs, felso_kulcs):
    lower = _read_string_value(obj.get(also_kulcs))
    if lower is not None and lower.strip() != "":
        return lower
    if (upper := _read_string_value(obj.get(felso_kulcs))) is not None:
        return upper
    return lower


def _read_spot_type_value(el):
    if el is None or isinstance(el, bool):
        return None
    if isinstance(el, (int, float)):
        idx = int(el) - 1
        ertekek = list(SpotKind)
        if 0 <= idx < len(ertekek):
            return ertekek[idx]
        return None
    if isinstance(el, str):
        nyers = el
        if nyers is None or nyers.strip() == "":
            return None
        try:
            return SpotKind[nyers]
        except KeyError:
            return None
    return None


def _read_spot_type(obj, also_kulcs, felso_kulcs) -> SpotKind:
    if (lower := _read_spot_type_value(obj.get(also_kulcs))) is not None:
        return lower
    if (upper := _read_spot_type_value(obj.get(felso_kulcs))) is not None:
        return upper
    return SpotKind.Weapon


def _as_object(el):
    return el if isinstance(el, dict) else None


def _read_float(el) -> float:
    if el is None or isinstance(el, bool):
        return 0.0
    if isinstance(el, (int, float)):
        from rebsgo.helpers.floats import f32

        return f32(el)
    return 0.0


_HELY_TENGELYEK = (("x", 0.0), ("y", 0.0), ("z", 0.0))
_FORDULAT_TENGELYEK = _HELY_TENGELYEK + (("w", 1.0),)


def _tengelyek(obj, tengelyek):
    return [_read_float(obj.get(nev)) for nev, _ in tengelyek]


def _alaphelyzet(obj, tengelyek) -> bool:
    if obj is None:
        return True
    return all(ertek == nyugalom
               for ertek, (_, nyugalom) in zip(_tengelyek(obj, tengelyek), tengelyek))


def _to_vector(obj) -> Vector3:
    return Vector3(*_tengelyek(obj, _HELY_TENGELYEK))


def _to_quaternion(obj) -> Quaternion:
    return Quaternion(*_tengelyek(obj, _FORDULAT_TENGELYEK))


def _is_zero_vector(obj) -> bool:
    return _alaphelyzet(obj, _HELY_TENGELYEK)


def _is_identity_quaternion(obj) -> bool:
    return _alaphelyzet(obj, _FORDULAT_TENGELYEK)


def _read_vector(obj, also_kulcs, felso_kulcs) -> Vector3:
    lower = _as_object(obj.get(also_kulcs))
    upper = _as_object(obj.get(felso_kulcs))
    if lower is None and upper is None:
        return Vector3.zero()
    lower_vec = None if lower is None else _to_vector(lower)
    upper_vec = None if upper is None else _to_vector(upper)
    if _is_zero_vector(lower) and upper_vec is not None and not _is_zero_vector(upper):
        return upper_vec
    if lower_vec is not None:
        return lower_vec
    return upper_vec if upper_vec is not None else Vector3.zero()


def _read_quaternion(obj, also_kulcs, felso_kulcs) -> Quaternion:
    lower = _as_object(obj.get(also_kulcs))
    upper = _as_object(obj.get(felso_kulcs))
    if lower is None and upper is None:
        return Quaternion(0, 0, 0, 1)
    lower_quat = None if lower is None else _to_quaternion(lower)
    upper_quat = None if upper is None else _to_quaternion(upper)
    if _is_identity_quaternion(lower) and upper_quat is not None and not _is_identity_quaternion(upper):
        return upper_quat
    if lower_quat is not None:
        return lower_quat
    return upper_quat if upper_quat is not None else Quaternion(0, 0, 0, 1)


class SunInfo(Info):
    @classmethod
    def from_json(cls, obj: dict) -> "SunInfo":
        return cls(
            jh.as_text(obj, "name"),
            jh.get_color(obj, "raysColor"),
            jh.get_color(obj, "streakColor"),
            jh.get_color(obj, "glowColor"),
            jh.get_color(obj, "discColor"),
            jh.as_flag(obj, "occlusionFade"),
            jh.get_vector3(obj, "scale"),
            jh.get_quaternion(obj, "rotation"),
            jh.get_vector3(obj, "position"),
        )

    def __init__(self, name: str, rays_color, streak_color, glow_color, disc_color,
                 occlusion_fade: bool, scale, rotation=None, position=None):
        super().__init__(name)
        self.rays_color = rays_color
        self.streak_color = streak_color
        self.glow_color = glow_color
        self.disc_color = disc_color
        self.occlusion_fade = occlusion_fade
        self.scale = scale
        if rotation is not None:
            self.rotation = rotation
        if position is not None:
            self.position = position

    def to_wire(self, bw) -> None:
        bw.write_color(self.rays_color)
        bw.write_color(self.streak_color)
        bw.write_color(self.glow_color)
        bw.write_color(self.disc_color)
        bw.write_boolean(self.occlusion_fade)
        bw.write_quaternion(self.rotation)
        bw.write_vector3(self.position)
        bw.write_vector3(self.scale)


class FrozenPrice(Price):
    def __init__(self, buy_price: Price | None):
        super().__init__({} if buy_price is None else dict(buy_price.items()))

    def take_price(self, price: Price, count: int = 1) -> None:
        raise TypeError('this price cannot be serialized')

    def add_item(self, card_guid: int, count: int) -> None:
        raise TypeError('this price cannot be serialized')


class AreaBracket:
    def __init__(self, bracket_id: int, min_level: int, max_level: int, rewards, targyak):
        self.bracket_id = bracket_id
        self.min_level = min_level
        self.max_level = max_level
        self.rewards = rewards
        self.ship_items = targyak

    @classmethod
    def from_json(cls, obj: dict) -> "AreaBracket":
        from rebsgo.gamedata.decoding.ship_item_parser import ship_item_from_json

        raw_rewards = obj.get("Rewards")
        jutalmak = None if raw_rewards is None else [AreaRewardRank.from_json(r) for r in raw_rewards]
        raw_admission = obj.get("Admission")
        ship_items = None if raw_admission is None else [ship_item_from_json(it) for it in raw_admission]
        return cls(
            jh.as_short(obj, "BracketId"),
            jh.as_short(obj, "MinLevel"),
            jh.as_short(obj, "MaxLevel"),
            jutalmak,
            ship_items,
        )

    def to_wire(self, bw) -> None:
        from rebsgo.gamedata.ship_parts.parts import ShipItemBody

        bw.write_byte(self.bracket_id)
        bw.write_byte(self.min_level)
        bw.write_byte(self.max_level)
        bw.write_desc_array(self.rewards)
        ShipItemBody.to_wire(bw, self.ship_items)


_META_WEAPON_MAPPINGS = (
    (ObjectStat.MetaWeaponCooldown, ObjectStat.Cooldown),
    (ObjectStat.MetaWeaponPowerCost, ObjectStat.PowerPointCost),
)
_GENERIC_MISSILE_MAPPINGS = (
    (ObjectStat.MissileMaxHullPoints, ObjectStat.MaxHullPoints),
    (ObjectStat.MissileAcceleration, ObjectStat.Acceleration),
    (ObjectStat.MissileSpeed, ObjectStat.Speed),
    (ObjectStat.MissileDamageHigh, ObjectStat.DamageHigh),
    (ObjectStat.MissileDamageLow, ObjectStat.DamageLow),
    (ObjectStat.MissileCriticalOffense, ObjectStat.CriticalOffense),
    (ObjectStat.MissileArmorPiercing, ObjectStat.ArmorPiercing),
    (ObjectStat.MissileDrainHigh, ObjectStat.DrainHigh),
    (ObjectStat.MissileDrainLow, ObjectStat.DrainLow),
    (ObjectStat.MissileAvoidance, ObjectStat.Avoidance),
    (ObjectStat.MissileMaxRange, ObjectStat.MaxRange),
    (ObjectStat.MissileMinRange, ObjectStat.MinRange),
    (ObjectStat.MissileAngle, ObjectStat.Angle),
    (ObjectStat.MissilePowerPointCost, ObjectStat.PowerPointCost),
    (ObjectStat.MissileCooldown, ObjectStat.Cooldown),
    (ObjectStat.MissileLifeTime, ObjectStat.LifeTime),
)
_ACTION_STAT_MAPPINGS = {
    AbilityActionKind.FireCannon: (
        (ObjectStat.CannonAccuracy, ObjectStat.Accuracy),
        (ObjectStat.CannonDamageHigh, ObjectStat.DamageHigh),
        (ObjectStat.CannonDamageLow, ObjectStat.DamageLow),
        (ObjectStat.CannonCriticalOffense, ObjectStat.CriticalOffense),
        (ObjectStat.CannonArmorPiercing, ObjectStat.ArmorPiercing),
        (ObjectStat.CannonDrainHigh, ObjectStat.DrainHigh),
        (ObjectStat.CannonDrainLow, ObjectStat.DrainLow),
        (ObjectStat.CannonOptimalRange, ObjectStat.OptimalRange),
        (ObjectStat.CannonMaxRange, ObjectStat.MaxRange),
        (ObjectStat.CannonMinRange, ObjectStat.MinRange),
        (ObjectStat.CannonAngle, ObjectStat.Angle),
        (ObjectStat.CannonPowerPointCost, ObjectStat.PowerPointCost),
        (ObjectStat.CannonCooldown, ObjectStat.Cooldown),
    ) + _META_WEAPON_MAPPINGS,
    AbilityActionKind.FireKillCannon: (
        (ObjectStat.KillCannonAccuracy, ObjectStat.Accuracy),
        (ObjectStat.KillCannonDamageHigh, ObjectStat.DamageHigh),
        (ObjectStat.KillCannonDamageLow, ObjectStat.DamageLow),
        (ObjectStat.KillCannonCriticalOffense, ObjectStat.CriticalOffense),
        (ObjectStat.KillCannonArmorPiercing, ObjectStat.ArmorPiercing),
        (ObjectStat.KillCannonDrainHigh, ObjectStat.DrainHigh),
        (ObjectStat.KillCannonDrainLow, ObjectStat.DrainLow),
        (ObjectStat.KillCannonOptimalRange, ObjectStat.OptimalRange),
        (ObjectStat.KillCannonMaxRange, ObjectStat.MaxRange),
        (ObjectStat.KillCannonMinRange, ObjectStat.MinRange),
        (ObjectStat.KillCannonAngle, ObjectStat.Angle),
        (ObjectStat.KillCannonPowerPointCost, ObjectStat.PowerPointCost),
        (ObjectStat.KillCannonCooldown, ObjectStat.Cooldown),
    ) + _META_WEAPON_MAPPINGS,
    AbilityActionKind.FireShotgun: (
        (ObjectStat.ShotgunAccuracy, ObjectStat.Accuracy),
        (ObjectStat.ShotgunDamageHigh, ObjectStat.DamageHigh),
        (ObjectStat.ShotgunDamageLow, ObjectStat.DamageLow),
        (ObjectStat.ShotgunCriticalOffense, ObjectStat.CriticalOffense),
        (ObjectStat.ShotgunArmorPiercing, ObjectStat.ArmorPiercing),
        (ObjectStat.ShotgunDrainHigh, ObjectStat.DrainHigh),
        (ObjectStat.ShotgunDrainLow, ObjectStat.DrainLow),
        (ObjectStat.ShotgunOptimalRange, ObjectStat.OptimalRange),
        (ObjectStat.ShotgunMaxRange, ObjectStat.MaxRange),
        (ObjectStat.ShotgunMinRange, ObjectStat.MinRange),
        (ObjectStat.ShotgunAngle, ObjectStat.Angle),
        (ObjectStat.ShotgunPowerPointCost, ObjectStat.PowerPointCost),
        (ObjectStat.ShotgunCooldown, ObjectStat.Cooldown),
    ) + _META_WEAPON_MAPPINGS,
    AbilityActionKind.FireMachineGun: (
        (ObjectStat.MachineGunAccuracy, ObjectStat.Accuracy),
        (ObjectStat.MachineGunDamageHigh, ObjectStat.DamageHigh),
        (ObjectStat.MachineGunDamageLow, ObjectStat.DamageLow),
        (ObjectStat.MachineGunCriticalOffense, ObjectStat.CriticalOffense),
        (ObjectStat.MachineGunArmorPiercing, ObjectStat.ArmorPiercing),
        (ObjectStat.MachineGunDrainHigh, ObjectStat.DrainHigh),
        (ObjectStat.MachineGunDrainLow, ObjectStat.DrainLow),
        (ObjectStat.MachineGunOptimalRange, ObjectStat.OptimalRange),
        (ObjectStat.MachineGunMaxRange, ObjectStat.MaxRange),
        (ObjectStat.MachineGunMinRange, ObjectStat.MinRange),
        (ObjectStat.MachineGunAngle, ObjectStat.Angle),
        (ObjectStat.MachineGunPowerPointCost, ObjectStat.PowerPointCost),
        (ObjectStat.MachineGunCooldown, ObjectStat.Cooldown),
    ) + _META_WEAPON_MAPPINGS,
    AbilityActionKind.FireMissle: (
        (ObjectStat.MissileMaxHullPoints, ObjectStat.MaxHullPoints),
        (ObjectStat.MissileAcceleration, ObjectStat.Acceleration),
        (ObjectStat.MissileSpeed, ObjectStat.Speed),
        (ObjectStat.MissileDamageHigh, ObjectStat.DamageHigh),
        (ObjectStat.MissileDamageLow, ObjectStat.DamageLow),
        (ObjectStat.MissileCriticalOffense, ObjectStat.CriticalOffense),
        (ObjectStat.MissileArmorPiercing, ObjectStat.ArmorPiercing),
        (ObjectStat.MissileDrainHigh, ObjectStat.DrainHigh),
        (ObjectStat.MissileDrainLow, ObjectStat.DrainLow),
        (ObjectStat.MissileAvoidance, ObjectStat.Avoidance),
        (ObjectStat.MissileMaxRange, ObjectStat.MaxRange),
        (ObjectStat.MissileMinRange, ObjectStat.MinRange),
        (ObjectStat.MissileAngle, ObjectStat.Angle),
        (ObjectStat.MissilePowerPointCost, ObjectStat.PowerPointCost),
        (ObjectStat.MissileCooldown, ObjectStat.Cooldown),
        (ObjectStat.MissileLifeTime, ObjectStat.LifeTime),
    ) + _META_WEAPON_MAPPINGS,
    AbilityActionKind.FireLightMissile: (
        (ObjectStat.LightMissileMaxHullPoints, ObjectStat.MaxHullPoints),
        (ObjectStat.LightMissileAcceleration, ObjectStat.Acceleration),
        (ObjectStat.LightMissileSpeed, ObjectStat.Speed),
        (ObjectStat.LightMissileDamageHigh, ObjectStat.DamageHigh),
        (ObjectStat.LightMissileDamageLow, ObjectStat.DamageLow),
        (ObjectStat.LightMissileCriticalOffense, ObjectStat.CriticalOffense),
        (ObjectStat.LightMissileArmorPiercing, ObjectStat.ArmorPiercing),
        (ObjectStat.LightMissileDrainHigh, ObjectStat.DrainHigh),
        (ObjectStat.LightMissileDrainLow, ObjectStat.DrainLow),
        (ObjectStat.LightMissileAvoidance, ObjectStat.Avoidance),
        (ObjectStat.LightMissileMaxRange, ObjectStat.MaxRange),
        (ObjectStat.LightMissileMinRange, ObjectStat.MinRange),
        (ObjectStat.LightMissileAngle, ObjectStat.Angle),
        (ObjectStat.LightMissilePowerPointCost, ObjectStat.PowerPointCost),
        (ObjectStat.LightMissileCooldown, ObjectStat.Cooldown),
        (ObjectStat.LightMissileLifeTime, ObjectStat.LifeTime),
    ) + _GENERIC_MISSILE_MAPPINGS + _META_WEAPON_MAPPINGS,
    AbilityActionKind.FireHeavyMissile: (
        (ObjectStat.HeavyMissileMaxHullPoints, ObjectStat.MaxHullPoints),
        (ObjectStat.HeavyMissileAcceleration, ObjectStat.Acceleration),
        (ObjectStat.HeavyMissileSpeed, ObjectStat.Speed),
        (ObjectStat.HeavyMissileDamageHigh, ObjectStat.DamageHigh),
        (ObjectStat.HeavyMissileDamageLow, ObjectStat.DamageLow),
        (ObjectStat.HeavyMissileCriticalOffense, ObjectStat.CriticalOffense),
        (ObjectStat.HeavyMissileArmorPiercing, ObjectStat.ArmorPiercing),
        (ObjectStat.HeavyMissileDrainHigh, ObjectStat.DrainHigh),
        (ObjectStat.HeavyMissileDrainLow, ObjectStat.DrainLow),
        (ObjectStat.HeavyMissileAvoidance, ObjectStat.Avoidance),
        (ObjectStat.HeavyMissileMaxRange, ObjectStat.MaxRange),
        (ObjectStat.HeavyMissileMinRange, ObjectStat.MinRange),
        (ObjectStat.HeavyMissileAngle, ObjectStat.Angle),
        (ObjectStat.HeavyMissilePowerPointCost, ObjectStat.PowerPointCost),
        (ObjectStat.HeavyMissileCooldown, ObjectStat.Cooldown),
        (ObjectStat.HeavyMissileLifeTime, ObjectStat.LifeTime),
    ) + _GENERIC_MISSILE_MAPPINGS + _META_WEAPON_MAPPINGS,
    AbilityActionKind.FireTorpedo: (
        (ObjectStat.TorpedoMaxHullPoints, ObjectStat.MaxHullPoints),
        (ObjectStat.TorpedoAcceleration, ObjectStat.Acceleration),
        (ObjectStat.TorpedoSpeed, ObjectStat.Speed),
        (ObjectStat.TorpedoDamageHigh, ObjectStat.DamageHigh),
        (ObjectStat.TorpedoDamageLow, ObjectStat.DamageLow),
        (ObjectStat.TorpedoCriticalOffense, ObjectStat.CriticalOffense),
        (ObjectStat.TorpedoArmorPiercing, ObjectStat.ArmorPiercing),
        (ObjectStat.TorpedoDrainHigh, ObjectStat.DrainHigh),
        (ObjectStat.TorpedoDrainLow, ObjectStat.DrainLow),
        (ObjectStat.TorpedoAvoidance, ObjectStat.Avoidance),
        (ObjectStat.TorpedoMaxRange, ObjectStat.MaxRange),
        (ObjectStat.TorpedoMinRange, ObjectStat.MinRange),
        (ObjectStat.TorpedoAngle, ObjectStat.Angle),
        (ObjectStat.TorpedoPowerPointCost, ObjectStat.PowerPointCost),
        (ObjectStat.TorpedoCooldown, ObjectStat.Cooldown),
        (ObjectStat.TorpedoLifeTime, ObjectStat.LifeTime),
    ) + _GENERIC_MISSILE_MAPPINGS + _META_WEAPON_MAPPINGS,
    AbilityActionKind.FireMining: (
        (ObjectStat.MiningAccuracy, ObjectStat.Accuracy),
        (ObjectStat.MiningDamageHigh, ObjectStat.DamageHigh),
        (ObjectStat.MiningDamageLow, ObjectStat.DamageLow),
        (ObjectStat.MiningCriticalOffense, ObjectStat.CriticalOffense),
        (ObjectStat.MiningArmorPiercing, ObjectStat.ArmorPiercing),
        (ObjectStat.MiningOptimalRange, ObjectStat.OptimalRange),
        (ObjectStat.MiningMaxRange, ObjectStat.MaxRange),
        (ObjectStat.MiningMinRange, ObjectStat.MinRange),
        (ObjectStat.MiningAngle, ObjectStat.Angle),
        (ObjectStat.MiningPowerPointCost, ObjectStat.PowerPointCost),
        (ObjectStat.MiningCooldown, ObjectStat.Cooldown),
    ) + _META_WEAPON_MAPPINGS,
    AbilityActionKind.DropMine: (
        (ObjectStat.MineMaxHullPoints, ObjectStat.MaxHullPoints),
        (ObjectStat.MineAvoidence, ObjectStat.Avoidance),
        (ObjectStat.MineDamageHigh, ObjectStat.DamageHigh),
        (ObjectStat.MineDamageLow, ObjectStat.DamageLow),
        (ObjectStat.MineCriticalOffense, ObjectStat.CriticalOffense),
        (ObjectStat.MineArmorPiercing, ObjectStat.ArmorPiercing),
        (ObjectStat.MinePowerPointCost, ObjectStat.PowerPointCost),
        (ObjectStat.MineCooldown, ObjectStat.Cooldown),
        (ObjectStat.MineLifeTime, ObjectStat.LifeTime),
    ) + _META_WEAPON_MAPPINGS,
    AbilityActionKind.DropAntiStealthMine: (
        (ObjectStat.SmartMineMaxHullPoints, ObjectStat.MaxHullPoints),
        (ObjectStat.SmartMineMaxPowerPoints, ObjectStat.MaxPowerPoints),
        (ObjectStat.SmartMineAvoidance, ObjectStat.Avoidance),
        (ObjectStat.SmartMineArmorValue, ObjectStat.ArmorValue),
        (ObjectStat.SmartMineDamageHigh, ObjectStat.DamageHigh),
        (ObjectStat.SmartMineDamageLow, ObjectStat.DamageLow),
        (ObjectStat.SmartMineArmorPiercing, ObjectStat.ArmorPiercing),
        (ObjectStat.SmartMineCriticialOffense, ObjectStat.CriticalOffense),
        (ObjectStat.SmartMineDrainHigh, ObjectStat.DrainHigh),
        (ObjectStat.SmartMineDrainLow, ObjectStat.DrainLow),
        (ObjectStat.SmartMinePowerPointCost, ObjectStat.PowerPointCost),
        (ObjectStat.SmartMineCooldown, ObjectStat.Cooldown),
        (ObjectStat.SmartMineLifetime, ObjectStat.LifeTime),
        (ObjectStat.SmartMineMinRange, ObjectStat.MinRange),
        (ObjectStat.SmartMineMaxRange, ObjectStat.MaxRange),
    ) + _META_WEAPON_MAPPINGS,
    AbilityActionKind.ToggleStealth: (
        (ObjectStat.ToggleSystemPowerPointCost, ObjectStat.PowerPointCost),
        (ObjectStat.ToggleSystemCooldown, ObjectStat.Cooldown),
        (ObjectStat.ToggleSystemPowerCostPerSec, ObjectStat.PpCostPerSec),
    ),
    AbilityActionKind.ToggleSystem: (
        (ObjectStat.ToggleSystemPowerPointCost, ObjectStat.PowerPointCost),
        (ObjectStat.ToggleSystemCooldown, ObjectStat.Cooldown),
        (ObjectStat.ToggleSystemPowerCostPerSec, ObjectStat.PpCostPerSec),
    ),
}
_ACTION_STAT_MAPPINGS[AbilityActionKind.Flak] = _ACTION_STAT_MAPPINGS[AbilityActionKind.FireCannon]
_ACTION_STAT_MAPPINGS[AbilityActionKind.PointDefence] = _ACTION_STAT_MAPPINGS[AbilityActionKind.FireCannon]


def get_action_stat_mappings(action_type):
    return _ACTION_STAT_MAPPINGS.get(action_type, ())


def apply_action_stat_multipliers(action_type, szorzok: ObjectStats, target_stats: ObjectStats) -> None:
    ObjectStats.scale_into(szorzok, target_stats)
    for source_stat, target_stat in get_action_stat_mappings(action_type):
        if not szorzok.holds_stat(source_stat) or not target_stats.holds_stat(target_stat):
            continue
        target_stats.set_stat(target_stat, target_stats.stat(target_stat) * szorzok.stat(source_stat))
