# github.com/Shran21

from __future__ import annotations

from dataclasses import dataclass

from collections import Counter

from abc import ABC, abstractmethod
from rebsgo.world.sectors.spoils.drops import AsteroidSpoils
from rebsgo.world.sectors.running.coming_and_going import DepartureWatcher
from rebsgo.world.sectors.running.jumps import Booking
from rebsgo.world.sectors.npc_minds import PatrolGoal
from rebsgo.geometry.primitives.quaternion import Quaternion
from rebsgo.geometry.primitives.transform import Transform
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.services import Services
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.library import Catalogue
from rebsgo.gamedata.npc_minds import template_of_tier
from rebsgo.gamedata.ship_parts.parts import CountableItem
from rebsgo.gamedata.reading import ObjectStat
from rebsgo.helpers.dice import Dice
from rebsgo.helpers.floats import f32
from rebsgo.helpers.small_helpers import WeightedPick
from rebsgo.helpers.locks import ReentrantLock
from rebsgo.vocabulary.pilot import ResourceKind
from rebsgo.vocabulary.world import DepartureCause, ObjectKind
import heapq
import logging


@dataclass(slots=True, eq=False)
class AsteroidYield:
    asteroid_count: int
    red_count: int
    tyl_count: int
    titanium_count: int
    water_count: int

    def tylium_share(self) -> float:
        if self.rich_asteroid_count == 0:
            return 0
        return f32(self.tyl_count / self.rich_asteroid_count)

    def titanium_share(self) -> float:
        if self.rich_asteroid_count == 0:
            return 0
        return f32(self.titanium_count / self.rich_asteroid_count)

    def water_share(self) -> float:
        if self.rich_asteroid_count == 0:
            return 0
        return f32(self.water_count / self.rich_asteroid_count)

    def red_percentage(self) -> float:
        if self.asteroid_count == 0:
            return 0
        return f32(self.red_count / self.asteroid_count)

    @property
    def rich_asteroid_count(self) -> float:
        return f32(self.asteroid_count - self.red_count)

    def __repr__(self) -> str:
        return (f'<{self.asteroid_count} asteroids:'
                f' {self.red_count} barren ({self.red_percentage():.0%}),'
                f' {self.tyl_count} tylium ({self.tylium_share():.0%}),'
                f' {self.titanium_count} titanium ({self.titanium_share():.0%}),'
                f' {self.water_count} water ({self.water_share():.0%})>')


class SpawnRule(ABC):
    def __init__(self, spawn_runner, kelto_figyelo):
        self.catalogue: Catalogue = Services.get(Catalogue)
        self._spawn_runner = spawn_runner
        self._spawn_subscriber = kelto_figyelo

    @abstractmethod
    def spawn(self) -> None:
        pass

    def follow_up(self):
        return None

    @property
    def _is_server_just_started(self) -> bool:
        return self._spawn_runner.tick.seconds_since_start < 60.0

    def _adjust_spawn_time_if_is_initial_spawn(self, kelt_ekkor: int) -> int:
        return 10 if self._is_server_just_started else kelt_ekkor


class BirthArea:
    def __init__(self, keltohely_sablon):
        self._spawn_area_template = keltohely_sablon
        self._rnd = Dice()
        self._rotation = keltohely_sablon.direction().quaternion

    def rotation_of(self):
        return self._rotation

    @property
    def rnd(self) -> Dice:
        return self._rnd

    @property
    def random_position(self) -> Vector3:
        return Vector3.of_array(self._rnd.point_between(
            self._spawn_area_template.corner_a().to_array_,
            self._spawn_area_template.corner_b().to_array_))


class PlacedObject:
    def __init__(self, template, space_object):
        self._template = template
        self._space_object = space_object

    @property
    def template(self):
        return self._template

    @property
    def space_object(self):
        return self._space_object

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, PlacedObject):
            return False
        return self._template == other._template and self._space_object == other._space_object

    def __hash__(self) -> int:
        return hash((self._template, self._space_object))

    def __repr__(self) -> str:
        return f'<{self._space_object} placed from {self._template}>'


