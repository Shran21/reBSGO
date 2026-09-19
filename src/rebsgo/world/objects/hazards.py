# github.com/Shran21

from __future__ import annotations

import datetime as _dt
from rebsgo.world.movement.movers import FreeMover
from rebsgo.world.objects.world_object import WorldObject
from rebsgo.vocabulary.world import ObjectKind
from rebsgo.gamedata.reading import ObjectStat, AbilityActionKind
from rebsgo.helpers.floats import f32


class Mine(WorldObject):
    def __init__(self, object_id, owner_card, world_card, movement_card, faction, faction_group,
                 space_subscribe_info, gazda, mine_tier: int, kelt_ora: int,
                 armed_at_time_stamp: int):
        super().__init__(object_id, owner_card, world_card, ObjectKind.Mine, faction,
                         faction_group, space_subscribe_info)
        self._movement_card = movement_card
        self._owner_object = gazda
        self._mine_tier = mine_tier
        self._tick_spawn_time = kelt_ora
        self._armed_at_time_stamp = armed_at_time_stamp
        self._anchored = False

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_uint32(self._owner_object.id_in_space())
        bw.write_byte(self._mine_tier & 0xFF)
        armed_at = _dt.datetime.fromtimestamp(self._armed_at_time_stamp / 1000.0,
                                              tz=_dt.timezone.utc).replace(tzinfo=None)
        bw.write_date_time(armed_at)

    def spawned_by(self, kelto) -> bool:
        return self._owner_object == kelto

    def fresh_mover(self, transform) -> None:
        self._mover = FreeMover(transform, self._movement_card)

    @property
    def is_anchored(self) -> bool:
        return self._anchored

    def settle(self) -> None:
        self._anchored = True

    @property
    def owner_object(self):
        return self._owner_object

    @property
    def mine_tier(self) -> int:
        return self._mine_tier

    def is_armed(self, ekkor: int) -> bool:
        return ekkor >= self._armed_at_time_stamp

    def tick_spawn_is_after(self, ekkor: int) -> bool:
        diff = ekkor - self._tick_spawn_time
        life_time = self._space_subscribe_info.stat(ObjectStat.LifeTime)
        if life_time is None:
            from rebsgo.gamedata.from_json.template_readers import mine_tuning
            life_time = mine_tuning().fallback_life_seconds
        life_time_long = int(life_time) * 1000
        return diff >= life_time_long


class Missile(WorldObject):
    def __init__(self, object_id, owner_card, world_card, movement_card, faction, faction_group,
                 space_subscribe_info, gazda, raketa_celpontja, raketa_szint,
                 object_point_hash, effect_radius, kelt_ora):
        super().__init__(object_id, owner_card, world_card, ObjectKind.Missile, faction,
                         faction_group, space_subscribe_info)
        self._owner_object = gazda
        self._missile_launched_on_object = raketa_celpontja
        self._missile_tier = raketa_szint
        self._object_point_hash = object_point_hash
        self._effect_radius = f32(effect_radius)
        self._tick_spawn_time = kelt_ora
        self._movement_card = movement_card

    @property
    def effect_radius(self) -> float:
        return self._effect_radius

    @property
    def missile_launched_on_object(self):
        return self._missile_launched_on_object

    @property
    def missile_tier(self) -> int:
        return self._missile_tier

    @property
    def movement_card(self):
        return self._movement_card

    @property
    def object_point_hash(self) -> int:
        return self._object_point_hash

    @property
    def owner_object(self):
        return self._owner_object

    @property
    def tick_spawn_time(self) -> float:
        return self._tick_spawn_time

    def forget_launch_of(self) -> None:
        self._missile_launched_on_object = None

    def fresh_mover(self, transform) -> None:
        self._mover = FreeMover(transform, self._movement_card)

    def spawned_by(self, kelto) -> bool:
        return self._owner_object == kelto

    def take_from_ability_card(self, ship_ability_card) -> None:
        if ship_ability_card.ability_action_type != AbilityActionKind.FireMissle:
            return

    def tick_spawn_is_after(self, ekkor: int) -> bool:
        diff = ekkor - self._tick_spawn_time
        life_time = self._space_subscribe_info.stat(ObjectStat.LifeTime)
        if life_time is None:
            from rebsgo.gamedata.from_json.template_readers import mine_tuning
            life_time = mine_tuning().fallback_life_seconds
        life_time_long = int(life_time) * 1000
        return diff >= life_time_long

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_uint32(self._owner_object.id_in_space())
        if self._missile_launched_on_object is None:
            bw.write_uint32(0)
        else:
            bw.write_uint32(self._missile_launched_on_object.id_in_space())

        bw.write_byte(self._missile_tier & 0xFF)
        bw.write_uint16(self._object_point_hash)
        bw.write_single(self._effect_radius)
