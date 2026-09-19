# github.com/Shran21

from __future__ import annotations

import logging
from rebsgo.gamedata.from_json.game_data_loader import GameDataLoader
from rebsgo.gamedata.reading import ObjectStat
from rebsgo import paths
from rebsgo.vocabulary.pilot import Faction


log = logging.getLogger(__name__)


class NpcGrade:
    def __init__(self, min_owner_level: int, stat_overrides: dict):
        self._min_owner_level = min_owner_level
        self._stat_overrides = stat_overrides

    @property
    def min_owner_level(self) -> int:
        return self._min_owner_level

    @property
    def stat_overrides(self) -> dict:
        return self._stat_overrides


class NpcStatTemplates:
    def __init__(self, by_ship_guid: dict):
        self._by_ship_guid = by_ship_guid

    def overrides_for(self, ship_guid: int, owner_level: int) -> dict:
        grades = self._by_ship_guid.get(ship_guid)
        if not grades:
            return {}
        for grade in grades:
            if owner_level >= grade.min_owner_level:
                return grade.stat_overrides
        return {}

    @property
    def empty(self) -> bool:
        return not self._by_ship_guid


class NpcStatTemplateReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Npc")

    def fetch(self) -> NpcStatTemplates:
        by_ship_guid: dict = {}
        for utvonal in self.file_paths():
            try:
                obj = self.read_json(utvonal)
            except Exception:
                log.exception("Failed to parse NPC template %s", utvonal)
                continue
            if obj is None:
                continue
            for bejegyzes in obj.get("npcs", []):
                ship_guid = int(bejegyzes["shipGuid"])
                grades = []
                for g in bejegyzes.get("grades", []):
                    overrides = {}
                    for stat_name, ertek in (g.get("stats") or {}).items():
                        try:
                            overrides[ObjectStat[stat_name]] = float(ertek)
                        except KeyError:
                            log.warning("NPC template: unknown stat '%s' for ship %s", stat_name, ship_guid)
                    grades.append(NpcGrade(int(g.get("minOwnerLevel", 0)), overrides))
                grades.sort(key=lambda gr: gr.min_owner_level, reverse=True)
                by_ship_guid.setdefault(ship_guid, []).extend(grades)
        for guid in by_ship_guid:
            by_ship_guid[guid].sort(key=lambda gr: gr.min_owner_level, reverse=True)
        log.info("Loaded NPC stat templates for %s base ships", len(by_ship_guid))
        return NpcStatTemplates(by_ship_guid)

log = logging.getLogger(__name__)


class OutpostBeaconFactionConfig:
    def __init__(self, card_guid: int, angle_degrees: float):
        self.card_guid = card_guid
        self.angle_degrees = angle_degrees


class OutpostBeaconConfig:
    def __init__(self, min_readiness: float, spawn_radius: float, arrival_radius: float,
                 vertical_offset: float, beacons_by_faction,
                 respawn_delay_seconds: float = 0.0):
        self.min_readiness = min_readiness
        self.spawn_radius = spawn_radius
        self.arrival_radius = arrival_radius
        self.vertical_offset = vertical_offset
        self.respawn_delay_seconds = respawn_delay_seconds
        self.beacons_by_faction = beacons_by_faction

    @property
    def empty(self) -> bool:
        return not self.beacons_by_faction


class OutpostBeaconTemplateReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Outpost")

    def fetch(self) -> OutpostBeaconConfig:
        for utvonal in self.file_paths():
            if utvonal.name != "beacons.json":
                continue
            obj = self.read_json(utvonal)
            if obj is None:
                continue
            beacons = {}
            for fac_name, ertek in obj.get("beacons", {}).items():
                beacons[Faction[fac_name]] = OutpostBeaconFactionConfig(
                    int(ertek["cardGuid"]),
                    float(ertek.get("angleDegrees", 0.0)))
            cfg = OutpostBeaconConfig(
                float(obj.get("minReadiness", 150.0)),
                float(obj.get("spawnRadius", 600.0)),
                float(obj.get("arrivalRadius", 800.0)),
                float(obj.get("verticalOffset", 300.0)),
                beacons,
                float(obj.get("respawnDelaySeconds", 0.0)))
            log.info("Loaded outpost beacon config: %s factions, min readiness %s%%, spawn radius %s, "
                     "arrival radius %s",
                     len(beacons), cfg.min_readiness, cfg.spawn_radius, cfg.arrival_radius)
            return cfg
        log.warning("No OutpostTemplates/beacons.json found; outpost jump beacons disabled")
        return OutpostBeaconConfig(150.0, 600.0, 800.0, 300.0, {})

