# github.com/Shran21

from __future__ import annotations

from rebsgo.world.sectors.harm.damage_log import DamageLog
from rebsgo.world.sectors.running.coming_and_going import DepartureWatcher
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.protocol_book_replies import replies_for
from rebsgo.helpers.floats import f32


class SectorDamageLog(DepartureWatcher):
    def __init__(self, itt_levok):
        self._object_damage_history_map = {}
        self._sector_users = itt_levok

    def refresh_damage(self, sebzes_sor) -> None:
        dmg_history = self._object_damage_history_map.get(sebzes_sor.to.id_in_space())
        if dmg_history is None:
            dmg_history = DamageLog(self._sector_users)
            self._object_damage_history_map[sebzes_sor.to.id_in_space()] = dmg_history
        dmg_history.took_a_hit(sebzes_sor)

    def damage_history(self, arg):
        if isinstance(arg, int):
            return self._object_damage_history_map.get(arg)
        return self.damage_history(arg.id_in_space())

    def kill_shot_dealer_of_object(self, space_object):
        dmg_history = self.damage_history(space_object)
        if dmg_history is None:
            return None
        return dmg_history.kill_shot_dealer()

    def on_update(self, arg) -> None:
        self._object_damage_history_map.pop(arg.departed_object.id_in_space(), None)


class WearFromDamage:
    def __init__(self, pilotak, sender):
        self._users = pilotak
        self._sender = sender
        self._pilot_wire = replies_for(ProtocolID.Pilot)

    def took_a_hit(self, sebzes_sor) -> None:
        target_object = sebzes_sor.to
        if not target_object.is_player():
            return

        user = self._users.user(target_object.pilot_id())
        if user is None:
            return

        active_ship = user.pilot_of().hangar_of().active_ship()
        rekeszek = active_ship.ship_slots
        durability_to_reduce_by = sebzes_sor.damage

        slots_with_system = sum(1 for rekesz in rekeszek.values() if rekesz.ship_system is not None)
        slots_with_system = 1 if slots_with_system == 0 else slots_with_system
        divided_damage = f32(durability_to_reduce_by / slots_with_system)

        active_ship.wear_down(divided_damage)

        for rekesz in rekeszek.values():
            rendszer = rekesz.ship_system
            if rendszer is None:
                continue
            rendszer.wear_down(divided_damage)

        self._sender.push_to(self._pilot_wire.ship_info_durability(active_ship), user)
        self._sender.push_to(self._pilot_wire.ship_slots(active_ship), user)
