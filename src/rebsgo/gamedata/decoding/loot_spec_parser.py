# github.com/Shran21
from __future__ import annotations

from rebsgo.gamedata.loot_tables import LootDamageRadiusSpec, LootDamageSpec, LootRadiusSpec, LootSpecKind


_OLVASOK = {
    LootSpecKind.Damage: LootDamageSpec,
    LootSpecKind.Radius: LootRadiusSpec,
    LootSpecKind.RadiusDamage: LootDamageRadiusSpec,
    LootSpecKind.RadiusAll: LootRadiusSpec,
}


def loot_spec_from_json(obj: dict):
    fajta = LootSpecKind[obj["type"]]
    olvaso = _OLVASOK.get(fajta)
    if olvaso is None:
        raise RuntimeError(f"no reader covers loot kind {fajta}")
    return olvaso.from_json(obj)
