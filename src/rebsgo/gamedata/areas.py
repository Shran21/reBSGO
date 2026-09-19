# github.com/Shran21

from __future__ import annotations

from dataclasses import dataclass

from rebsgo.gamedata import json_helper as jh
from rebsgo.vocabulary.sorszamos_enum import SorszamosEnum


class AreaGoalPointKind(SorszamosEnum):
    Pilot = 0
    Drone = 1
    Torpedo = 2
    Platform = 3
    MotherShip = 4


class AreaGoalTrigger(SorszamosEnum):
    ON_START = 0
    ON_OBJECTIVE_COMPLETE = 1
    ON_PLAYER_ENTER_RADIUS = 2
    ON_TIME_ELAPSED = 3


class GoalKind(SorszamosEnum):
    DESTROY = 0
    REACH_LOCATION = 1
    CAPTURE = 2


class Timetable:
    def __init__(self, utemezes, hossz_perc):
        self._cron_expression = utemezes
        self._duration_minutes = hossz_perc

    @classmethod
    def from_json(cls, obj: dict) -> "Timetable":
        return cls(jh.as_text(obj, "cronExpression"), jh.as_text(obj, "durationMinutes"))

    @property
    def cron_expression(self):
        return self._cron_expression

    @property
    def duration_minutes(self):
        return self._duration_minutes


class AreaGoalPoints:
    def __init__(self, terulet_cel_fajta, pts):
        self._zone_objective_pt_type = terulet_cel_fajta
        self._pts = pts

    @classmethod
    def from_json(cls, obj: dict) -> "AreaGoalPoints":
        return cls(jh.as_enum_by_name(obj, "zoneObjectivePtType", AreaGoalPointKind),
                   jh.as_long(obj, "pts"))

    @property
    def zone_objective_pt_type(self):
        return self._zone_objective_pt_type

    @property
    def pts(self):
        return self._pts

    def __eq__(self, other):
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self._zone_objective_pt_type == other._zone_objective_pt_type

    def __hash__(self):
        return hash(self._zone_objective_pt_type)


class DataAsset:
    def __init__(self, condition):
        self._condition = condition

    @classmethod
    def from_json(cls, obj: dict) -> "DataAsset":
        return cls(jh.as_enum_by_name(obj, "condition", AreaGoalTrigger))

    @property
    def condition(self):
        return self._condition


@dataclass(slots=True, eq=False)
class GoalSpec:
    objective_id: object
    type: object
    position: object
    radius: object
    description: object
    trigger_scripts: object
    next_objectives: object

    @classmethod
    def from_json(cls, obj: dict) -> "GoalSpec":
        raw_scripts = obj.get("triggerScripts")
        trigger_scripts = None if raw_scripts is None else [DataAsset.from_json(x) for x in raw_scripts]
        raw_next = obj.get("nextObjectives")
        next_objectives = None if raw_next is None else [cls.from_json(x) for x in raw_next]
        return cls(
            jh.as_long(obj, "objectiveId"),
            jh.as_enum_by_name(obj, "type", GoalKind),
            jh.get_vector3(obj, "position"),
            jh.as_double(obj, "radius"),
            jh.as_text(obj, "description"),
            trigger_scripts,
            next_objectives,
        )


@dataclass(slots=True, eq=False)
class AreaSpec:
    zone_guid: object
    sector_guid: object
    schedule: object
    zone_objective_points: object
    objectives: object
    scriptable_objects: object

    @classmethod
    def from_json(cls, obj: dict) -> "AreaSpec":
        schedule_raw = obj.get("schedule")
        schedule = None if schedule_raw is None else Timetable.from_json(schedule_raw)

        pts_raw = obj.get("zoneObjectivePoints")
        if pts_raw is None:
            zone_objective_points = None
        else:
            zone_objective_points = []
            latott = set()
            for x in pts_raw:
                pt = AreaGoalPoints.from_json(x)
                if pt in latott:
                    continue
                latott.add(pt)
                zone_objective_points.append(pt)

        objectives_raw = obj.get("objectives")
        objectives = None if objectives_raw is None else [GoalSpec.from_json(x) for x in objectives_raw]

        scripts_raw = obj.get("scriptableObjects")
        scriptable_objects = None if scripts_raw is None else [DataAsset.from_json(x) for x in scripts_raw]

        return cls(jh.as_long(obj, "zoneGuid"), jh.as_long(obj, "sectorGuid"), schedule,
                   zone_objective_points, objectives, scriptable_objects)