class DueList:
    def __init__(self):
        priority_queue = []
        lock = ReentrantLock()
        self._priority_queue = priority_queue
        self._lock = lock

    def _has_item_with_timeout(self, current) -> bool:
        if not self._priority_queue:
            return False
        jump_schedule_item = self._priority_queue[0]
        delta = jump_schedule_item.time_stamp() - current.time_stamp()
        return delta <= 0

    def all_timeout_items(self, current):
        return self.timeout_items(current, 0)

    def timeout_items(self, current, max_items: int = 0):
        with self._lock:
            if not self._has_item_with_timeout(current):
                return []

            r_lst = []
            while self._has_item_with_timeout(current):
                if max_items > 0 and len(r_lst) >= max_items:
                    break
                r_lst.append(heapq.heappop(self._priority_queue))
            return r_lst

    def due_item(self, current):
        with self._lock:
            if not self._has_item_with_timeout(current):
                return None
            return heapq.heappop(self._priority_queue)

    def has_timeout_items(self, current) -> bool:
        with self._lock:
            return self._has_item_with_timeout(current)

    def enqueue(self, mostani_ora, e, utemezes_keses: float) -> None:
        if mostani_ora is None or e is None:
            raise TypeError('both the tick and the rule are required')

        with self._lock:
            heapq.heappush(self._priority_queue, Booking(mostani_ora, utemezes_keses, e))

    def item(self) -> Booking:
        with self._lock:
            if not self._priority_queue:
                raise RuntimeError('queue is empty; nothing to take')
            return heapq.heappop(self._priority_queue)


class CruiserRule(SpawnRule):
    def __init__(self, cirkalo_sablon, spawn_runner, factory, arrival_gate):
        super().__init__(spawn_runner, spawn_runner)
        self._join_queue = arrival_gate
        self._factory = factory
        self._cruiser_template = cirkalo_sablon

    def spawn(self) -> None:
        tmp_cruiser = self._factory.hatch_cruiser(self._cruiser_template)
        self._join_queue.admit_object(tmp_cruiser)


class DynamicNpcRule(SpawnRule):
    def __init__(self, bot_sablon, spawn_runner, factory, arrival_gate, dice):
        super().__init__(spawn_runner, spawn_runner)
        self._join_queue = arrival_gate
        self._factory = factory
        self._dice = dice
        self._bot_template = bot_sablon

    def spawn(self) -> None:
        sablon = self._bot_template
        doboz = None if sablon is None else sablon.spawn_box
        if doboz is None or doboz.min() is None or doboz.max() is None:
            return
        ship_card = self.catalogue.card_of(sablon.object_guid, CardView.Ship)
        if ship_card is None:
            return

        helyzet = Transform(
            Vector3.of_array(self._dice.point_between(doboz.min().to_array_, doboz.max().to_array_)),
            Quaternion.any_rotation(self._dice.between_whole(0, 3)))
        viselkedes = template_of_tier(
            ship_card.tier,
            self._dice.wobble(sablon.lifespan_seconds, 0.1),
            sablon.jumps_out_when_fighting, 400)

        jarat = self._factory.hatch_fighter(
            sablon.object_guid, [], [], [PatrolGoal(0, doboz)], helyzet, viselkedes,
            [] if sablon.loot_template_ids is None else sablon.loot_template_ids,
            owner_guid=sablon.owner_guid, gear_level=sablon.gear_level)
        self._join_queue.admit_object(jarat)
        self._spawn_runner.template_by_object[jarat.id_in_space()] = \
            PlacedObject(sablon, jarat)


class ResourceRule(SpawnRule):
    def __init__(self, valaszto, elso_keltes: int, spawn_runner, loot_ownership):
        super().__init__(spawn_runner, spawn_runner)
        self._item_picker = valaszto
        self._init_spawn_time = elso_keltes
        self._loot_ownership = loot_ownership


class BirthAreas:
    def __init__(self):
        self._spawn_map = {}

    def register_spawn(self, keltohely_sablon) -> None:
        spawns = self._spawn_map.get(keltohely_sablon.faction())
        if spawns is None:
            self._spawn_map[keltohely_sablon.faction()] = {}
            spawns = self._spawn_map[keltohely_sablon.faction()]
        spawns[keltohely_sablon.id()] = BirthArea(keltohely_sablon)

    def spawn_for(self, faction):
        if faction not in self._spawn_map:
            return None
        values = list(self._spawn_map[faction].values())
        if not values:
            return None
        return values[0]


