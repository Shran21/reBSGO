# github.com/Shran21

from __future__ import annotations

from rebsgo.vocabulary.combat import SpecialMove


class PilotLoot:
    def __init__(self, user, experience: int, items, special_action):
        self._user = user
        self._experience = experience
        self._items = items
        self._special_action = special_action

    def user(self):
        return self._user

    @property
    def experience(self) -> int:
        return self._experience

    def items(self):
        return self._items

    @property
    def special_action(self):
        return self._special_action

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, PilotLoot):
            return False
        return (self._user == other._user and self._experience == other._experience
                and self._items == other._items and self._special_action == other._special_action)

    def __hash__(self) -> int:
        return hash((self._user, self._experience))

    def __repr__(self) -> str:
        return (f'<spoils for {self._user}: {self._experience} xp, {self._items},'
                f' bonus {self._special_action}>')


class PilotLootItems:
    def __init__(self, user, keszletek):
        self._user = user
        self._item_countables = keszletek

    def user(self):
        return self._user

    @property
    def item_countables(self):
        return self._item_countables

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, PilotLootItems):
            return False
        return self._user == other._user and self._item_countables == other._item_countables

    def __hash__(self) -> int:
        return hash(self._user)

    def __repr__(self) -> str:
        return f'<pickings for {self._user}: {self._item_countables}>'


class PilotBelongings:
    def __init__(self, user, keszletek, exp: int, kulon_gombok=None):
        if kulon_gombok is None:
            kulon_gombok = [SpecialMove.None_]
        self._user = user
        self._item_countables = keszletek
        self._exp = exp
        self._special_actions = kulon_gombok

    def user(self):
        return self._user

    @property
    def item_countables(self):
        return self._item_countables

    def exp(self) -> int:
        return self._exp

    @property
    def special_actions(self):
        return self._special_actions

    def highest_special_action(self):
        highest_special_action = SpecialMove.None_
        highest = 0
        for mostani in self._special_actions:
            if mostani.loot_multiplier > highest:
                highest = mostani.loot_multiplier
                highest_special_action = mostani
        return highest_special_action

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, PilotBelongings):
            return False
        return (self._user == other._user and self._item_countables == other._item_countables
                and self._exp == other._exp and self._special_actions == other._special_actions)

    def __hash__(self) -> int:
        return hash((self._user, self._exp))

    def __repr__(self) -> str:
        return (f'<{self._user} carries {self._item_countables}, {self._exp} xp,'
                f' bonuses {self._special_actions}>')


class CountableLootEntry:
    def __init__(self, item_countable, entry_details):
        self._item_countable = item_countable
        self._loot_entry_info = entry_details

    @property
    def item_countable(self):
        return self._item_countable

    @property
    def entry_details(self):
        return self._loot_entry_info

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, CountableLootEntry):
            return False
        return self._item_countable == other._item_countable and self._loot_entry_info == other._loot_entry_info

    def __hash__(self) -> int:
        return hash((self._item_countable, self._loot_entry_info))

    def __repr__(self) -> str:
        return f'<{self._item_countable} rolled from {self._loot_entry_info}>'


class CountableBonusKind:
    def __init__(self, item_countable, bonusz_tabla=None):
        if bonusz_tabla is None:
            bonusz_tabla = {}
        self._item_countable = item_countable
        self._loot_bonus_type_long_map = bonusz_tabla

    @property
    def item_countable(self):
        return self._item_countable

    @property
    def loot_bonus_type_long_map(self):
        return self._loot_bonus_type_long_map

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, CountableBonusKind):
            return False
        return (self._item_countable == other._item_countable
                and self._loot_bonus_type_long_map == other._loot_bonus_type_long_map)

    def __hash__(self) -> int:
        return hash(self._item_countable)

    def __repr__(self) -> str:
        return f'<{self._item_countable}, bonus shares {self._loot_bonus_type_long_map}>'


class DuelOutcome:
    def __init__(self, user, kisorsoltak, experience: int, *kulon_gombok):
        self._user = user
        self._rolled_items = kisorsoltak
        self._experience = experience
        self._special_actions = list(kulon_gombok)

    def user(self):
        return self._user

    @property
    def rolled_items(self):
        return self._rolled_items

    @property
    def experience(self) -> int:
        return self._experience

    @property
    def special_actions(self):
        return self._special_actions

    def holds_action(self, *vizsgalando_gombok) -> bool:
        for action in self._special_actions:
            for other in vizsgalando_gombok:
                if action == other:
                    return True
        return False

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, DuelOutcome):
            return False
        return (self._user == other._user and self._rolled_items == other._rolled_items
                and self._experience == other._experience and self._special_actions == other._special_actions)

    def __hash__(self) -> int:
        return hash((self._user, self._experience))

    def __repr__(self) -> str:
        return (f'<duel won by {self._user}: {self._rolled_items}, {self._experience} xp,'
                f' bonuses {self._special_actions}>')
