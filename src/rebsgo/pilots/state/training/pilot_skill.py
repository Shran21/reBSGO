# github.com/Shran21
from __future__ import annotations

from rebsgo.services import Services
from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.library import Catalogue
from rebsgo.helpers.gathering import Ownable
from rebsgo.helpers.locks import ReentrantLock


class PilotSkill(Outgoing, Ownable):
    def __init__(self, server_id: int, training_card_guid: int):
        self._catalogue: Catalogue = Services.get(Catalogue)
        self._server_id = server_id
        self._lock = ReentrantLock()
        self._skill_card = None
        self._next_skill_card = None
        self._setup_skill_card_from_guid(training_card_guid)

    def to_wire(self, bw) -> None:
        with self._lock:
            bw.write_uint16(self._server_id)
            bw.write_guid(self._skill_card.card_guid_of())

    def raise_skill(self) -> None:
        with self._lock:
            if self._skill_card.level < self._skill_card.max_level:
                self.seed_skill_card(self._skill_card.next_skill_card_guid)

    def _setup_skill_card_from_guid(self, guid: int) -> None:
        skill_card = self._catalogue.card_of(guid, CardView.Skill)
        if skill_card is None:
            return
        self._skill_card = skill_card
        if self._skill_card.next_skill_card_guid == 0:
            return
        next_skill_card = self._catalogue.card_of(self._skill_card.next_skill_card_guid, CardView.Skill)
        if next_skill_card is None:
            return
        self._next_skill_card = next_skill_card

    def seed_skill_card(self, guid: int) -> None:
        with self._lock:
            self._setup_skill_card_from_guid(guid)

    def belongs_to_group(self, skill_group) -> bool:
        return self._skill_card.skill_group == skill_group

    @property
    def is_max_level(self) -> bool:
        return self._skill_card.next_skill_card_guid == 0

    def upgrade_price(self) -> int:
        if self.is_max_level:
            raise RuntimeError('already at the top tier')
        return self._next_skill_card.price

    @property
    def static_buff(self):
        return self._skill_card.static_buff

    @property
    def multiply_buff(self):
        return self._skill_card.multiply_buff

    @property
    def server_id(self) -> int:
        return self._server_id

    @server_id.setter
    def server_id(self, server_id: int) -> None:
        self._server_id = server_id

    @property
    def skill_card(self):
        return self._skill_card

    def __lt__(self, other: "PilotSkill") -> bool:
        return self._skill_card.sort_weight < other._skill_card.sort_weight

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self._server_id == other._server_id

    def __hash__(self) -> int:
        return self._server_id

    def __str__(self) -> str:
        return f'<training #{self._server_id} in {self._skill_card}>' 