log = logging.getLogger(__name__)


class OutpostPlatformConfig:
    def __init__(self, respawn_delay_seconds: int, tiers, platforms_by_faction,
                 hull_recovery_percent_per_sec: float = 0.0):
        self.respawn_delay_seconds = respawn_delay_seconds
        self.tiers = tiers
        self.platforms_by_faction = platforms_by_faction
        self.hull_recovery_percent_per_sec = hull_recovery_percent_per_sec

    @property
    def empty(self) -> bool:
        return not self.tiers or not self.platforms_by_faction


class OutpostPlatformTemplateReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Outpost")

    def fetch(self) -> OutpostPlatformConfig:
        for utvonal in self.file_paths():
            if utvonal.name != "platforms.json":
                continue
            obj = self.read_json(utvonal)
            if obj is None:
                continue
            tiers = []
            for t in obj.get("tiers", []):
                tiers.append((t["name"], float(t["minReadiness"]), int(t["count"]), float(t["radius"])))
            tiers.sort(key=lambda x: x[1])
            platforms = {}
            for fac_name, by_tier in obj.get("platforms", {}).items():
                platforms[Faction[fac_name]] = {k: int(v) for k, v in by_tier.items()}
            cfg = OutpostPlatformConfig(int(obj.get("respawnDelaySeconds", 480)), tiers, platforms,
                                        float(obj.get("hullRecoveryPercentPerSec", 0.0)))
            log.info("Loaded outpost platform config: %s tiers, respawn delay %ss",
                     len(tiers), cfg.respawn_delay_seconds)
            return cfg
        log.warning("No OutpostTemplates/platforms.json found; outpost platforms disabled")
        return OutpostPlatformConfig(480, [], {})


class DebrisCardPools:
    def __init__(self, piles, wrecks, fragments, walls, cargo: int):
        self.piles = tuple(piles)
        self.wrecks = tuple(wrecks)
        self.fragments = tuple(fragments)
        self.walls = tuple(walls)
        self.cargo = cargo

    @property
    def empty(self) -> bool:
        return not (self.piles or self.wrecks or self.fragments or self.walls)


class DebrisCardTemplateReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Debris")

    def fetch(self) -> DebrisCardPools:
        for utvonal in self.file_paths():
            if utvonal.name != "debris_cards.json":
                continue
            obj = self.read_json(utvonal)
            if obj is None:
                continue

            def keszlet(nev):
                return [int(g) for g in (obj.get(nev) or {}).get("guids", [])]

            keszletek = DebrisCardPools(
                keszlet("piles"), keszlet("wrecks"), keszlet("fragments"), keszlet("walls"),
                int((obj.get("cargo") or {}).get("guid", 0)))
            log.info("Loaded debris card pools: %s piles, %s wrecks, %s fragments, %s walls",
                     len(keszletek.piles), len(keszletek.wrecks),
                     len(keszletek.fragments), len(keszletek.walls))
            return keszletek
        log.warning("No Debris/debris_cards.json found; debris fields have nothing to build from")
        return DebrisCardPools((), (), (), (), 0)


_debris_card_pools = None


def debris_card_pools() -> DebrisCardPools:
    global _debris_card_pools
    if _debris_card_pools is None:
        _debris_card_pools = DebrisCardTemplateReader().fetch()
    return _debris_card_pools


class ClaimRules:
    def __init__(self, obj: dict):
        self.pvp_hold_ms = int(obj.get("pvpHoldSeconds", 20)) * 1000
        self.pvp_damage_share = float(obj.get("pvpDamageShare", 0.1))
        self.asteroid_hold_seconds = int(obj.get("asteroidHoldSeconds", 45))
        self.default_hold_seconds = int(obj.get("defaultHoldSeconds", 60))
        self.solo_share_threshold = float(obj.get("soloShareThreshold", 0.6))
        self.cargo_loot_seconds = int(obj.get("cargoLootSeconds", 5))


class ClaimRulesTemplateReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Spoils")

    def fetch(self) -> ClaimRules:
        for utvonal in self.file_paths():
            if utvonal.name != "claim_rules.json":
                continue
            if (obj := self.read_json(utvonal)) is not None:
                szabalyok = ClaimRules(obj)
                log.info("Loaded loot claim rules: pvp %ss, asteroid %ss, default %ss",
                         szabalyok.pvp_hold_ms // 1000, szabalyok.asteroid_hold_seconds,
                         szabalyok.default_hold_seconds)
                return szabalyok
        log.warning("No Spoils/claim_rules.json found; falling back to the shipped holds")
        return ClaimRules({})


_claim_rules = None


def claim_rules() -> ClaimRules:
    global _claim_rules
    if _claim_rules is None:
        _claim_rules = ClaimRulesTemplateReader().fetch()
    return _claim_rules


class MineTuning:
    def __init__(self, obj: dict):
        fejek = obj.get("warheads") or {}
        self.warheads = {nev: (int(par.get("single", 0)), int(par.get("field", 0)))
                         for nev, par in fejek.items()}
        self.field_from_tier = int(obj.get("fieldFromTier", 3))
        self.blast_radius = float(obj.get("blastRadius", 350.0))
        self.trigger_radius = float(obj.get("triggerRadius", 150.0))
        nuklearis = obj.get("nuclear") or {}
        self.hull_multiplier = float(nuklearis.get("hullMultiplier", 2.5))
        self.damage_multiplier = float(nuklearis.get("damageMultiplier", 1.8))
        self.fallback_life_seconds = float(obj.get("fallbackLifeTimeSeconds", 120.0))

    def guid_for(self, warhead: str, launcher_tier: int) -> int:
        single, field = self.warheads.get(warhead) or self.warheads.get("he", (0, 0))
        return field if launcher_tier >= self.field_from_tier else single


class MineTemplateReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Weapons")

    def fetch(self) -> MineTuning:
        for utvonal in self.file_paths():
            if utvonal.name != "mines.json":
                continue
            if (obj := self.read_json(utvonal)) is not None:
                hangolas = MineTuning(obj)
                log.info("Loaded mine tuning: %s warheads, blast radius %s",
                         len(hangolas.warheads), hangolas.blast_radius)
                return hangolas
        log.warning("No Weapons/mines.json found; mines fall back to the shipped figures")
        return MineTuning({})


_mine_tuning = None


def mine_tuning() -> MineTuning:
    global _mine_tuning
    if _mine_tuning is None:
        _mine_tuning = MineTemplateReader().fetch()
    return _mine_tuning


class CapitalRules:
    def __init__(self, obj: dict):
        hajok = obj.get("ships") or {}
        self.ship_by_faction = {nev: int(g) for nev, g in hajok.items()}
        self.hangar_slot = int(obj.get("hangarSlot", 12))
        self.command_seconds = float(obj.get("commandSeconds", 3600.0))
        self.sector_by_faction = {nev: int(s) for nev, s
                                  in (obj.get("defendedSector") or {}).items()}
        self.default_ammo = {int(k): int(v) for k, v
                             in (obj.get("defaultAmmo") or {}).items() if k.isdigit()}
        self.ammo_counts = {int(k): int(v) for k, v
                            in (obj.get("ammoCounts") or {}).items() if k.isdigit()}

    def ship_guid(self, faction) -> int:
        return self.ship_by_faction.get(getattr(faction, "name", None), 0)

    def is_capital(self, guid: int) -> bool:
        return guid in self.ship_by_faction.values()

    def defended_sector(self, faction, ha_nincs: int = -1) -> int:
        return self.sector_by_faction.get(getattr(faction, "name", None), ha_nincs)


class CapitalTemplateReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Capital")

    def fetch(self) -> CapitalRules:
        for utvonal in self.file_paths():
            if utvonal.name != "capital_ships.json":
                continue
            if (obj := self.read_json(utvonal)) is not None:
                szabalyok = CapitalRules(obj)
                log.info("Loaded capital rules: %s ships, command %ss, slot %s",
                         len(szabalyok.ship_by_faction), int(szabalyok.command_seconds),
                         szabalyok.hangar_slot)
                return szabalyok
        log.warning("No Capital/capital_ships.json found; capitals fall back to the shipped figures")
        return CapitalRules({})


_capital_rules = None


def capital_rules() -> CapitalRules:
    global _capital_rules
    if _capital_rules is None:
        _capital_rules = CapitalTemplateReader().fetch()
    return _capital_rules


