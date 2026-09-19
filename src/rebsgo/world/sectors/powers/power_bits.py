# github.com/Shran21

from __future__ import annotations

from rebsgo.world.sectors.powers.deeds import Deed, Elsutes, PaintDeed, TransponderDeed, BoonDeed, BaneDeed, JamMissileDeed, FlareDeed, MineDeed, TailDeed, FortifyDeed, CannonDeed, RepeaterDeed, ShotgunDeed, MiningBeamDeed, MissileDeed, FlakDeed, PointDefenceDeed, SurveyDeed, MendDeed, ShrapnelDeed, is_shrapnel_burst_slot, SlideDeed, ShortCircuitDeed, StealthDeed, ToggleDeed
from rebsgo.gamedata.reading import AbilityActionKind


class CastOrder:
    def __init__(self, caster, ability_id, fired_automatically, *target_ids):
        if caster is None:
            raise TypeError('the ability points at a ship that is absent')
        if len(target_ids) == 1 and isinstance(target_ids[0], (set, frozenset)):
            target_id_list = list(target_ids[0])
        else:
            if len(target_ids) == 1 and isinstance(target_ids[0], (list, tuple)):
                target_id_list = list(target_ids[0])
            else:
                target_id_list = list(target_ids)
            if CastOrder._contains_duplicate_entry(target_id_list):
                raise ValueError('target list repeats an entry')
        self._casting_ship = caster
        self._ability_id = ability_id
        self._target_ids = target_id_list
        self._is_auto_cast_ability = fired_automatically
        self._enqueued_ms = None

    @staticmethod
    def _contains_duplicate_entry(target_ids) -> bool:
        return len(target_ids) > 1 and len(set(target_ids)) != len(target_ids)

    @property
    def ability_id(self) -> int:
        return self._ability_id

    @property
    def target_ids(self):
        return self._target_ids

    @property
    def fired_automatically(self) -> bool:
        return self._is_auto_cast_ability

    @property
    def casting_ship(self):
        return self._casting_ship

    def mark_enqueued(self, enqueued_ms: float) -> None:
        self._enqueued_ms = enqueued_ms

    def mark_enqueued_if_missing(self, enqueued_ms: float) -> None:
        if self._enqueued_ms is None:
            self._enqueued_ms = enqueued_ms

    @property
    def enqueued_ms(self):
        return self._enqueued_ms

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        if self._ability_id != other._ability_id:
            return False
        return self._casting_ship == other._casting_ship

    def __hash__(self) -> int:
        return hash((self._casting_ship, self._ability_id))

    @staticmethod
    def key_for(object_id: int, ability_id: int) -> int:
        szam = ability_id
        szam <<= 32
        return szam + object_id


class DeedSource:
    def __init__(self, ctx, engagement, damage_book, arrival_gate, loot_ownership,
                 cast_desk=None):
        self._ctx = ctx
        self._engagement = engagement
        self._damage_book = damage_book
        self._join_queue = arrival_gate
        self._loot_ownership = loot_ownership
        self._cast_desk = cast_desk

    DEEDS = {
        AbilityActionKind.Slide: (SlideDeed, ()),
        AbilityActionKind.Buff: (BoonDeed, ()),
        AbilityActionKind.Fortify: (FortifyDeed, ()),
        AbilityActionKind.Debuff: (BaneDeed, ("kepletek",)),
        AbilityActionKind.ActivatePaintTheTarget: (PaintDeed, ("kepletek",)),
        AbilityActionKind.ActivateJumpTargetTransponder:
            (TransponderDeed, ("belepteto",)),
        AbilityActionKind.DropFlare: (FlareDeed, ("kepletek",)),
        AbilityActionKind.DropMine: (MineDeed, ("belepteto",)),
        AbilityActionKind.DropAntiStealthMine: (MineDeed, ("belepteto",)),
        AbilityActionKind.DeflectMissile: (JamMissileDeed, ()),
        AbilityActionKind.ShortCircuit: (ShortCircuitDeed, ("kepletek",)),
        AbilityActionKind.ResourceScan: (SurveyDeed, ("zsakmany",)),
        AbilityActionKind.RestoreBuff: (MendDeed, ()),
        AbilityActionKind.Follow: (TailDeed, ()),
        AbilityActionKind.FireMissle: (MissileDeed, ("kepletek", "sebzes", "belepteto", "sor")),
        AbilityActionKind.FireTorpedo: (MissileDeed, ("kepletek", "sebzes", "belepteto", "sor")),
        AbilityActionKind.FireLightMissile: (MissileDeed, ("kepletek", "sebzes", "belepteto", "sor")),
        AbilityActionKind.FireHeavyMissile: (MissileDeed, ("kepletek", "sebzes", "belepteto", "sor")),
        AbilityActionKind.FireCannon: (CannonDeed, ("kepletek", "sebzes", "sor")),
        AbilityActionKind.FireKillCannon: (CannonDeed, ("kepletek", "sebzes", "sor")),
        AbilityActionKind.FireShotgun: (ShotgunDeed, ("kepletek", "sebzes", "sor")),
        AbilityActionKind.FireMachineGun: (RepeaterDeed, ("kepletek", "sebzes", "sor")),
        AbilityActionKind.ToggleStealth: (StealthDeed, ("sor",)),
        AbilityActionKind.ToggleSystem: (ToggleDeed, ()),
        AbilityActionKind.FireMining: (MiningBeamDeed, ("kepletek", "sebzes")),
        AbilityActionKind.PointDefence: (PointDefenceDeed, ("kepletek", "sebzes")),
    }

    _KELLEKEK = {
        "kepletek": lambda self: self._engagement,
        "sebzes": lambda self: self._damage_book,
        "belepteto": lambda self: self._join_queue,
        "zsakmany": lambda self: self._loot_ownership,
        "sor": lambda self: self._cast_desk,
    }

    def create(self, caster, kilovo_rekesz, chosen_targets, onmukodo) -> Deed:
        elsutes = Elsutes(caster, kilovo_rekesz, chosen_targets,
                          onmukodo, self._ctx)
        fajta = kilovo_rekesz.ship_ability().ship_ability_card.ability_action_type
        if fajta is AbilityActionKind.Flak:
            if is_shrapnel_burst_slot(kilovo_rekesz):
                return ShrapnelDeed(elsutes, self._engagement,
                                    self._damage_book, self._cast_desk)
            return FlakDeed(elsutes, self._engagement, self._damage_book)

        sor = self.DEEDS.get(fajta)
        if sor is None:
            raise ValueError(f"no deed covers ability kind {fajta}")
        cselekves, kellek_nevek = sor
        return cselekves(elsutes, *(self._KELLEKEK[nev](self) for nev in kellek_nevek))
