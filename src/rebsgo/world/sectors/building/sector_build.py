# github.com/Shran21

from __future__ import annotations

from contextlib import suppress
from rebsgo.world.sectors.building.spawners import AsteroidBelt
from rebsgo.vocabulary.world import ArrivalCause, ObjectKind
from rebsgo.geometry.primitives.euler3 import Euler3
from rebsgo.geometry.primitives.quaternion import Quaternion
from rebsgo.geometry.primitives.transform import Transform
from rebsgo.geometry.primitives.vector3 import Vector3
from rebsgo.gamedata.object_templates import AsteroidSpec, PlanetoidSpec
from rebsgo.helpers.floats import f32, fdiv


class SectorServices:
    def __init__(self, tick, pilotak, objektumok, dice, sender, terv, id_nyilvantarto,
                 object_forge, outpost_scoreboard, loot_ownership):
        self._tick = tick
        self._users = pilotak
        self._space_objects = objektumok
        self._dice = dice
        self._sender = sender
        self._blueprint = terv
        self._id_registry = id_nyilvantarto
        self._object_forge = object_forge
        self._outpost_scoreboard = outpost_scoreboard
        self._loot_ownership = loot_ownership

    def tick(self):
        return self._tick

    def users(self):
        return self._users

    def space_objects(self):
        return self._space_objects

    def dice(self):
        return self._dice

    def sender(self):
        return self._sender

    def blueprint(self):
        return self._blueprint

    @property
    def id_registry(self):
        return self._id_registry

    @property
    def object_forge(self):
        return self._object_forge

    @property
    def outpost_scoreboard(self):
        return self._outpost_scoreboard

    @property
    def loot_ownership(self):
        return self._loot_ownership


