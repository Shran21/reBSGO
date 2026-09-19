# github.com/Shran21

from __future__ import annotations

import logging
import threading
from rebsgo.vocabulary.world import WellKnownCard, DepartureCause, ObjectKind
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.world.sectors.running.coming_and_going import LastPositionKey
from rebsgo.world.objects.ships import Ship
from rebsgo.geometry.primitives.transform import Transform
from rebsgo.vocabulary.pilot import Faction


log = logging.getLogger(__name__)


def _leallit_es_megvar(vegrehajto) -> None:
    if vegrehajto is None:
        return
    try:
        vegrehajto.shutdown(wait=True)
    except TypeError:
        vegrehajto.shutdown()
    except Exception:
        pass


class SectorBook:
    def __init__(self, sector_source, catalogue, merok, sorsolo,
                 utemezo):
        self._sector_source = sector_source
        self._catalogue = catalogue
        self._is_shutdown = False
        self._merok = merok

        self._executor_service = utemezo
        self._lock = threading.Lock()
        self._sector_map = {}
        self._zones_map = {}
        self._started = False
        self._sector_random_generation_utils = sorsolo
        try:
            self.open_standard_sectors()
        except Exception:
            log.exception("SectorBook failed during setup_standard_sectors(); continuing with 0 sectors.")

    def open_standard_sectors(self) -> None:
        map_card = self._catalogue.card_of(WellKnownCard.GalaxyMap, CardView.GalaxyMap)
        if map_card is None:
            return

        for map_star in map_card.stars.values():
            id = map_star.id
            try:
                tmp_sector = self._sector_source.open_sector(id)
                self._merok.watch_sector_headcount(tmp_sector)
                self.register_sector(tmp_sector)
            except Exception:
                log.exception('sector id=%s refused to start and stays offline', id)

    def start_zone(self, zone_guid: int) -> None:
        zone_card = self._catalogue.card_of(zone_guid, CardView.Zone)

    def register_sector(self, sector) -> None:
        if self._is_shutdown:
            raise RuntimeError("SectorBook is shutdown, no new sectors available!")
        with self._lock:
            self._sector_map[sector.id] = sector
            should_start = self._started
        if should_start:
            self._executor_service.launch(sector.run)

    def start_all_sectors(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            sectors = list(self._sector_map.values())
        for sector in sectors:
            self._executor_service.launch(sector.run)

    def sector_by_id(self, id: int):
        with self._lock:
            return self._sector_map.get(id)

    def restart_sector(self, id: int):
        with self._lock:
            old = self._sector_map.get(id)
        if old is None or self._is_shutdown:
            return None
        fresh = self._sector_source.open_sector(id)
        self._merok.watch_sector_headcount(fresh)
        with self._lock:
            self._sector_map[id] = fresh
            should_start = self._started
        if should_start:
            self._executor_service.launch(fresh.run)
        old.close_sector()
        return fresh

    def sectors(self):
        with self._lock:
            return [sector for _id, sector in sorted(self._sector_map.items())]

    @property
    def sector_source(self):
        return self._sector_source

    @property
    def sector_random_generation_utils(self):
        return self._sector_random_generation_utils

    def shutdown(self) -> None:
        self._is_shutdown = True
        with self._lock:
            sectors = list(self._sector_map.values())
        for sector in sectors:
            sector.close_sector()
        _leallit_es_megvar(self._executor_service)


_ALL_TYPES = list(ObjectKind)


class SectorObjects:
    def __init__(self):
        space_objects_by_object_id = {}
        space_entity_type_objects = {}
        transform_by_old_user_position = {}
        static_added_space_objects = set()
        self._space_objects_by_object_id = space_objects_by_object_id
        self._space_entity_type_objects = space_entity_type_objects
        self._transform_by_old_user_position = transform_by_old_user_position

        for space_entity_type in _ALL_TYPES:
            self._space_entity_type_objects[space_entity_type] = {}
        self._static_added_space_objects = static_added_space_objects
        self._cache_version = 0
        self._cached_all_values_version = -1
        self._cached_all_values = ()
        self._cached_ships_version = -1
        self._cached_ships = ()
        self._cached_types = {}
        self._cached_not_types = {}
        self._player_object_by_player_id = {}
        for obj in self._space_objects_by_object_id.values():
            self._track_player_object(obj)

    def by_player_id(self, player_id: int):
        return self._player_object_by_player_id.get(player_id)

    def add(self, space_object) -> None:
        elozo = self._space_objects_by_object_id.get(space_object.id_in_space())
        if elozo is not None:
            self._untrack_player_object(elozo)
        self._space_objects_by_object_id[space_object.id_in_space()] = space_object
        if elozo is not None:
            log.error("Previous WorldObject was megvan, critical error! %s %s",
                      elozo.id_in_space(), elozo.space_entity_type)
        existing = self._space_entity_type_objects[space_object.space_entity_type]
        existing[space_object.id_in_space()] = space_object
        if not space_object.mover_of().is_moving_object:
            self._static_added_space_objects.add(space_object.id_in_space())
        self._track_player_object(space_object)
        self._invalidate_cache()

    def get(self, id_: int):
        return self._space_objects_by_object_id.get(id_)

    def values(self):
        if self._cached_all_values_version != self._cache_version:
            self._cached_all_values = tuple(self._space_objects_by_object_id.values())
            self._cached_all_values_version = self._cache_version
        return self._cached_all_values

    @property
    def pairs(self):
        return self._space_objects_by_object_id.items()

    def remove(self, arg, removing_cause):
        object_id = arg if isinstance(arg, int) else arg.id_in_space()
        self._static_added_space_objects.discard(object_id)
        containing_obj = self._space_objects_by_object_id.get(object_id)
        if containing_obj is not None:
            del self._space_objects_by_object_id[object_id]
            self._space_entity_type_objects[containing_obj.space_entity_type].pop(object_id, None)
            self._untrack_player_object(containing_obj)
            self._invalidate_cache()

        if containing_obj is not None and containing_obj.is_player():
            self._transform_by_old_user_position.pop(
                LastPositionKey(containing_obj.pilot_id(), containing_obj.faction), None)
            if removing_cause == DepartureCause.Dock:
                self._transform_by_old_user_position[
                    LastPositionKey(containing_obj.pilot_id(), containing_obj.faction)] = Transform(
                        containing_obj.mover_of().position_of(),
                        containing_obj.mover_of().rotation_of(),
                        True)

        return containing_obj

    def space_objects_of_entity_type(self, space_entity_type):
        cache_key = (space_entity_type,)
        cached = self._cached_types.get(cache_key)
        if cached is None or cached[0] != self._cache_version:
            cached = (self._cache_version, tuple(self._space_entity_type_objects[space_entity_type].values()))
            self._cached_types[cache_key] = cached
        return list(cached[1])

    def objects_of_kind(self, space_entity_type):
        return self._space_entity_type_objects[space_entity_type].values()

    def space_objects_of_entity_types(self, *types):
        cache_key = tuple(types)
        cached = self._cached_types.get(cache_key)
        if cached is None or cached[0] != self._cache_version:
            cached_values = []
            for type_ in types:
                cached_values.extend(self._space_entity_type_objects[type_].values())
            cached = (self._cache_version, tuple(cached_values))
            self._cached_types[cache_key] = cached
        return list(cached[1])

    def objects_among_kinds(self, *types):
        yield from self._get_space_objects_of_entity_types_tuple(*types)

    @property
    def space_objects_of_type_ship(self):
        return self.space_objects_of_entity_types(*ObjectKind.ship_types())

    def ships_stream_of(self):
        yield from self._get_ships_tuple()

    def space_objects_not_of_entity_type(self, *space_entity_types):
        if len(space_entity_types) == 0:
            return []
        return list(self._get_space_objects_not_of_entity_type_tuple(*space_entity_types))

    def objects_other_than(self, *space_entity_types):
        if len(space_entity_types) == 0:
            return
        yield from self._get_space_objects_not_of_entity_type_tuple(*space_entity_types)

    def size(self) -> int:
        return len(self._space_objects_by_object_id)

    def ship_by_object_id(self, object_id: int):
        sp_obj = self.get(object_id)
        if sp_obj is None:
            return None
        if isinstance(sp_obj, Ship):
            return sp_obj
        return None

    @property
    def transform_by_old_user_position(self):
        return self._transform_by_old_user_position

    def follow_missiles(self, space_object):
        return [m for m in self.space_objects_of_entity_type(ObjectKind.Missile)
                if m.missile_launched_on_object is not None
                and m.missile_launched_on_object == space_object]

    def drop_and_stage_static(self, object_id: int) -> bool:
        if object_id in self._static_added_space_objects:
            self._static_added_space_objects.remove(object_id)
            return True
        return False

    def _invalidate_cache(self) -> None:
        self._cache_version += 1

    def _get_ships_tuple(self):
        if self._cached_ships_version != self._cache_version:
            self._cached_ships = self._get_space_objects_of_entity_types_tuple(*ObjectKind.ship_types())
            self._cached_ships_version = self._cache_version
        return self._cached_ships

    def _get_space_objects_of_entity_types_tuple(self, *types):
        cache_key = tuple(types)
        cached = self._cached_types.get(cache_key)
        if cached is None or cached[0] != self._cache_version:
            cached_values = []
            for type_ in types:
                cached_values.extend(self._space_entity_type_objects[type_].values())
            cached = (self._cache_version, tuple(cached_values))
            self._cached_types[cache_key] = cached
        return cached[1]

    def _get_space_objects_not_of_entity_type_tuple(self, *space_entity_types):
        cache_key = tuple(space_entity_types)
        cached = self._cached_not_types.get(cache_key)
        if cached is None or cached[0] != self._cache_version:
            excluded_types = set(space_entity_types)
            cached_values = []
            for space_entity_type in _ALL_TYPES:
                if space_entity_type in excluded_types:
                    continue
                cached_values.extend(self._space_entity_type_objects[space_entity_type].values())
            cached = (self._cache_version, tuple(cached_values))
            self._cached_not_types[cache_key] = cached
        return cached[1]

    def _track_player_object(self, space_object) -> None:
        is_player = getattr(space_object, "is_player", None)
        if callable(is_player) and is_player():
            self._player_object_by_player_id[space_object.pilot_id()] = space_object

    def _untrack_player_object(self, space_object) -> None:
        is_player = getattr(space_object, "is_player", None)
        if not (callable(is_player) and is_player()):
            return
        player_id = space_object.pilot_id()
        if self._player_object_by_player_id.get(player_id) is space_object:
            self._player_object_by_player_id.pop(player_id, None)


class SectorPilots:
    def __init__(self):
        users_by_user_id = {}
        ship_of_pilot = {}
        player_ships_by_object_id = {}
        user_ids_with_spawned_objects = set()
        self._users_by_user_id = users_by_user_id
        self._ship_of_pilot = ship_of_pilot
        self._player_ships_by_object_id = player_ships_by_object_id
        self._user_ids_with_spawned_objects = user_ids_with_spawned_objects

    def add(self, user, player_ship) -> None:
        user_id = user.pilot_of().user_id_of()
        self._users_by_user_id[user_id] = user
        self._ship_of_pilot[user_id] = player_ship
        self._player_ships_by_object_id[player_ship.id_in_space()] = player_ship

    def remove(self, user_id: int):
        if user_id < 0:
            return None

        removed_user = self._users_by_user_id.pop(user_id, None)
        if (removed_ship := self._ship_of_pilot.pop(user_id, None)) is not None:
            self._player_ships_by_object_id.pop(removed_ship.id_in_space(), None)
        self.clear_join_flag(user_id)
        return removed_user

    def user(self, arg):
        if isinstance(arg, int):
            return self._users_by_user_id.get(arg)
        if not arg.is_player():
            return None
        return self.user(arg.pilot_id())

    def user_unsafe(self, user_id: int):
        return self._users_by_user_id.get(user_id)

    def player_ship_unsafe(self, user_id: int):
        return self._ship_of_pilot.get(user_id)

    def ship_of_pilot(self, user_id: int):
        return self._ship_of_pilot.get(user_id)

    @property
    def empty(self) -> bool:
        return len(self._users_by_user_id) == 0

    def users_of(self):
        return self._users_by_user_id.values()

    def user_cnt_based_on_faction(self, faction) -> int:
        if faction is Faction.Cylon or faction is Faction.Colonial:
            return sum(1 for user in list(self._users_by_user_id.values())
                       if user.pilot_of().faction == faction)
        return len(self._users_by_user_id)

    def users(self):
        return list(self._users_by_user_id.values())

    def player_ships(self):
        return list(self._ship_of_pilot.values())

    @property
    def player_ships_collection(self):
        return self._ship_of_pilot.values()

    def player_ship_by_space_object_id(self, object_id: int):
        return self._player_ships_by_object_id.get(object_id)

    def note_arrival_of(self, user_id: int) -> None:
        self._user_ids_with_spawned_objects.add(user_id)

    def clear_join_flag(self, user_id: int) -> None:
        self._user_ids_with_spawned_objects.discard(user_id)
