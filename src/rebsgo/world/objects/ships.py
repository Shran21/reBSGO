# github.com/Shran21

from __future__ import annotations

from rebsgo.services import Services
from rebsgo.world.objects.world_object import WorldObject
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.library import Catalogue
from rebsgo.world.movement.movers import PilotMover, FreeMover
from rebsgo.vocabulary.world import ArrivalCause, ObjectKind
from abc import abstractmethod
from rebsgo.world.objects.attachments import ShipTraits, ShipHardpoints
from rebsgo.vocabulary.pilot import FactionGroup
from rebsgo.helpers.inheriting import csak_orokosen_at


class Ship(WorldObject):
    def __init__(self, object_id: int, owner_card, world_card, space_entity_type, faction,
                 faction_group, ship_bindings, ship_aspects, hajo_allapot, ship_card):
        csak_orokosen_at(self, Ship)
        super().__init__(object_id, owner_card, world_card, space_entity_type, faction, faction_group,
                         hajo_allapot)
        self.catalogue: Catalogue = Services.get(Catalogue)
        self._ship_bindings = ship_bindings
        self._ship_aspects = ship_aspects
        if hajo_allapot is not None and hasattr(hajo_allapot, "take_aspects"):
            hajo_allapot.take_aspects(ship_aspects)
        movement_card = self.catalogue.card_of(self.world_card().card_guid_of(), CardView.Movement)
        if movement_card is None:
            raise ValueError('a movement card is required')
        self._movement_card = movement_card
        self._ship_card = ship_card

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_desc(self._ship_bindings)
        bw.write_desc(self._ship_aspects)

    def bindings_of(self):
        return self._ship_bindings

    @property
    def ship_aspects(self):
        return self._ship_aspects

    def ship_card_of(self):
        return self._ship_card

    @property
    def movement_card(self):
        return self._movement_card

    @property
    def is_ship(self) -> bool:
        return True

    @property
    def prefab_name(self) -> str:
        paint_card = self._ship_bindings.ship_system_paint_card
        if paint_card is None or paint_card.uses_default_model:
            return super().prefab_name
        return paint_card.prefab_name.lower()


class PlayerShip(Ship):
    def __init__(self, object_id, owner_card, world_card, ship_card, faction, faction_group,
                 ship_bindings, ship_aspects, player_id, bgo_admin_roles, lathatosag,
                 hajo_adat):
        super().__init__(object_id, owner_card, world_card, ObjectKind.Pilot, faction,
                         faction_group, ship_bindings, ship_aspects, hajo_adat, ship_card)
        self._player_id = player_id
        self._roles = bgo_admin_roles
        self._player_visibility = lathatosag
        self.creating_cause = ArrivalCause.AlreadyExists

    def fresh_mover(self, transform) -> None:
        self._mover = PilotMover(transform, self._movement_card, self._player_id)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_uint32(self._player_id)
        bw.write_uint32(self._roles)
        bw.write_desc(self._player_visibility)

    def write_with_visibility_override(self, bw, is_visible: bool) -> None:
        super().to_wire(bw)
        bw.write_uint32(self._player_id)
        bw.write_uint32(self._roles)
        bw.write_boolean(is_visible)

    def is_visible(self) -> bool:
        return self._player_visibility.is_visible()

    def visibility_of(self):
        return self._player_visibility

    def pilot_id(self) -> int:
        return self._player_id

    def is_player(self) -> bool:
        return True

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self._player_id == other._player_id

    def __hash__(self) -> int:
        return hash(self._player_id)


class NpcShip(Ship):
    def __init__(self, object_id, owner_card, world_card, space_entity_type, faction, faction_group,
                 ship_bindings, ship_aspects, hajo_allapot, ship_card, behaviour_template,
                 bot_celok, szuletett_ms):
        super().__init__(object_id, owner_card, world_card, space_entity_type, faction, faction_group,
                         ship_bindings, ship_aspects, hajo_allapot, ship_card)
        self._npc_behaviour_template = behaviour_template
        self._npc_objectives = bot_celok
        self._creating_time_stamp = szuletett_ms

    @property
    def behaviour_template(self):
        return self._npc_behaviour_template

    @property
    def creating_time_stamp(self) -> int:
        return self._creating_time_stamp

    @property
    def npc_objectives(self):
        return self._npc_objectives

    def kill_objectives(self):
        from rebsgo.world.sectors.npc_minds import NpcGoalKind
        return [obj for obj in self._npc_objectives if obj.type == NpcGoalKind.Kill]

    def kor_szunetel(self, mennyi_ms: int) -> None:
        if mennyi_ms > 0:
            self._creating_time_stamp += mennyi_ms

    def patrol_objectives(self):
        from rebsgo.world.sectors.npc_minds import NpcGoalKind
        return [obj for obj in self._npc_objectives if obj.type == NpcGoalKind.Patrol]

    @abstractmethod
    def wants_kills(self) -> bool:
        ...