class PlatformRule(SpawnRule):
    def __init__(self, objektum_sablon, spawn_runner, object_forge, arrival_gate):
        super().__init__(spawn_runner, spawn_runner)
        self._weapon_platform_template = objektum_sablon
        self._object_forge = object_forge
        self._join_queue = arrival_gate

    def spawn(self) -> None:
        new_platform = self._object_forge.hatch_platform(self._weapon_platform_template)
        self._join_queue.admit_object(new_platform)
        self._spawn_runner.template_by_object[new_platform.id_in_space()] = \
            PlacedObject(self._weapon_platform_template, new_platform)


class AsteroidResourceRule(ResourceRule):
    def __init__(self, spawn_runner, valaszto, loot_ownership, asteroid,
                 asteroid_desc, dice):
        super().__init__(valaszto, asteroid_desc.respawn_resource_time, spawn_runner, loot_ownership)
        self._max_resource_desc = asteroid_desc.max_resource_desc
        self._asteroid = asteroid
        self._asteroid_desc = asteroid_desc
        self._dice = dice

    def spawn(self) -> None:
        if self._asteroid is None or self._asteroid.is_removed():
            return
        ujra = self._adjust_spawn_time_if_is_initial_spawn(self._init_spawn_time)
        talalat = self._item_picker.random_item()

        if talalat.resource_type != ResourceKind.None_:
            if self._asteroid_desc.max_resource_desc.min_red_percentage == 1:
                return
            eloszlas = self._spawn_runner.asteroid_distribution()
            if (self._item_picker.rnd.passes(talalat.chance)
                and self.red_share_within_bounds(eloszlas)
                and self._share_below_ceiling(talalat, eloszlas)):
                telito = self._asteroid.space_subscribe_info().stat(ObjectStat.MaxHullPoints)
                darab = self._dice.wobble(
                    int(telito * talalat.hp_to_resource_factor), talalat.variation)
                self._loot_ownership.stash_loot(
                    self._asteroid,
                    AsteroidSpoils(CountableItem.from_guid(talalat.resource_type.guid, darab)))
                return

        self._spawn_subscriber.on_spawn(self.follow_up(), ujra)

    def _share_below_ceiling(self, sorsolt_tetel, aszteroida_eloszlas) -> bool:
        percentage = 0
        max_percentage = 0
        resource_type = sorsolt_tetel.resource_type
        if resource_type == ResourceKind.Tylium:
            percentage = aszteroida_eloszlas.tylium_share()
            max_percentage = self._max_resource_desc.max_tylium_percentage
        elif resource_type == ResourceKind.Titanium:
            percentage = aszteroida_eloszlas.titanium_share()
            max_percentage = self._max_resource_desc.max_titanium_percentage
        elif resource_type == ResourceKind.Water:
            percentage = aszteroida_eloszlas.water_share()
            max_percentage = self._max_resource_desc.max_water_percentage
        if max_percentage >= 100:
            return False

        return percentage <= max_percentage

    def red_share_within_bounds(self, nyersanyag_eloszlas) -> bool:
        min_red_percentage = self._max_resource_desc.min_red_percentage

        if nyersanyag_eloszlas.asteroid_count == 0 or nyersanyag_eloszlas.red_count == 0:
            return True

        return nyersanyag_eloszlas.red_percentage() > min_red_percentage

    def follow_up(self):
        return self.copy()

    def copy(self) -> "AsteroidResourceRule":
        return AsteroidResourceRule(self._spawn_runner, self._item_picker,
                                    self._loot_ownership, self._asteroid,
                                    self._asteroid_desc, self._dice)


class PlanetoidResourceRule(ResourceRule):
    def __init__(self, spawn_runner, valaszto, planetoida_leiras, loot_ownership,
                 planetoid, dice):
        super().__init__(valaszto, planetoida_leiras.respawn_resource_time, spawn_runner, loot_ownership)
        self._planetoid_desc = planetoida_leiras
        self._planetoid = planetoid
        self._dice = dice

    def spawn(self) -> None:
        if self._planetoid is None or self._planetoid.is_removed():
            return
        ujra = self._adjust_spawn_time_if_is_initial_spawn(self._init_spawn_time)
        talalat = self._item_picker.random_item()

        if talalat.resource_type != ResourceKind.None_ and self._dice.passes(talalat.chance):
            ertek = self._dice.between_whole(
                self._planetoid_desc.min_resources, self._planetoid_desc.max_resources)
            self._loot_ownership.stash_loot(
                self._planetoid,
                AsteroidSpoils(CountableItem.from_guid(talalat.resource_type.guid, ertek)))
            return

        self._spawn_subscriber.on_spawn(self.follow_up(), ujra)

    def follow_up(self):
        return self.copy()

    def copy(self) -> "PlanetoidResourceRule":
        return PlanetoidResourceRule(self._spawn_runner, self._item_picker,
                                     self._planetoid_desc, self._loot_ownership,
                                     self._planetoid, self._dice)


