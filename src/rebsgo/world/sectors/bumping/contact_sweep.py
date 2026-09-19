# github.com/Shran21
from __future__ import annotations

import itertools

import logging

from rebsgo.config.config import Config
from rebsgo.world.sectors.bumping.hit import Hit
from rebsgo.world.sectors.bumping.contact_pair import ContactPair
from rebsgo.world.sectors.spatial.uniform_grid import UniformGridSpatialIndex
from rebsgo.world.sectors.sector_parts import SectorStep
from rebsgo.vocabulary.world import ObjectKind
from rebsgo.native.hotpath import filter_sphere_pair_indices, log_native_event

log = logging.getLogger(__name__)

_CONFIG = Config.instance()
_SPATIAL_INDEX_ENABLED = _CONFIG.bool("rebsgo.sector.spatial-index.enabled", True)
_SPATIAL_INDEX_CELL_SIZE = _CONFIG.float("rebsgo.sector.spatial-index.cell-size", 5000.0)
_SPATIAL_INDEX_MIN_OBJECTS = _CONFIG.int("rebsgo.sector.spatial-index.min-objects", 32)
_SPATIAL_INDEX_MAX_CELLS_PER_OBJECT = _CONFIG.int(
    "rebsgo.sector.spatial-index.max-cells-per-object", 512)
_SPATIAL_INDEX_PRIMITIVE_ENABLED = _CONFIG.bool("rebsgo.sector.spatial-index.primitive-enabled", True)


