# github.com/Shran21

from __future__ import annotations

from dataclasses import dataclass

import math
from rebsgo.geometry.maths.maths import Maths
from rebsgo.gamedata.reading import ShipSlotType
from rebsgo.helpers.floats import f32


@dataclass(slots=True, eq=False)
class RepairAllOrder:
    ship_id: int
    use_cubits: bool
    costs_ship_repair: float
    costs_all_systems: float

    def __repr__(self) -> str:
        fizetoeszkoz = 'cubits' if self.use_cubits else 'resources'
        return (f'<repair ship {self.ship_id} in {fizetoeszkoz}:'
                f' hull {self.costs_ship_repair} + systems {self.costs_all_systems}'
                f' = {self.costs_ship_repair + self.costs_all_systems}>')


class WearCost:
    def __init__(self, world_card):
        self._global_card = world_card

    def _durability_gap(self, system) -> float:
        return f32(system.ship_system_card.durability * f32(1.0 - system.quality()))

    def cost_of_system(self, system, use_cubits: bool) -> float:
        if system.card_guid_of() == 0:
            raise ValueError('repair asked on a system that is not mounted')
        repair_mult = self._global_card.repair_card(use_cubits)
        return Maths.ceil(f32(self._durability_gap(system) * repair_mult))

    def ship_hull_repair_costs(self, ship, use_cubits: bool) -> float:
        repair_mult = self._global_card.repair_card(use_cubits)
        return Maths.ceil(f32(repair_mult * f32(ship.ship_card_of().durability - ship.durability)))

    def repair_all_costs(self, ship, use_cubits: bool) -> int:
        durability_mult = self._global_card.repair_card(use_cubits)

        total_costs = 0.0
        if not use_cubits:
            total_costs += ship.ship_card_of().durability * (1.0 - ship.quality()) * durability_mult
        for rekesz in ship.ship_slots.values():
            if rekesz.ship_slot_card().ship_slot_type == ShipSlotType.ship_paint:
                continue
            if rekesz.ship_system is not None and rekesz.ship_system.card_guid_of() != 0:
                total_costs += self.cost_of_system(rekesz.ship_system, use_cubits)
        return int(math.floor(total_costs + 0.5))

    def repair_system(self, ship_slot) -> None:
        ship_system = ship_slot.ship_system
        if ship_system is None or ship_system.card_guid_of() == 0:
            return
        if (ship_system.ship_system_card.ship_slot_type == ShipSlotType.avionics
            or ship_system.ship_system_card.ship_slot_type == ShipSlotType.ship_paint):
            return
        ship_system.restore_durability()
