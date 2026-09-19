# github.com/Shran21
from __future__ import annotations

from rebsgo.gamedata.from_json.combat_tuning_reader import nuclear_tuning
from rebsgo.gamedata.reading import ConsumableEffectKind, ObjectStat, ObjectStats
from rebsgo.helpers.floats import f32


def classify_launcher(kepesseg_kartya) -> str:
    return nuclear_tuning().launcher_of(kepesseg_kartya)


def _damage_multiplier(consumable_card) -> float:
    marker = 0.0
    for kulcs, ertek in consumable_card.item_buff_add.all_stats.items():
        if kulcs not in (ObjectStat.DamageLow, ObjectStat.DamageHigh):
            continue
        marker = max(marker, ertek)
    return 1.0 + marker


def apply_nuclear_damage(stats: ObjectStats, kepesseg_kartya, consumable_card) -> None:
    if consumable_card.effect_type != ConsumableEffectKind.DamageNuclear:
        return

    base = kepesseg_kartya.item_buff_add
    base_low = base.stat_or_default(ObjectStat.DamageLow)
    base_high = base.stat_or_default(ObjectStat.DamageHigh)
    damage_mult = _damage_multiplier(consumable_card)
    stats.set_stat(ObjectStat.DamageLow, f32(base_low * damage_mult))
    stats.set_stat(ObjectStat.DamageHigh, f32(base_high * damage_mult))


def apply_to_ability_stats(ability_stats: ObjectStats, kepesseg_kartya, consumable_card) -> None:
    apply_nuclear_damage(ability_stats, kepesseg_kartya, consumable_card)


def apply_to_missile_stats(missile_stats: ObjectStats, kepesseg_kartya, consumable_card) -> None:
    apply_nuclear_damage(missile_stats, kepesseg_kartya, consumable_card)


def ensure_aoe_stats(missile_stats: ObjectStats, kepesseg_kartya) -> None:
    inner, outer = nuclear_tuning().aoe_radii(classify_launcher(kepesseg_kartya))
    missile_stats.set_stat(ObjectStat.AoeInnerRadius, inner)
    missile_stats.set_stat(ObjectStat.AoeOuterRadius, outer)

    if not missile_stats.holds_stat(ObjectStat.DrainLow):
        dmg_low = missile_stats.stat_or_default(ObjectStat.DamageLow)
        dmg_high = missile_stats.stat_or_default(ObjectStat.DamageHigh)
        arany = nuclear_tuning().drain_from_damage()
        missile_stats.set_stat(ObjectStat.DrainLow, f32(dmg_low * arany))
        missile_stats.set_stat(ObjectStat.DrainHigh, f32(dmg_high * arany))