class SectorPolicy:
    def __init__(self, obj: dict):
        self.disabled = frozenset(int(x) for x in obj.get("disabledSectors") or [])
        self.player_limits = {int(k): int(v)
                              for k, v in (obj.get("playerLimits") or {}).items()
                              if int(v) > 0}

    def is_disabled(self, sector_id) -> bool:
        return int(sector_id) in self.disabled

    def player_limit(self, sector_id):
        return self.player_limits.get(int(sector_id))


class SectorPolicyTemplateReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "World")

    def fetch(self) -> SectorPolicy:
        for utvonal in self.file_paths():
            if utvonal.name != "sector_policy.json":
                continue
            if (obj := self.read_json(utvonal)) is not None:
                policy = SectorPolicy(obj)
                log.info("Loaded sector policy: %s closed, %s limited",
                         len(policy.disabled), len(policy.player_limits))
                return policy
        return SectorPolicy({})


_sector_policy = None


def sector_policy() -> SectorPolicy:
    global _sector_policy
    if _sector_policy is None:
        _sector_policy = SectorPolicyTemplateReader().fetch()
    return _sector_policy


def reload_sector_policy() -> SectorPolicy:
    global _sector_policy
    _sector_policy = SectorPolicyTemplateReader().fetch()
    return _sector_policy


class WorldPlaces:
    def __init__(self, obj: dict):
        self.home_by_faction = {nev: int(s) for nev, s
                                in (obj.get("homeStations") or {}).items()}
        self.starting_outposts = {
            int(sid): (sor.get("faction"), int(sor.get("points", 0)))
            for sid, sor in (obj.get("startingOutposts") or {}).items() if sid.isdigit()}
        self.outpost_growth_seconds = int(obj.get("outpostGrowthSeconds", 3600))

    @property
    def home_sectors(self) -> frozenset:
        return frozenset(self.home_by_faction.values())

    def is_home_station(self, sector_id: int) -> bool:
        return sector_id in self.home_sectors

    def starting_points(self, sector_id: int, faction_name: str) -> int:
        birtokos, pontok = self.starting_outposts.get(sector_id, (None, 0))
        return pontok if birtokos == faction_name else 0


class WorldPlacesTemplateReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "World")

    def fetch(self) -> WorldPlaces:
        for utvonal in self.file_paths():
            if utvonal.name != "home_sectors.json":
                continue
            if (obj := self.read_json(utvonal)) is not None:
                helyek = WorldPlaces(obj)
                log.info("Loaded world places: home sectors %s, %s starting outposts",
                         sorted(helyek.home_sectors), len(helyek.starting_outposts))
                return helyek
        log.warning("No World/home_sectors.json found; no sector counts as home")
        return WorldPlaces({})


_world_places = None


def world_places() -> WorldPlaces:
    global _world_places
    if _world_places is None:
        _world_places = WorldPlacesTemplateReader().fetch()
    return _world_places


class DroneHullTemplateReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "World")

    def fetch(self) -> frozenset:
        for utvonal in self.file_paths():
            if utvonal.name != "drone_hulls.json":
                continue
            if (obj := self.read_json(utvonal)) is not None:
                kulcsok = frozenset(int(k) for k in obj.get("objectKeys", []))
                log.info("Loaded drone hull keys: %s", len(kulcsok))
                return kulcsok
        log.warning("No World/drone_hulls.json found; drone cards are left as they ship")
        return frozenset()


_drone_hull_keys = None


def drone_hull_keys() -> frozenset:
    global _drone_hull_keys
    if _drone_hull_keys is None:
        _drone_hull_keys = DroneHullTemplateReader().fetch()
    return _drone_hull_keys


class ArenaTemplateReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Arena")

    def fetch(self) -> dict:
        for utvonal in self.file_paths():
            if utvonal.name != "arena.json":
                continue
            if (obj := self.read_json(utvonal)) is not None:
                terms = {k: v for k, v in obj.items() if not k.startswith("_")}
                log.info("Loaded arena terms: sector %s, duel %ss",
                         terms.get("arenaSectorId"), terms.get("duelDurationSeconds"))
                return terms
        log.warning("No Arena/arena.json found; the shipped arena terms stand in")
        return {}


_arena_terms = None


