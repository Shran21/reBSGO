# github.com/Shran21
from __future__ import annotations

from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.services import Services
from rebsgo.world.combat_rules import LevelCurve
from rebsgo.pilots.state.training.pilot_skill import PilotSkill
from rebsgo.pilots.state.watching import InfoBroadcast
from rebsgo.protocol.watching.watching import InfoKind
from rebsgo.gamedata.library import Catalogue
from rebsgo.gamedata.reading import AbilityActionKind, get_action_stat_mappings, ObjectStat, ObjectStats, SkillFamily
from rebsgo.helpers.guarded import GuardedCount
from rebsgo.helpers.locks import ReadWriteLock, Zarhato
from rebsgo.gamedata.from_json.upgrade_rules_reader import upgrade_rules

_XP_PLAFON = 2 ** 31 - 1


_ATVITEL = (
    ((AbilityActionKind.FireCannon, AbilityActionKind.Flak, AbilityActionKind.PointDefence),
     SkillFamily.Weapon,
     [(ObjectStat.CannonCriticalOffense, ObjectStat.CriticalOffense),
      (ObjectStat.OptimalRange, ObjectStat.OptimalRange),
      (ObjectStat.Accuracy, ObjectStat.Accuracy)],
     True),
    ((AbilityActionKind.FireShotgun, AbilityActionKind.FireKillCannon, AbilityActionKind.FireMachineGun, AbilityActionKind.FireLightMissile, AbilityActionKind.FireHeavyMissile, AbilityActionKind.FireTorpedo),
     SkillFamily.Weapon,
     [],
     True),
    ((AbilityActionKind.FireMining,),
     SkillFamily.Weapon,
     [(ObjectStat.MiningCooldown, ObjectStat.Cooldown),
      (ObjectStat.DamageMining, ObjectStat.DamageLow),
      (ObjectStat.DamageMining, ObjectStat.DamageHigh),
      (ObjectStat.MiningAccuracy, ObjectStat.Accuracy),
      (ObjectStat.MiningArmorPiercing, ObjectStat.ArmorPiercing)],
     True),
    ((AbilityActionKind.FireMissle,),
     SkillFamily.Weapon,
     [(ObjectStat.MissileCriticalOffense, ObjectStat.CriticalOffense),
      (ObjectStat.MissileCooldown, ObjectStat.Cooldown),
      (ObjectStat.MissileMaxRange, ObjectStat.MaxRange),
      (ObjectStat.MissileMaxRange, ObjectStat.MaxRange)],
     True),
    ((AbilityActionKind.RestoreBuff,),
     SkillFamily.Hull,
     [(ObjectStat.RestorePowerPointCost, ObjectStat.PowerPointCost),
      (ObjectStat.RestoreCooldown, ObjectStat.Cooldown)],
     False),
    ((AbilityActionKind.Buff,),
     SkillFamily.Computer,
     [(ObjectStat.BuffPowerPointCost, ObjectStat.PowerPointCost),
      (ObjectStat.BuffDuration, ObjectStat.Duration),
      (ObjectStat.BuffMaxRange, ObjectStat.MaxRange)],
     False),
    ((AbilityActionKind.Debuff,),
     SkillFamily.Computer,
     [(ObjectStat.DebuffPowerPointCost, ObjectStat.PowerPointCost),
      (ObjectStat.DebuffCooldown, ObjectStat.Cooldown)],
     False),
    ((AbilityActionKind.ResourceScan,),
     SkillFamily.Computer,
     [(ObjectStat.BuffMaxRange, ObjectStat.MaxRange),
      (ObjectStat.BuffPowerPointCost, ObjectStat.PowerPointCost)],
     False),
    ((AbilityActionKind.Slide,),
     SkillFamily.Engine,
     [(ObjectStat.ManeuverCooldown, ObjectStat.Cooldown),
      (ObjectStat.BuffPowerPointCost, ObjectStat.PowerPointCost)],
     False),
)


