# github.com/Shran21
from __future__ import annotations

from rebsgo.gamedata.cards.card_view import CardView


def write_layout(obj, bw, layout) -> None:
    for sor in layout:
        ertek = getattr(obj, sor[1])
        if len(sor) == 3:
            ertek = getattr(ertek, sor[2])
        getattr(bw, "write_" + sor[0])(ertek)


class Card:
    def __init__(self, card_guid: int, view: CardView):
        self.card_guid = card_guid
        self.card_view = view

    _HUZALREND = (
        ('uint32', 'card_guid'),
        ('uint16', 'card_view', 'value'),
    )

    def to_wire(self, bw) -> None:
        write_layout(self, bw, Card._HUZALREND)

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self.card_guid == other.card_guid and self.card_view == other.card_view

    def __hash__(self) -> int:
        return hash((self.card_guid, self.card_view))

    def __repr__(self) -> str:
        return "<Card " + f"card_guid={self.card_guid}, card_view={self.card_view}" + ">"

    def card_guid_of(self) -> int:
        return self.card_guid
