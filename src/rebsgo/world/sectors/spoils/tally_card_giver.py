# github.com/Shran21
from __future__ import annotations

from rebsgo.world.objects.ships import Ship, WeaponPlatform
from rebsgo.vocabulary.pilot import Faction, ResourceKind
from rebsgo.vocabulary.world import ObjectKind
from rebsgo.vocabulary.combat import SpecialMove
from rebsgo.gamedata.cards.misc_cards import TallyCardKind
from rebsgo.gamedata.from_json.hull_tally_reader import hull_tallies


class TallyCardGiver:
    def __init__(self, pilotak, sector_card):
        self._users = pilotak
        self._sector_card = sector_card

    def outpost_down(self, erintett_pilotak) -> None:
        for user in erintett_pilotak:
            self._increment_counter(user, TallyCardKind.outposts_killed)

    def npc_downed(self, user, elesett, loot) -> None:
        if (Faction.negated(elesett.faction) == user.pilot_of().faction
            and elesett.is_ship):
            self._increment_counter(user, TallyCardKind.opposite_faction_killed)

        entity_type = elesett.space_entity_type
        if entity_type == ObjectKind.MiningShip:
            self._increment_counter(user, TallyCardKind.mining_ships_killed)
        elif entity_type == ObjectKind.Comet:
            self._increment_counter(user, TallyCardKind.comets_killed)
        elif entity_type == ObjectKind.JumpBeacon:
            self._increment_counter(user, TallyCardKind.jump_beacons_killed)
        if isinstance(elesett, Ship):
            self._overall_ship_killed(user, elesett)

    def _overall_ship_killed(self, user, elesett_hajo) -> None:
        self._increment_counter(user, TallyCardKind.npc_downed)

        if elesett_hajo.faction == Faction.Ancient:
            self.ancients_downed(user, elesett_hajo)
        else:
            self._hull_tally(user, elesett_hajo)

    def _hull_tally(self, user, elesett_hajo) -> None:
        szamlalo = hull_tallies().get(elesett_hajo.ship_card_of().ship_object_key)
        if szamlalo is not None:
            self._increment_counter(user, szamlalo)

    def ancients_downed(self, user, ship) -> None:
        self._increment_counter(user, TallyCardKind.ancients_killed)
        if isinstance(ship, WeaponPlatform):
            self._overall_ancient_stationary_killed(user)
        elif ship.ship_card_of().ship_object_key in (2, 40, 41):
            self._increment_counter(user, TallyCardKind.drones_killed)

    def _overall_ancient_stationary_killed(self, user) -> None:
        self._increment_counter(user, TallyCardKind.stationaries_killed)

    def pilot_downed(self, user, elesett, kulon_gombok) -> None:
        for special_action in kulon_gombok or ():
            if special_action is SpecialMove.Killer or special_action is SpecialMove.AssistCountingAsKill:
                self._increment_counter(user, TallyCardKind.pilot_downed)
                self._increment_counter(user, TallyCardKind.pvp_action_killer)
                if Faction.negated(elesett.faction) == user.pilot_of().faction:
                    self._increment_counter(user, TallyCardKind.opposite_faction_killed)
            elif special_action is SpecialMove.Assist:
                self._increment_counter(user, TallyCardKind.pvp_action_assist)
            elif special_action is SpecialMove.Buffer:
                self._increment_counter(user, TallyCardKind.pvp_action_buffer)
            elif special_action is SpecialMove.Debuffer:
                self._increment_counter(user, TallyCardKind.pvp_action_debuffer)
            elif special_action is SpecialMove.Saviour:
                self._increment_counter(user, TallyCardKind.pvp_action_savior)
            elif special_action is SpecialMove.Avenger:
                self._increment_counter(user, TallyCardKind.pvp_action_avenger)

    def planetoid_claimed(self, user) -> None:
        self._increment_counter(user, TallyCardKind.planetoids_claimed)

    def debris_looted(self, user) -> None:
        self._increment_counter(user, TallyCardKind.debris_looted)

    def ore_taken_out(self, user, item_countable) -> None:
        self.ore_taken(user, item_countable)

    def ore_taken(self, user, item_countable) -> None:
        resource_type = ResourceKind.from_code(item_countable.card_guid_of())
        if resource_type is None or resource_type == ResourceKind.None_:
            return

        self._increment_counter(user, TallyCardKind.asteroids_mined)
        counter_card_type = None
        if resource_type == ResourceKind.Water:
            counter_card_type = TallyCardKind.water_mined
        elif resource_type == ResourceKind.Tylium:
            counter_card_type = TallyCardKind.tylium_mined
        elif resource_type == ResourceKind.Titanium:
            counter_card_type = TallyCardKind.titanium_mined
        if counter_card_type is None:
            return

        self._increment_counter(user, counter_card_type.card_guid, item_countable.count())

    def _increment_counter(self, user, tally, mennyivel: float = 1) -> None:
        user.pilot_of().tally_desk.bump_counter(
            tally, self._sector_card.card_guid_of(), mennyivel)