log = logging.getLogger(__name__)


class AsteroidRule(SpawnRule):
    def __init__(self, aszteroida_sablon, sector_desc, spawn_runner, object_forge, arrival_gate, valaszto, loot_ownership, random):
        super().__init__(spawn_runner, spawn_runner)
        self._asteroid_template = aszteroida_sablon
        self._asteroid_desc = sector_desc.asteroid_desc
        self._object_forge = object_forge
        self._join_queue = arrival_gate
        self._dice = random
        self._item_picker = valaszto
        self._loot_ownership = loot_ownership
        self._asteroid = None

    def spawn(self) -> None:
        hp = self._calculate_hp()
        asteroid = self._object_forge.hatch_asteroid(self._asteroid_template, hp)

        self._join_queue.admit_object(asteroid)
        self._asteroid = asteroid

        respawn_resource_time = self._adjust_spawn_time_if_is_initial_spawn(self._asteroid_desc.respawn_resource_time)

        self._spawn_subscriber.on_spawn(self.follow_up(), respawn_resource_time)
        self._spawn_runner.template_by_object[asteroid.id_in_space()] = \
            PlacedObject(self._asteroid_template, asteroid)

    def follow_up(self):
        return AsteroidResourceRule(self._spawn_runner, self._item_picker, self._loot_ownership,
                                    self._asteroid, self._asteroid_desc, self._dice)

    def _calculate_hp(self) -> float:
        hp = 1
        try:
            min_ = self._asteroid_desc.hp_interval[0]
            max_ = self._asteroid_desc.hp_interval[1]
            hp = self._dice.between_whole(min_, max_)
        except IndexError as index_out_of_bounds_exception:
            log.error(str(index_out_of_bounds_exception))

        return hp


class PlanetoidRule(SpawnRule):
    def __init__(self, planetoida_sablon, sector_desc, spawn_runner, object_forge, arrival_gate, valaszto, loot_ownership, dice):
        super().__init__(spawn_runner, spawn_runner)
        self._planetoid_template = planetoida_sablon
        self._planetoid_desc = sector_desc.planetoid_desc
        self._object_forge = object_forge
        self._join_queue = arrival_gate
        self._item_picker = valaszto
        self._loot_ownership = loot_ownership
        self._dice = dice
        self._planetoid = None

    def spawn(self) -> None:
        guid = self._planetoid_template.object_guid

        world_owner_cards = self.catalogue.world_owner_cards(guid)

        planetoid = self._object_forge.hatch_planetoid(self._planetoid_template)
        planetoid.fresh_mover(self._planetoid_template.transform_of())

        self._join_queue.admit_object(planetoid)

        self._planetoid = planetoid

        is_server_just_restarted = self._spawn_runner.tick.seconds_since_start < 60.0
        respawn_resource_time = 1 if is_server_just_restarted else self._planetoid_desc.respawn_resource_time

        self._spawn_subscriber.on_spawn(self.follow_up(), respawn_resource_time)
        self._spawn_runner.template_by_object[planetoid.id_in_space()] = \
            PlacedObject(self._planetoid_template, planetoid)

    def follow_up(self):
        return PlanetoidResourceRule(
            self._spawn_runner, self._item_picker, self._planetoid_desc, self._loot_ownership,
            self._planetoid, self._dice)


