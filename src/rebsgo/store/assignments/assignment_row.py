# github.com/Shran21
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, eq=False)
class AssignmentRow:
    server_id: int
    mission_guid: int
    associated_sector_card_guid: int
    counter_card_guid: int
    current_count: int
    need_count: int

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        if self.server_id != other.server_id:
            return False
        return self.counter_card_guid == other.counter_card_guid

    def __hash__(self) -> int:
        return hash((self.server_id, self.counter_card_guid))

    def __repr__(self) -> str:
        return (f'<assignment #{self.server_id}, mission {self.mission_guid}'
                f' in sector {self.associated_sector_card_guid}: counter'
                f' {self.counter_card_guid} at {self.current_count}/{self.need_count}>')