class SectorScatter:
    def __init__(self, catalogue):
        self._catalogue = catalogue

    def scatter_sector_objects(self, sector, kocka,
                               aszteroidak_szama: int, planetoida_darab: int,
                               mezok_szama: int, mezonkenti_darab: int, mezo_merete: int,
                               loop_count: int, koronkent: int, koronkenti_darab: int) -> None:
        factory = sector.ctx.object_forge
        planetoida_kartyak = self._catalogue.all_world_cards_of_prefab_start_with("planetoid")
        aszteroida_kartyak = [world_card for world_card in self._catalogue.all_asteroid_world_cards
                              if "field" not in world_card.prefab_name]

        sector_card = sector.ctx.blueprint().sector_cards().sector_card
        fel_magassag = f32(sector_card.height * 0.5)
        fel_hossz = f32(sector_card.length * 0.5)
        fel_szelesseg = f32(sector_card.width * 0.5)

        def barhol() -> Vector3:
            return Vector3(kocka.between(-fel_szelesseg, fel_szelesseg),
                           kocka.between(f32(-fel_magassag / 2), f32(fel_magassag / 2)),
                           kocka.between(-fel_hossz, fel_hossz))

        planetoidak = [self._planetoida(factory, kocka, planetoida_kartyak, barhol())
                       for _ in range(planetoida_darab)]

        aszteroidak = []
        for planetoida in planetoidak:
            aszteroidak.extend(self._planetoida_gyuruje(
                factory, kocka, aszteroida_kartyak, planetoida, aszteroidak_szama))
        for _ in range(mezok_szama):
            aszteroidak.extend(self._aszteroida_mezo(
                factory, kocka, aszteroida_kartyak, barhol(),
                aszteroidak_szama, mezonkenti_darab, mezo_merete))
        for _ in range(loop_count):
            aszteroidak.extend(self._aszteroida_hurok(
                factory, kocka, aszteroida_kartyak, barhol(), koronkenti_darab, koronkent))

        for space_object in planetoidak + aszteroidak:
            sector.arrival_gate.admit_object(space_object)

    @staticmethod
    def _planetoida(factory, kocka, kartyak, hol):
        sablon = PlanetoidSpec(kocka.pick(kartyak).card_guid_of(),
                               ObjectKind.Planetoid, ArrivalCause.AlreadyExists, 1, True,
                               hol, Euler3.zero(), 1, 0)
        planetoida = factory.hatch_planetoid(sablon)
        planetoida.fresh_mover(sablon.transform_of())
        return planetoida

    @staticmethod
    def _veletlen_aszteroida(factory, kocka, kartyak, hol):
        sablon = AsteroidSpec(kocka.pick(kartyak).card_guid_of(),
                              ObjectKind.Asteroid, ArrivalCause.AlreadyExists, 1, True,
                              hol, Euler3.zero(), kocka.between(30.0, 150.0), 0)
        return factory.hatch_asteroid(sablon, f32(kocka.between_whole(300, 5000)))

    def _planetoida_gyuruje(self, factory, kocka, kartyak, planetoida, aszteroidak_szama):
        kozel = f32(kocka.between_whole(1100, 1300))
        tavol = kocka.between(kozel, f32(kozel + kocka.between_whole(300, 700)))
        kozeppont = planetoida.mover_of().transform_of()

        gyuru = []
        for i in range(aszteroidak_szama):
            helyben = Vector3(kocka.between(kozel, tavol), kocka.between_whole(-300, 300), 0)
            fordulat = Euler3(0, f32(360.0 / f32(aszteroidak_szama)) * i, 0)
            gyuru.append(self._veletlen_aszteroida(
                factory, kocka, kartyak,
                kozeppont.through_transform(fordulat.quaternion.mult_(helyben))))
        return gyuru

    def _aszteroida_mezo(self, factory, kocka, kartyak, kozeppont,
                         aszteroidak_szama, mezonkenti_darab, mezo_merete):
        forog_x = f32(kocka.between_whole(0, 4))
        forog_y = f32(kocka.between_whole(0, 4))
        forog_z = f32(kocka.between_whole(0, 4))
        if forog_x == 0 and forog_y == 0 and forog_z == 0:
            forog_x = 1

        kozep_transform = Transform(kozeppont, Euler3(0, 0, 0).quaternion)
        mezo = []
        for hanyadik in range(mezonkenti_darab):
            helyben = Vector3.zero()
            helyben.add_x(f32(f32(fdiv(f32(mezo_merete), f32(aszteroidak_szama))) * hanyadik))

            def szog(mennyit: float) -> float:
                teljes = f32(mennyit * 360.0)
                lepesenkent = f32(teljes / f32(mezonkenti_darab))
                return f32(lepesenkent * hanyadik)

            helyben.copy_from(Euler3(szog(forog_x), szog(forog_y), szog(forog_z)).quaternion.mult_(helyben))
            mezo.append(self._veletlen_aszteroida(
                factory, kocka, kartyak, kozep_transform.through_transform(helyben)))
        return mezo

    def _aszteroida_hurok(self, factory, kocka, kartyak, kozeppont, koronkenti_darab, koronkent):
        kozep_transform = Transform(kozeppont, Quaternion.identity())
        hurok = []
        for hanyadik in range(koronkenti_darab):
            helyben = Vector3()
            helyben.add_x(kocka.signed(koronkent))
            helyben.add_y(kocka.between_wide(-koronkent, koronkent))
            fordulat = Euler3(0, f32(360.0 / f32(koronkenti_darab)) * hanyadik, 0)
            hurok.append(self._veletlen_aszteroida(
                factory, kocka, kartyak,
                kozep_transform.through_transform(fordulat.quaternion.mult_(helyben))))
        return hurok

    def scatter_one(self, sector, csoport_kelthet) -> None:
        csoport_kelthet.create()
        children = csoport_kelthet.children()
        join_queue = sector.arrival_gate

        with suppress(Exception):
            parent = csoport_kelthet.parent()
            join_queue.admit_object(parent)
        for child in children:
            join_queue.admit_object(child)

    def scatter_ring(self, sector, random, spread_from_centre: int, aszteroida_darab: int,
                     min_distance: float, max_distance: float, angle_shift: float) -> None:
        asteroid_ring = AsteroidBelt(sector, aszteroida_darab, min_distance, max_distance, angle_shift, random, spread_from_centre)
        self.scatter_one(sector, asteroid_ring)
