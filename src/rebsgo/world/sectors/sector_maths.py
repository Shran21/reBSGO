# github.com/Shran21

from __future__ import annotations

from rebsgo.vocabulary.world import DepartureCause, ObjectKind


def clear_asteroids(sector) -> None:
    for ertek in sector.ctx.space_objects().values():
        if ertek.space_entity_type != ObjectKind.Asteroid:
            continue

        sector.departures_desk.note_removal_cause(ertek, DepartureCause.Death)


def clear_non_player(sector) -> None:
    all_non_player_objects = sector.ctx.space_objects().space_objects_not_of_entity_type(
        ObjectKind.Pilot)
    for ertek in all_non_player_objects:
        sector.departures_desk.note_removal_cause(ertek, DepartureCause.Death)


def remove_colliding_asteroids(sector) -> None:
    remover = sector.departures_desk
    objektumok = sector.ctx.space_objects()
    aszteroidak = objektumok.space_objects_of_entity_type(ObjectKind.Asteroid)
    egyebek = objektumok.space_objects_of_entity_types(
        ObjectKind.Planetoid, ObjectKind.Outpost)

    egymasba, mas_utjaban = [], []
    for i, aszteroida in enumerate(aszteroidak):
        for masik in aszteroidak[i + 1:]:
            if _osszeernek(aszteroida, masik):
                egymasba.append((aszteroida, masik))
        for egyeb in egyebek:
            if _osszeernek(aszteroida, egyeb):
                mas_utjaban.append(aszteroida)

    for aszteroida in mas_utjaban:
        remover.note_removal_cause(aszteroida, DepartureCause.Death)
    for elso, masodik in egymasba:
        if not elso.is_removed() and not masodik.is_removed():
            remover.note_removal_cause(elso, DepartureCause.Death)


def _osszeernek(elso, masodik) -> bool:
    return elso.collider_of().overlaps(masodik.collider_of())
