# github.com/Shran21
from __future__ import annotations


class SectorPlan:
    def __init__(self, sector_desc, szektor_kartyak, csillag_leiras):
        self._sector_desc = sector_desc
        self._sector_cards = szektor_kartyak
        self._star_desc = csillag_leiras

    @property
    def sector_desc(self):
        return self._sector_desc

    def sector_cards(self):
        return self._sector_cards

    @property
    def star_desc(self):
        return self._star_desc

    def __repr__(self) -> str:
        return (f'<sector plan {self._sector_desc}: cards {self._sector_cards}, '
                f'star {self._star_desc}>')
