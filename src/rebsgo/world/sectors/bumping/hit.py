# github.com/Shran21
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, unsafe_hash=True)
class Hit:
    collision_record: object
    object1: object
    object2: object

    def __repr__(self) -> str:
        return f'<{self.object1} struck {self.object2}: {self.collision_record}>' 
