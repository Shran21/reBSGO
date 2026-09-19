# github.com/Shran21

from __future__ import annotations

from dataclasses import dataclass

from rebsgo.helpers.floats import FLOAT_MAX_VALUE


@dataclass(slots=True, unsafe_hash=True)
class NpcBehaviourSpec:
    id: int
    auto_aggro_distance: float
    aggro_reach: float
    lifespan_seconds: float
    jumps_out_when_fighting_spec: bool
    halt_distance: float

def template_of_tier(tier: int, lifespan_seconds: int, jumps_out_when_fighting_spec: bool,
                     halt_distance: float) -> NpcBehaviourSpec:
    if tier == 1:
        return NpcBehaviourSpec(1, 1000, 4000, lifespan_seconds, jumps_out_when_fighting_spec, halt_distance)
    if tier == 2:
        return NpcBehaviourSpec(2, 1500, 4000, lifespan_seconds, jumps_out_when_fighting_spec, halt_distance)
    if tier == 3:
        return NpcBehaviourSpec(3, 2000, 4000, lifespan_seconds, jumps_out_when_fighting_spec, halt_distance)
    raise ValueError(f'Tier {tier} has no implementation')


def outpost_template() -> NpcBehaviourSpec:
    return NpcBehaviourSpec(1, 3300, 3300, FLOAT_MAX_VALUE, False, 0)


def platform_template(tier: int, platform_sablon) -> NpcBehaviourSpec:
    if platform_sablon.aggro_reach > 0:
        return NpcBehaviourSpec(0, platform_sablon.auto_aggro_distance,
                                platform_sablon.aggro_reach,
                                FLOAT_MAX_VALUE, False, 0)
    if tier <= 2:
        return NpcBehaviourSpec(1, 500, 2000, FLOAT_MAX_VALUE, False, 0)
    return NpcBehaviourSpec(1, 1000, 3000, FLOAT_MAX_VALUE, False, 0)