class SpawnRunner(DueList, DepartureWatcher):
    def __init__(self, teruletek, sector_desc, tick, object_forge, arrival_gate,
                 loot_ownership, objektumok):
        template_by_object = {}
        DueList.__init__(self)
        self._areas = teruletek
        self._sector_desc = sector_desc
        self._template_by_object = template_by_object
        self._asteroid_item_picker = WeightedPick()
        self._object_forge = object_forge
        self._join_queue = arrival_gate
        self._space_objects = objektumok
        for resource_entry in sector_desc.asteroid_desc.resource_entries:
            self._asteroid_item_picker.add(resource_entry, resource_entry.chance)
        self._planetoid_item_picker = WeightedPick()
        for resource_entry in sector_desc.planetoid_desc.resource_entries:
            self._planetoid_item_picker.add(resource_entry, resource_entry.chance)
        self._tick = tick
        self._loot_ownership = loot_ownership
        self._random = Dice()

    @property
    def sector_desc(self):
        return self._sector_desc

    @property
    def template_by_object(self):
        return self._template_by_object

    @property
    def tick(self):
        return self._tick

    @property
    def asteroid_probability_chooser(self):
        return self._asteroid_item_picker

    def on_spawn(self, kovetkezo_kelthet, kelt_ekkor: float) -> None:
        DueList.enqueue(self, self._tick.copy(), kovetkezo_kelthet, kelt_ekkor)

    @property
    def planetoid_probability_chooser(self):
        return self._planetoid_item_picker

    SZULETESEK = {
        ObjectKind.Asteroid: lambda self, sablon: AsteroidRule(sablon, self.sector_desc, self, self._object_forge, self._join_queue, self.asteroid_probability_chooser, self._loot_ownership, self._random),
        ObjectKind.Planetoid: lambda self, sablon: PlanetoidRule(sablon, self.sector_desc, self, self._object_forge, self._join_queue, self.planetoid_probability_chooser, self._loot_ownership, self._random),
        ObjectKind.WeaponPlatform: lambda self, sablon: PlatformRule(sablon, self, self._object_forge, self._join_queue),
        ObjectKind.BotFighter: lambda self, sablon: DynamicNpcRule(sablon, self, self._object_forge, self._join_queue, self._random),
        ObjectKind.Cruiser: lambda self, sablon: CruiserRule(sablon, self, self._object_forge, self._join_queue),
    }

    def spawn_for(self, objektum_sablon):
        epito = self.SZULETESEK.get(objektum_sablon.space_entity_type)
        if epito is None:
            raise ValueError(
                f"nothing spawns a {objektum_sablon.space_entity_type}")
        return epito(self, objektum_sablon)

    def all_timeout_items(self, current=None):
        if current is None:
            return DueList.all_timeout_items(self, self.tick)
        return DueList.all_timeout_items(self, current)

    def timeout_items(self, current=None, max_items: int = 0):
        if current is None:
            return DueList.timeout_items(self, self.tick, max_items)
        return DueList.timeout_items(self, current, max_items)

    def due_item(self, current=None):
        if current is None:
            return DueList.due_item(self, self.tick)
        return DueList.due_item(self, current)

    def has_timeout_items(self, current=None) -> bool:
        if current is None:
            return DueList.has_timeout_items(self, self.tick)
        return DueList.has_timeout_items(self, current)

    def enqueue(self, spawnable, kelt_ekkor: float) -> None:
        DueList.enqueue(self, self.tick, spawnable, kelt_ekkor)

    @property
    def loot_ownership(self):
        return self._loot_ownership

    def asteroid_distribution(self) -> AsteroidYield:
        nyersanyag_szerint: Counter[int] = Counter()
        osszes = ures = 0
        for tarolo in self.template_by_object.values():
            aszteroida = tarolo.space_object
            if aszteroida.space_entity_type != ObjectKind.Asteroid:
                continue
            osszes += 1
            van_zsakmany = self._loot_ownership.carries_loot(aszteroida)
            zsakmany = self._loot_ownership.get(aszteroida)
            if not van_zsakmany:
                ures += 1
            elif isinstance(zsakmany, AsteroidSpoils):
                nyersanyag_szerint[zsakmany.ressource.card_guid_of()] += 1
        return AsteroidYield(osszes, ures,
                             nyersanyag_szerint[ResourceKind.Tylium.guid],
                             nyersanyag_szerint[ResourceKind.Titanium.guid],
                             nyersanyag_szerint[ResourceKind.Water.guid])

    def on_update(self, arg) -> None:
        obj = arg.departed_object
        removing_cause = arg.removal_cause_of()

        if obj.is_player():
            return

        paros = self.template_by_object.pop(obj.id_in_space(), None)
        if paros is None:
            return

        associated_template = paros.template
        if removing_cause == DepartureCause.Death:
            spawn_able = self.spawn_for(associated_template)
            self.enqueue(spawn_able, associated_template.respawn_time)
        elif removing_cause == DepartureCause.JumpOut:
            spawn_able = self.spawn_for(associated_template)
            self.enqueue(spawn_able, associated_template.respawn_time_jump_out)