def arena_terms() -> dict:
    global _arena_terms
    if _arena_terms is None:
        _arena_terms = ArenaTemplateReader().fetch()
    return _arena_terms


class RankingCounterMapReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Ranking")

    def fetch(self) -> dict:
        from rebsgo.pilots.standings.score_columns import Ranglista

        for utvonal in self.file_paths():
            if utvonal.name != "counter_map.json":
                continue
            if (obj := self.read_json(utvonal)) is None:
                continue
            listak = {}
            for kulcs, leiras in (obj.get("groups") or {}).items():
                try:
                    listak[int(kulcs)] = Ranglista.from_json(leiras)
                except Exception:
                    log.exception("leaderboard %s could not be read", kulcs)
            log.info("Loaded ranking columns: %s boards", len(listak))
            return listak
        log.warning("No Ranking/counter_map.json found; the leaderboards stay empty")
        return {}


class MedalBandReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Ranking")

    def fetch(self) -> dict:
        from rebsgo.pilots.standings.medal_desk import CSATORNAK, _csatornat_olvas

        for utvonal in self.file_paths():
            if utvonal.name != "medals.json":
                continue
            if (obj := self.read_json(utvonal)) is None:
                continue
            csatornak = {}
            for kulcs, _mezo, enum_osztaly in CSATORNAK:
                if (leiras := obj.get(kulcs)) is not None:
                    csatornak[kulcs] = _csatornat_olvas(leiras, enum_osztaly)
            log.info("Loaded medal bands: %s channels", len(csatornak))
            return csatornak
        log.warning("No Ranking/medals.json found; nobody wears a badge")
        return {}


class ArenaPointsReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Ranking")

    def fetch(self) -> dict:
        for utvonal in self.file_paths():
            if utvonal.name != "arena_points.json":
                continue
            if (obj := self.read_json(utvonal)) is None:
                continue
            return {
                "role_columns": {str(k): int(v) for k, v in (obj.get("role_columns") or {}).items()},
                "arena_1x1": [int(g) for g in obj.get("arena_1x1", [])],
                "arena_3x3": [int(g) for g in obj.get("arena_3x3", [])],
                "winPoints": float(obj.get("winPoints", 0)),
                "lossPoints": float(obj.get("lossPoints", 0)),
            }
        log.warning("No Ranking/arena_points.json found; the arena ladders stay empty")
        return {}


class InterdictionCounterReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Ranking")

    def fetch(self) -> dict:
        for utvonal in self.file_paths():
            if utvonal.name != "interdiction.json":
                continue
            if (obj := self.read_json(utvonal)) is None:
                continue
            return {
                "rank_counters": {str(k): int(v) for k, v in (obj.get("rank_counters") or {}).items()},
                "dynamic_counters": {str(k): int(v)
                                     for k, v in (obj.get("dynamic_counters") or {}).items()},
            }
        return {"rank_counters": {}, "dynamic_counters": {}}


class TournamentBoardReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Ranking")

    def fetch(self) -> tuple:
        from rebsgo.pilots.standings.score_columns import Ranglista

        for utvonal in self.file_paths():
            if utvonal.name != "tournament.json":
                continue
            if (obj := self.read_json(utvonal)) is None:
                continue
            listak = {}
            for kulcs, leiras in (obj.get("groups") or {}).items():
                try:
                    listak[int(kulcs)] = Ranglista.from_json(leiras)
                except Exception:
                    log.exception("tournament class %s could not be read", kulcs)
            honapok = max(1, int(obj.get("seasonMonths", 1)))
            log.info("Loaded tournament ladder: %s classes, %s-month seasons",
                     len(listak), honapok)
            return listak, honapok
        log.warning("No Ranking/tournament.json found; the tournament ladder stays empty")
        return {}, 1


class SectorEventTerms:
    def __init__(self, obj: dict):
        self.trigger_radius = float(obj.get("triggerRadius", 2500.0))
        self.arm_timeout_seconds = int(obj.get("armTimeoutSeconds", 600))
        self.whois_sync_ms = int(obj.get("whoisSyncMs", 5000))
        self.announce_interval_ms = int(obj.get("announceIntervalMs", 45000))
        self.announce_min_damage = int(obj.get("announceMinDamage", 200))


class SectorEventTemplateReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "World")

    def fetch(self) -> SectorEventTerms:
        for utvonal in self.file_paths():
            if utvonal.name != "sector_events.json":
                continue
            if (obj := self.read_json(utvonal)) is not None:
                terms = SectorEventTerms(obj)
                log.info("Loaded sector event terms: radius %s, arm timeout %ss",
                         terms.trigger_radius, terms.arm_timeout_seconds)
                return terms
        log.warning("No World/sector_events.json found; the shipped event terms stand in")
        return SectorEventTerms({})


_sector_event_terms = None


def sector_event_terms() -> SectorEventTerms:
    global _sector_event_terms
    if _sector_event_terms is None:
        _sector_event_terms = SectorEventTemplateReader().fetch()
    return _sector_event_terms


class ReadinessTerms:
    def __init__(self, obj: dict):
        self.base_percent_per_minute = float(obj.get("basePercentPerMinute", 1.0))
        self.per_extra_pilot = float(obj.get("perExtraPilot", 0.05))
        self.points_per_percent = float(obj.get("pointsPerPercent", 9.0))


class ReadinessTemplateReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Outpost")

    def fetch(self) -> ReadinessTerms:
        for utvonal in self.file_paths():
            if utvonal.name != "readiness.json":
                continue
            if (obj := self.read_json(utvonal)) is not None:
                terms = ReadinessTerms(obj)
                log.info("Loaded outpost readiness: %s%%/min base, %s points per percent",
                         terms.base_percent_per_minute, terms.points_per_percent)
                return terms
        log.warning("No Outpost/readiness.json found; the shipped readiness rates stand in")
        return ReadinessTerms({})


_readiness_terms = None


def readiness_terms() -> ReadinessTerms:
    global _readiness_terms
    if _readiness_terms is None:
        _readiness_terms = ReadinessTemplateReader().fetch()
    return _readiness_terms


class ShopWeaponKeys:
    def __init__(self, obj: dict):
        self.capital_prefix = str(obj.get("capitalPrefix", "ability_capship_"))
        self.carrier_prefix = str(obj.get("carrierPrefix", "item_slot_capital_system_"))
        self.stealth_prefix = str(obj.get(
            "stealthPrefix", "item_slot_strike_stealth_weapon_system_"))


class ShopWeaponKeyReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Shop")

    def fetch(self) -> ShopWeaponKeys:
        for utvonal in self.file_paths():
            if utvonal.name != "weapon_keys.json":
                continue
            if (obj := self.read_json(utvonal)) is not None:
                return ShopWeaponKeys(obj)
        log.warning("No Shop/weapon_keys.json found; the shipped weapon prefixes stand in")
        return ShopWeaponKeys({})


_shop_weapon_keys = None


def shop_weapon_keys() -> ShopWeaponKeys:
    global _shop_weapon_keys
    if _shop_weapon_keys is None:
        _shop_weapon_keys = ShopWeaponKeyReader().fetch()
    return _shop_weapon_keys


def _fajtakra(nevek, enum_osztaly, honnan: str) -> frozenset:
    tagok = []
    for nev in nevek or ():
        tag = getattr(enum_osztaly, str(nev), None)
        if tag is None:
            raise ValueError(f"{honnan}: {enum_osztaly.__name__} has no '{nev}'")
        tagok.append(tag)
    return frozenset(tagok)


class SectorRules:
    def __init__(self, obj: dict, object_kind, ability_kind):
        utkozes = obj.get("collision") or {}
        kepessegek = obj.get("npcAbilities") or {}
        self.pass_through_planetoid = _fajtakra(
            utkozes.get("passThroughPlanetoid"), object_kind, "rules.json/passThroughPlanetoid")
        self.same_kind_pass_through = _fajtakra(
            utkozes.get("sameKindPassThrough"), object_kind, "rules.json/sameKindPassThrough")
        self.npc_self_abilities = _fajtakra(
            kepessegek.get("onSelf"), ability_kind, "rules.json/onSelf")
        self.npc_enemy_abilities = _fajtakra(
            kepessegek.get("onEnemy"), ability_kind, "rules.json/onEnemy")


class SectorRulesReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "World")

    def fetch(self, object_kind, ability_kind) -> SectorRules:
        for utvonal in self.file_paths():
            if utvonal.name != "rules.json":
                continue
            if (obj := self.read_json(utvonal)) is not None:
                szabalyok = SectorRules(obj, object_kind, ability_kind)
                log.info("Loaded sector rules: %s pass a planetoid, %s NPC self-abilities",
                         len(szabalyok.pass_through_planetoid), len(szabalyok.npc_self_abilities))
                return szabalyok
        log.warning("No World/rules.json found; the shipped collision and NPC rules stand in")
        return SectorRules({}, object_kind, ability_kind)


