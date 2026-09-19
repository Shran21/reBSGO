# github.com/Shran21

from __future__ import annotations

from rebsgo.world.objects.ships import PlayerShip
from rebsgo.vocabulary.world import ObjectKind
from rebsgo.gamedata.from_json.template_readers import sector_rules
from rebsgo.gamedata.reading import AbilityActionKind

_SZABALYOK = sector_rules(ObjectKind, AbilityActionKind)

BOLYGOCSONK_ATENGEDI = _SZABALYOK.pass_through_planetoid

EGYMASSAL_NEM = _SZABALYOK.same_kind_pass_through


class OverlapFilter:
    def __init__(self, regulation_card):
        self._regulation_card = regulation_card

    def worth_testing(self, first, second) -> bool:
        if first is second or first.collider_of() is None or second.collider_of() is None:
            return False

        elso_fajta = first.space_entity_type
        masodik_fajta = second.space_entity_type

        if elso_fajta == masodik_fajta and elso_fajta in EGYMASSAL_NEM:
            return False

        if ObjectKind.Planetoid in (elso_fajta, masodik_fajta):
            masik = masodik_fajta if elso_fajta == ObjectKind.Planetoid else elso_fajta
            return masik not in BOLYGOCSONK_ATENGEDI

        return self._lathato_par(first, second)

    @staticmethod
    def _lathato_par(first, second) -> bool:
        if not isinstance(first, PlayerShip):
            return True
        if not first.visibility_of().is_visible():
            return False
        if isinstance(second, PlayerShip):
            return second.visibility_of().is_visible()
        return True

    def test_missile_primitive(self, missile, raketan_kivul) -> bool:
        from rebsgo.world.sectors.sides import Stance, relation
        viszony = relation(missile, raketan_kivul, self._regulation_card.target_bracket_mode)
        return raketan_kivul.is_visible() and viszony != Stance.Self and viszony != Stance.Friend
