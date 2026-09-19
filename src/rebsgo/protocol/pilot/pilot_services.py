# github.com/Shran21

from __future__ import annotations

from dataclasses import dataclass, field

from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.helpers.floats import f32


@dataclass(slots=True, eq=False)
class PilotServices(Outgoing):
    current_sector_id: int
    is_name_change_allowed: bool
    cooldown_faction_switch: int
    cooldown_name_change: int
    last_use_faction_switch: int
    last_use_name_change: int
    cubits_price_faction: float
    cubits_price_name: float
    faction_switch_level_bands: list = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cubits_price_faction = f32(self.cubits_price_faction)
        self.cubits_price_name = f32(self.cubits_price_name)

    def to_wire(self, bw) -> None:
        bw.write_byte(self.current_sector_id)
        bw.write_boolean(self.is_name_change_allowed)
        bw.write_int64(0)
        bw.write_int64(self.cooldown_faction_switch)
        bw.write_int64(self.cooldown_name_change)
        bw.write_int64(self.last_use_faction_switch)
        bw.write_int64(self.last_use_name_change)
        bw.write_single(self.cubits_price_faction)
        bw.write_single(self.cubits_price_name)
        bw.write_desc_collection(self.faction_switch_level_bands)
