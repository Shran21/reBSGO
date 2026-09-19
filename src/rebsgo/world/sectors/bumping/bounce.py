# github.com/Shran21

from __future__ import annotations

import logging

from rebsgo.world.movement.maneuvers import PulseManeuver
from rebsgo.world.objects.ships import Ship
from rebsgo.vocabulary.world import DepartureCause, ObjectKind
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.geometry.maths.maths import Maths
from rebsgo.gamedata.reading import ObjectStat
from rebsgo.helpers.floats import f32
from rebsgo.journal import hivasi_lanc

log = logging.getLogger(__name__)


class Bounce:
    def __init__(self, damage_book, takarito):
        self._damage_book = damage_book
        self._remover = takarito
        self._current_tick = None
        self._primitive_pair = None
        self._contact_pair = None

    def move_clock_to(self, mostani_ora) -> None:
        self._current_tick = mostani_ora

    def attach_contact_details(self, alakzat_par, erintkezo_par) -> None:
        self._primitive_pair = alakzat_par
        self._contact_pair = erintkezo_par

    @staticmethod
    def _get_tier(space_object) -> int:
        if isinstance(space_object, Ship):
            return space_object.ship_card_of().tier
        return 0

    @staticmethod
    def _get_space_object_ship_card(space_object):
        if not isinstance(space_object, Ship):
            raise ValueError("WorldObject is not first ship")
        return space_object.ship_card_of()

    def resolve_all(self) -> None:
        self._resolve_primitive()
        self._resolve_non_primitives()
    FELOLDOK = (
        (ObjectKind.Asteroid, "_resolve_asteroid_x_other", None),
        (ObjectKind.Missile, "_missile_against_other", None),
        (ObjectKind.Comet, "_resolve_comet_x_other", "_resolve_comet_x_comet"),
    )

    def _resolve_primitive(self) -> None:
        for par in self._primitive_pair or ():
            elso, masodik = par.first(), par.second()
            if elso.is_removed() or masodik.is_removed():
                continue
            self._par_feloldasa(elso, masodik)

    def _par_feloldasa(self, elso, masodik) -> None:
        elso_fajta = elso.space_entity_type
        masodik_fajta = masodik.space_entity_type
        for fajta, egyedul, mindketto in self.FELOLDOK:
            if elso_fajta != fajta and masodik_fajta != fajta:
                continue
            ez, amaz = ((elso, masodik) if elso_fajta == fajta else (masodik, elso))
            if amaz.space_entity_type == fajta:
                if mindketto is None:
                    raise RuntimeError(f"{fajta.name}-{fajta.name} pairing: a case this code rules out")
                getattr(self, mindketto)(ez, amaz)
                return
            getattr(self, egyedul)(ez, amaz)
            return
        raise RuntimeError(f'contact pair reached a state nothing handles: {elso} {masodik}')

    def _resolve_comet_x_other(self, comet, other) -> None:
        if other.space_entity_type.of_kind(ObjectKind.Planetoid, ObjectKind.Planet, ObjectKind.Outpost):
            self._remover.note_removal_cause(comet, DepartureCause.Death)
        elif other.space_entity_type.of_kind(*ObjectKind.ship_types()):
            self._remover.note_removal_cause(other, DepartureCause.Death)

    def _resolve_comet_x_comet(self, uston_teljes, masik_ustokos) -> None:
        self._remover.note_removal_cause(uston_teljes, DepartureCause.Death)
        self._remover.note_removal_cause(masik_ustokos, DepartureCause.Death)

    def _resolve_asteroid_x_other(self, asteroid, other) -> None:
        if other.is_removed():
            return
        self._damage_book.hurt_by_asteroid(asteroid, other)
        self._remover.note_removal_cause(asteroid, DepartureCause.Death)

    SEBEZHETO = (ObjectKind.Outpost, ObjectKind.WeaponPlatform, ObjectKind.Pilot,
                 ObjectKind.BotFighter, ObjectKind.MiningShip, ObjectKind.Comet)

    def _missile_against_other(self, missile, other) -> None:
        if missile.is_removed():
            self._elveszett_raketa(missile)
            return
        if other.space_entity_type == ObjectKind.Planetoid:
            self._remover.note_removal_cause(missile, DepartureCause.Hit, other)
            return
        if not other.space_entity_type.of_kind(*Bounce.SEBEZHETO) or other.is_removed():
            return
        self._damage_book.hurt_by_missile(missile, other)
        self._remover.note_removal_cause(missile, DepartureCause.Hit, other)

    @staticmethod
    def _elveszett_raketa(missile) -> None:
        try:
            raise RuntimeError('reached code believed unreachable')
        except Exception as honnan:
            log.info('missile %s despawned before impact (%s) - contact resolution dropped=%s',
                     missile.id_in_space(), missile.removal_cause_of(), hivasi_lanc(honnan))

    def _resolve_non_primitives(self) -> None:
        for collision_info in self._contact_pair:
            self.settle_contact(collision_info)

    def settle_contact(self, utkozes) -> None:
        current_obj = utkozes.object1
        against_obj = utkozes.object2

        if (current_obj.mover_of().is_moving_object
            and against_obj.mover_of().is_moving_object):
            self._resolve_moving_x_moving_object(current_obj, against_obj, utkozes.collision_record)
        elif (current_obj.mover_of().is_moving_object
              or against_obj.mover_of().is_moving_object):
            moving_object = current_obj if current_obj.mover_of().is_moving_object else against_obj
            static_object = against_obj if current_obj.mover_of().is_moving_object else current_obj
            inverse_normal = not current_obj.mover_of().is_moving_object
            self._resolve_moving_x_static_object(moving_object, static_object, utkozes.collision_record, inverse_normal)

    def _resolve_moving_x_moving_object(self, egyik_objektum, masik_ellen, utkozes_sor) -> None:
        last_collision_tick = egyik_objektum.mover_of().last_collision_tick

        if last_collision_tick is not None and last_collision_tick.value + 10 > self._current_tick.value:
            return

        current_linear_speed = egyik_objektum.mover_of().frame.linear_speed
        current_speed = current_linear_speed.magnitude_

        against_linear_speed = masik_ellen.mover_of().frame.linear_speed
        against_speed = against_linear_speed.magnitude_

        v = utkozes_sor.normal
        melyseg = utkozes_sor.penetration_depth

        current_tier = Bounce._get_tier(egyik_objektum)
        against_tier = Bounce._get_tier(masik_ellen)

        avg_speed = Maths.avg_float(current_speed, against_speed)
        if current_tier <= against_tier:
            depth_multiplier = 1.0
            boost_speed = egyik_objektum.space_subscribe_info().stat_or_default(ObjectStat.BoostSpeed)
            sum_force = Bounce._get_resolution_force(melyseg, depth_multiplier, current_tier, against_tier, avg_speed, boost_speed)
            irany = Vector3.mult(v, sum_force)
            self._set_collision_maneuver(egyik_objektum, irany)

        if against_tier <= current_tier:
            depth_multiplier = 1.0
            boost_speed = masik_ellen.space_subscribe_info().stat_or_default(ObjectStat.BoostSpeed)
            final_force = Bounce._get_resolution_force(melyseg, depth_multiplier, current_tier, against_tier, avg_speed, boost_speed)
            sum_force = -final_force
            irany = Vector3.mult(v, sum_force)
            self._set_collision_maneuver(masik_ellen, irany)

    def _resolve_moving_x_static_object(self, mozgo, allo, utkozes_sor, ellentett_normal: bool) -> None:
        moving_mover = mozgo.mover_of()

        last_collision_tick = moving_mover.last_collision_tick
        if last_collision_tick is not None and last_collision_tick.value + 10 > self._current_tick.value:
            return

        current_linear_speed = moving_mover.frame.linear_speed
        current_speed = current_linear_speed.magnitude_

        v = utkozes_sor.normal
        if ellentett_normal:
            v.negate_()
        melyseg = utkozes_sor.penetration_depth

        depth_multiplier = 1.5

        moving_tier = Bounce._get_tier(mozgo)
        static_tier = Bounce._get_tier(allo)

        boost_speed = mozgo.space_subscribe_info().stat_or_default(ObjectStat.BoostSpeed, 20)
        sum_force = Bounce._get_resolution_force(melyseg, depth_multiplier, moving_tier, static_tier, current_speed, boost_speed)
        irany = Vector3.mult(v, sum_force)
        self._set_collision_maneuver(mozgo, irany)

    @staticmethod
    def _get_resolution_force(depth, melyseg_szorzo, sajat_szint, masik_szint, speed, boost_korlat) -> float:
        depth_sum = f32(depth * melyseg_szorzo)
        base_force = 0 if (sajat_szint == 0 or masik_szint == 0) else f32(Maths.abs(masik_szint - sajat_szint) * 8)
        return Maths.min(depth_sum + base_force + Maths.clamp_safe(speed, 0, boost_korlat), boost_korlat * 4)

    def _set_collision_maneuver(self, space_object, direction) -> None:
        space_object.mover_of().queue_maneuver(PulseManeuver(direction))
        space_object.mover_of().note_collision_tick(self._current_tick)