class ContactSweep(SectorStep):
    def __init__(self, sector_objects, utkozes_feloldas, metszes_szuro, tick):
        self._space_objects = sector_objects
        self._collision_resolution = utkozes_feloldas
        self._intersection_filter = metszes_szuro
        self._tick = tick
        self._last_stats = {
            "candidate_objects": 0,
            "moving_colliders": 0,
            "contact_pairs": 0,
            "contact_collisions": 0,
            "primitive_pairs": 0,
            "spatial_enabled": 0,
            "spatial_cells": 0,
            "spatial_global_objects": 0,
            "spatial_raw_pairs": 0,
            "primitive_spatial_enabled": 0,
            "primitive_probe_objects": 0,
            "primitive_target_objects": 0,
            "primitive_candidate_pairs": 0,
            "sphere_pair_candidates": 0,
            "sphere_pair_rejected": 0,
        }

    def _prepare_pairs_plain(self, objects):
        utkozok = [o for o in objects if o.collider_of() is not None]
        collision_pairs = [ContactPair(a, b)
                           for a, b in itertools.combinations(utkozok, 2)
                           if self._intersection_filter.worth_testing(a, b)]

        self._last_stats["spatial_enabled"] = 0
        self._last_stats["spatial_cells"] = 0
        self._last_stats["spatial_global_objects"] = 0
        self._last_stats["spatial_raw_pairs"] = len(collision_pairs)
        return collision_pairs

    def _prepare_pairs_to_check2(self):
        objects = self._space_objects.space_objects_not_of_entity_type(
            ObjectKind.Asteroid, ObjectKind.Missile, ObjectKind.Comet)
        meret = len(objects)

        if not _SPATIAL_INDEX_ENABLED or meret < _SPATIAL_INDEX_MIN_OBJECTS:
            collision_pairs = self._prepare_pairs_plain(objects)
        else:
            try:
                sorszam = UniformGridSpatialIndex(_SPATIAL_INDEX_CELL_SIZE, _SPATIAL_INDEX_MAX_CELLS_PER_OBJECT)
                sorszam.rebuild(objects)
                pairs, mutatok = sorszam.pairs(self._intersection_filter.worth_testing)
                collision_pairs = [ContactPair(elso, second) for elso, second in pairs]
                self._last_stats["spatial_enabled"] = 1
                self._last_stats["spatial_cells"] = mutatok.cells
                self._last_stats["spatial_global_objects"] = mutatok.global_objects
                self._last_stats["spatial_raw_pairs"] = mutatok.raw_pairs
            except Exception:
                log.exception("Spatial collision broadphase failed; falling back to legacy pair scan")
                collision_pairs = self._prepare_pairs_plain(objects)

        self._last_stats["candidate_objects"] = meret
        self._last_stats["contact_pairs"] = len(collision_pairs)
        return collision_pairs

    def _actual_collision_check(self, pairs_to_check):
        pairs_collided = []
        sphere_pair_records = []
        sphere_pair_indexes = set()

        for sorszam, collision_pair in enumerate(pairs_to_check):
            first_collider = collision_pair.first().collider_of()
            second_collider = collision_pair.second().collider_of()
            if first_collider is None or second_collider is None:
                continue
            sphere_record = self._sphere_pair_record(sorszam, first_collider, second_collider)
            if sphere_record is not None:
                sphere_pair_records.append(sphere_record)
                sphere_pair_indexes.add(sorszam)

        if sphere_pair_records:
            try:
                overlapping_sphere_indexes = set(filter_sphere_pair_indices(sphere_pair_records))
            except Exception:
                log.exception("Native sphere collision prefilter failed; falling back to full sphere narrowphase")
                overlapping_sphere_indexes = sphere_pair_indexes
        else:
            overlapping_sphere_indexes = set()
        self._last_stats["sphere_pair_candidates"] = len(sphere_pair_records)
        self._last_stats["sphere_pair_rejected"] = max(0, len(sphere_pair_records) - len(overlapping_sphere_indexes))
        if sphere_pair_records:
            log_native_event(
                log,
                "collision_sphere_pair_filter_used",
                "Collision sphere-pair filter candidates=%s rejected=%s",
                len(sphere_pair_records),
                max(0, len(sphere_pair_records) - len(overlapping_sphere_indexes)),
            )

        for sorszam, collision_pair in enumerate(pairs_to_check):
            if sorszam in sphere_pair_indexes and sorszam not in overlapping_sphere_indexes:
                continue
            first_collider = collision_pair.first().collider_of()
            second_collider = collision_pair.second().collider_of()
            if first_collider is None or second_collider is None:
                continue
            collision_record = first_collider.touch(second_collider)

            if collision_record is not None:
                pairs_collided.append(Hit(collision_record, collision_pair.first(), collision_pair.second()))

        return pairs_collided

    @staticmethod
    def _sphere_pair_record(index: int, first_collider, second_collider):
        if not (
                hasattr(first_collider, "center_point")
                and hasattr(first_collider, "radius_of")
                and hasattr(second_collider, "center_point")
                and hasattr(second_collider, "radius_of")):
            return None
        first_center = first_collider.center_point()
        second_center = second_collider.center_point()
        return (
            int(index),
            float(first_center.x),
            float(first_center.y),
            float(first_center.z),
            float(first_collider.radius_of()),
            float(second_center.x),
            float(second_center.y),
            float(second_center.z),
            float(second_collider.radius_of()),
        )

    def run(self) -> None:
        moving_colliders = self.begin_collision_pass()
        primitive_results = self.primitive_collision_results
        contact_results = self._get_collision_results()

        self._collision_resolution.move_clock_to(self._tick.copy())
        self._collision_resolution.attach_contact_details(primitive_results, contact_results)
        self._collision_resolution.resolve_all()
        self._last_stats["moving_colliders"] = moving_colliders
        self._last_stats["primitive_pairs"] = len(primitive_results)
        self._last_stats["contact_collisions"] = len(contact_results)

    def begin_collision_pass(self) -> int:
        moving_colliders = 0
        for space_object in self._space_objects.objects_other_than(
                ObjectKind.Asteroid, ObjectKind.Planetoid, ObjectKind.Planet, ObjectKind.Debris):
            if not space_object.mover_of().is_moving_object:
                continue
            if (utkozotest := space_object.collider_of()) is not None:
                utkozotest.sync_to_transform()
                moving_colliders += 1
        return moving_colliders

    def _get_collision_results(self):
        pairs_to_check = self._prepare_pairs_to_check2()
        return self._actual_collision_check(pairs_to_check)

    def _primitive_check(self):
        parosok = []
        raketak = self._space_objects.space_objects_of_entity_type(ObjectKind.Missile)

        asteroids = self._space_objects.space_objects_of_entity_type(ObjectKind.Asteroid)
        players_and_comets = self._space_objects.space_objects_of_entity_types(
            ObjectKind.Pilot, ObjectKind.Comet)
        primitive_candidate_pairs = 0
        primitive_spatial_enabled = False

        asteroid_player_comet_pairs = self._primitive_candidate_pairs(asteroids, players_and_comets)
        if asteroid_player_comet_pairs is not None:
            primitive_spatial_enabled = True
            for asteroid, player_comet in asteroid_player_comet_pairs:
                primitive_candidate_pairs += 1
                eredmeny = self._check_primitive(asteroid, player_comet)
                if eredmeny is not None:
                    parosok.append(eredmeny)
        else:
            for asteroid in asteroids:
                for player_comet in players_and_comets:
                    primitive_candidate_pairs += 1
                    eredmeny = self._check_primitive(asteroid, player_comet)
                    if eredmeny is not None:
                        parosok.append(eredmeny)

        comets = self._space_objects.space_objects_of_entity_type(ObjectKind.Comet)
        for comet_outer in comets:
            for comet_inner in comets:
                if comet_inner is comet_outer:
                    continue

                primitive_candidate_pairs += 1
                eredmeny = self._check_primitive(comet_outer, comet_inner)
                if eredmeny is not None:
                    parosok.append(eredmeny)

        test_against_missiles = self._space_objects.space_objects_of_type_ship
        test_against_missiles.extend(self._space_objects.space_objects_of_entity_types(
            ObjectKind.Planetoid, ObjectKind.Comet, ObjectKind.Debris))

        missile_pairs = self._primitive_candidate_pairs(
            raketak, test_against_missiles, self._intersection_filter.test_missile_primitive)
        if missile_pairs is not None:
            primitive_spatial_enabled = True
            for raketa, space_object in missile_pairs:
                primitive_candidate_pairs += 1
                eredmeny = self._check_primitive(raketa, space_object)
                if eredmeny is not None:
                    parosok.append(eredmeny)
        else:
            for raketa in raketak:
                for space_object in test_against_missiles:
                    primitive_candidate_pairs += 1
                    needs_intersection = self._intersection_filter.test_missile_primitive(raketa, space_object)
                    if needs_intersection:
                        eredmeny = self._check_primitive(raketa, space_object)
                        if eredmeny is not None:
                            parosok.append(eredmeny)

        self._last_stats["primitive_spatial_enabled"] = 1 if primitive_spatial_enabled else 0
        self._last_stats["primitive_probe_objects"] = len(asteroids) + len(raketak)
        self._last_stats["primitive_target_objects"] = len(players_and_comets) + len(test_against_missiles)
        self._last_stats["primitive_candidate_pairs"] = primitive_candidate_pairs
        return parosok

    def _primitive_candidate_pairs(self, probes, targets, needs_pair=None):
        if not _SPATIAL_INDEX_ENABLED or not _SPATIAL_INDEX_PRIMITIVE_ENABLED:
            return None
        if not probes or not targets:
            return []
        if len(probes) * len(targets) < _SPATIAL_INDEX_MIN_OBJECTS:
            return None
        try:
            if needs_pair is None:
                needs_pair = lambda _first, _second: True
            sorszam = UniformGridSpatialIndex(_SPATIAL_INDEX_CELL_SIZE, _SPATIAL_INDEX_MAX_CELLS_PER_OBJECT)
            sorszam.rebuild(targets)
            parosok = []
            for probe in probes:
                for celpont in sorszam.query_overlaps(probe, needs_pair):
                    parosok.append((probe, celpont))
            return parosok
        except Exception:
            log.exception("Spatial primitive broadphase failed; falling back to legacy primitive scan")
            return None

    @staticmethod
    def _check_primitive(elso, masodik):
        elso_test = elso.collider_of()
        masodik_test = masodik.collider_of()
        if elso_test is None or masodik_test is None:
            return None
        return ContactPair(elso, masodik) if elso_test.overlaps(masodik_test) else None

    @property
    def primitive_collision_results(self):
        return self._primitive_check()

    def last_stats(self) -> dict:
        return dict(self._last_stats)