class CruiserShip(Ship):
    def __init__(self, object_id, owner_card, world_card, faction, faction_group, ship_bindings,
                 ship_aspects, hajo_allapot, ship_card):
        super().__init__(object_id, owner_card, world_card, ObjectKind.Cruiser, faction,
                         faction_group, ship_bindings, ship_aspects, hajo_allapot, ship_card)


class MiningShip(Ship):
    def __init__(self, object_id, owner_card, world_card, faction, space_subscribe_info, owner,
                 planetoidahoz_kotve, ship_card):
        super().__init__(object_id, owner_card, world_card, ObjectKind.MiningShip, faction,
                         FactionGroup.Group0, ShipHardpoints(), ShipTraits(), space_subscribe_info, ship_card)
        self._owner = owner
        self._attached_to_planetoid = planetoidahoz_kotve
        self._last_time_mining = 0
        self._last_time_assassin = 0

    @property
    def attached_to_planetoid(self):
        return self._attached_to_planetoid

    @property
    def last_time_assassin(self) -> int:
        return self._last_time_assassin

    @last_time_assassin.setter
    def last_time_assassin(self, utolso_orgyilkos: int) -> None:
        self._last_time_assassin = utolso_orgyilkos

    @property
    def last_time_mining(self) -> int:
        return self._last_time_mining

    @last_time_mining.setter
    def last_time_mining(self, utolso_banyaszat: int) -> None:
        self._last_time_mining = utolso_banyaszat

    @property
    def owner(self):
        return self._owner

    def spawned_by(self, kelto) -> bool:
        return self._owner.pilot_of().user_id_of() == kelto.pilot_id()


class PatrolBot(NpcShip):
    def __init__(self, object_id, owner_card, world_card, ship_card, faction, faction_group,
                 ship_bindings, ship_aspects, hajo_allapot, behaviour_template,
                 bot_celok, time_created):
        super().__init__(object_id, owner_card, world_card, ObjectKind.BotFighter, faction,
                         faction_group, ship_bindings, ship_aspects, hajo_allapot, ship_card,
                         behaviour_template, bot_celok, time_created)

    def fresh_mover(self, transform) -> None:
        self._mover = FreeMover(transform, self._movement_card)

    @property
    def wants_objectives(self) -> bool:
        return self._npc_objectives is not None and len(self._npc_objectives) > 0

    def wants_kills(self) -> bool:
        if self._npc_objectives is None:
            return False
        from rebsgo.world.sectors.npc_minds import NpcGoalKind
        kill_objectives = [obj for obj in self._npc_objectives if obj.type == NpcGoalKind.Kill]
        if not kill_objectives:
            return False
        return len(kill_objectives[0].objectives_to_kill) > 0


class WeaponPlatform(NpcShip):
    def __init__(self, object_id, owner_card, world_card, ship_card, faction,
                 space_subscribe_info, behaviour_template, szuletett_ms,
                 ship_bindings=None, ship_aspects=None):
        super().__init__(object_id, owner_card, world_card, ObjectKind.WeaponPlatform, faction,
                         FactionGroup.Group0,
                         ShipHardpoints() if ship_bindings is None else ship_bindings,
                         ShipTraits() if ship_aspects is None else ship_aspects,
                         space_subscribe_info, ship_card,
                         behaviour_template, [], szuletett_ms)

    def wants_kills(self) -> bool:
        return False


class Outpost(NpcShip):
    def __init__(self, object_id, owner_card, world_card, ship_card, faction,
                 hajo_allapot, behaviour_template, szuletett_ms,
                 ship_aspects, faction_group=FactionGroup.Group0, ship_bindings=None):
        ship_bindings = ShipHardpoints() if ship_bindings is None else ship_bindings
        super().__init__(object_id, owner_card, world_card, ObjectKind.Outpost, faction,
                         faction_group, ship_bindings, ship_aspects, hajo_allapot, ship_card,
                         behaviour_template, [], szuletett_ms)

    def wants_kills(self) -> bool:
        return False