_sector_rules = None


def sector_rules(object_kind, ability_kind) -> SectorRules:
    global _sector_rules
    if _sector_rules is None:
        _sector_rules = SectorRulesReader().fetch(object_kind, ability_kind)
    return _sector_rules


class WorldTimers:
    def __init__(self, obj: dict):
        parti = obj.get("party") or {}
        allomas = obj.get("station") or {}
        szektor = obj.get("sector") or {}
        letapogatas = obj.get("scanning") or {}
        kepessegek = obj.get("abilities") or {}
        hordozo = obj.get("carrier") or {}

        self.party_max_size = int(parti.get("maxSize", 10))
        self.repair_undock_block_seconds = int(allomas.get("repairUndockBlockSeconds", 30))
        self.reserved_slot_minutes = int(szektor.get("reservedSlotMinutes", 15))
        self.arrival_attempts = int(szektor.get("arrivalAttempts", 64))
        self.arrival_reservation_seconds = float(szektor.get("arrivalReservationSeconds", 30.0))
        self.arrival_obstacle_buffer = float(szektor.get("arrivalObstacleBuffer", 75.0))
        self.visibility_retry_ms = int(szektor.get("visibilityRetryMs", 10000))
        self.dradis_contact_seconds = float(letapogatas.get("dradisContactSeconds", 60.0))
        self.buff_range_tolerance = float(kepessegek.get("buffRangeTolerance", 300.0))
        self.toggle_modifier_seconds = float(kepessegek.get("toggleModifierSeconds", 604800.0))
        self.upkeep_min_interval_seconds = float(kepessegek.get("upkeepMinIntervalSeconds", 1.0))
        self.carrier_release_min_distance = float(hordozo.get("releaseMinDistance", 300.0))
        self.carrier_release_max_distance = float(hordozo.get("releaseMaxDistance", 500.0))


class WorldTimerReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "World")

    def fetch(self) -> WorldTimers:
        for utvonal in self.file_paths():
            if utvonal.name != "timers.json":
                continue
            if (obj := self.read_json(utvonal)) is not None:
                return WorldTimers(obj)
        log.warning("No World/timers.json found; the shipped waits and limits stand in")
        return WorldTimers({})


_world_timers = None


def world_timers() -> WorldTimers:
    global _world_timers
    if _world_timers is None:
        _world_timers = WorldTimerReader().fetch()
    return _world_timers


class ModuleBindings:
    def __init__(self, obj: dict, ability_kind):
        self._csaladok = {}
        for csalad in ("turret", "missile"):
            blokk = obj.get(csalad) or {}
            self._csaladok[csalad] = (
                _fajtakra(blokk.get("actions"), ability_kind,
                          f"module_bindings.json/{csalad}.actions"),
                {int(tier): int(guid) for tier, guid in (blokk.get("byTier") or {}).items()},
            )
        self.capital_tier = int(obj.get("capitalTier", 4))

    def guid_for(self, action_kind, tier: int) -> int:
        for akciok, tierenkent in self._csaladok.values():
            if action_kind in akciok:
                return tierenkent.get(tier, 0)
        return 0

    def capital_guids(self) -> tuple:
        return tuple(tierenkent.get(self.capital_tier, 0)
                     for _, tierenkent in self._csaladok.values())


class ModuleBindingReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Modules")

    def fetch(self, ability_kind) -> ModuleBindings:
        for utvonal in self.file_paths():
            if utvonal.name != "module_bindings.json":
                continue
            if (obj := self.read_json(utvonal)) is not None:
                kotesek = ModuleBindings(obj, ability_kind)
                log.info("Loaded module bindings: capitals show tier %s", kotesek.capital_tier)
                return kotesek
        log.warning("No Modules/module_bindings.json found; ships will show no weapon models")
        return ModuleBindings({}, ability_kind)


_module_bindings = None


def module_bindings(ability_kind) -> ModuleBindings:
    global _module_bindings
    if _module_bindings is None:
        _module_bindings = ModuleBindingReader().fetch(ability_kind)
    return _module_bindings