class SkillSheet(InfoBroadcast, Outgoing, Zarhato):
    def __init__(self, skills: dict | None = None, experience: int = 0, spent_experience: int = 0,
                 level_curve=None, player_id: int = 0):
        if level_curve is None:
            level_curve = LevelCurve()
        super().__init__(InfoKind.Level, player_id, level_curve.level_based_on_exp(experience))
        self._skills = {} if skills is None else skills
        self._experience = GuardedCount(experience)
        self._spent_experience = GuardedCount(spent_experience)
        self._level_curve = level_curve
        self._read_write_lock = ReadWriteLock()
        self._catalogue: Catalogue = Services.get(Catalogue)
        self._setup_starter_skills()

    def _setup_starter_skills(self) -> None:
        with self._irva:
            server_id = 0
            skill_cards = self._catalogue.all_skil_cards_of_level(0)
            for skill_card in skill_cards:
                player_skill = PilotSkill(server_id, skill_card.card_guid_of())
                self._skills[server_id] = player_skill
                server_id += 1

    def to_wire(self, bw) -> None:
        with self._olvasva:
            bw.write_length(len(self._skills))
            for skill in self._skills.values():
                bw.write_desc(skill)

    @property
    def experience(self) -> int:
        return self._experience.get()

    @experience.setter
    def experience(self, experience: int) -> None:
        self._experience.set(experience)

    def spent_experience(self) -> int:
        return self._spent_experience.get()

    @property
    def free_experience(self) -> int:
        return self._experience.get() - self._spent_experience.get()

    def note_spent_experience(self, spent_experience: int) -> None:
        self._spent_experience.set(spent_experience)

    def spend_experience(self, elkoltott_xp: int) -> None:
        if elkoltott_xp < 0:
            raise ValueError('spending negative experience is impossible')
        self._spent_experience.add(elkoltott_xp)

    def experience_reaches_next_level(self, keszseg_id: int) -> bool:
        skill = self._skills.get(keszseg_id)
        if skill is None or skill.is_max_level:
            return False
        return self.free_experience >= skill.upgrade_price()

    def raise_skill(self, keszseg_id: int) -> None:
        with self._irva:
            skill_to_upgrade = self._skills.get(keszseg_id)
            if skill_to_upgrade.is_max_level:
                return
            self.spend_experience(skill_to_upgrade.upgrade_price())
            skill_to_upgrade.raise_skill()

    def clear_skill(self, keszseg_id: int) -> None:
        with self._irva:
            skill = self._skills.get(keszseg_id)
            if skill is None:
                return
            skill_hash = skill.skill_card.hash
            skill_cards = self._catalogue.all_skil_cards_of_level(0)
            zero = next((s for s in skill_cards if s.hash == skill_hash), None)
            if zero is None:
                return
            skill.seed_skill_card(zero.card_guid_of())

    def earn_experience(self, experience_to_add: int) -> None:
        if experience_to_add < 0:
            raise ValueError('experience to add is required')
        current_experience = self.experience
        if current_experience == _XP_PLAFON:
            return
        new_experience = current_experience + experience_to_add
        if new_experience < current_experience:
            self.experience = _XP_PLAFON
        else:
            self.experience = new_experience
        new_level = self._level_curve.level_based_on_exp(new_experience)
        self.set(new_level)

    @property
    def all_skills(self) -> dict:
        return self._skills

    def as_object_stats(self, ability_action_type) -> ObjectStats:
        eredmeny = ObjectStats()
        for fajtak, csalad, parok, fajta_specifikus in _ATVITEL:
            if ability_action_type not in fajtak:
                continue
            for skill in self._skills.values():
                if not skill.belongs_to_group(csalad):
                    continue
                for honnan, hova in parok:
                    self.bind_skill_to_stat(skill, eredmeny, honnan, hova)
                if fajta_specifikus:
                    self._set_action_specific_weapon_skills(skill, eredmeny, ability_action_type)
            break
        return eredmeny

    def _set_action_specific_weapon_skills(self, skill, mutatok: ObjectStats, ability_action_type) -> None:
        for source_stat, target_stat in get_action_stat_mappings(ability_action_type):
            self.bind_skill_to_stat(skill, mutatok, source_stat, target_stat)

    def skill_for(self, skill_group, stat):
        return next((skill for skill in self._skills.values()
                     if skill.belongs_to_group(skill_group) and skill.multiply_buff.holds_stat(stat)), None)

    def bind_skill_to_stat(self, skill, stats: ObjectStats, keszseg_stat, felulir_stat) -> None:
        if skill.multiply_buff.holds_stat(keszseg_stat):
            pen_strength = skill.multiply_buff.stat(keszseg_stat)
            stats.set_stat(felulir_stat, pen_strength)

    def skill_by_hash(self, hash: int):
        with self._olvasva:
            return self._get_skill_by_hash_internal(hash)

    def _get_skill_by_hash_internal(self, hash: int):
        return next((ps for ps in self._skills.values() if ps.skill_card.hash == hash), None)

    def skills_allow_upgrade(self, skill_hashes, system_level: int) -> bool:
        kell = upgrade_rules().required_skill_level(system_level)
        with self._olvasva:
            meglevok = (self._get_skill_by_hash_internal(h) for h in skill_hashes)
            return all(k.skill_card.level >= kell for k in meglevok if k is not None)
