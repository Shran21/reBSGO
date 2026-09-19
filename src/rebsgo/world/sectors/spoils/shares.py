# github.com/Shran21

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from rebsgo.helpers.floats import f32, fdiv
from rebsgo.vocabulary.world import DepartureCause, ObjectKind
from rebsgo.world.sectors.running.coming_and_going import DepartureWatcher
from rebsgo.gamedata.from_json.template_readers import claim_rules
from rebsgo.helpers.inheriting import csak_orokosen_at
import logging


class ShareOutcome:
    def __init__(self, csapatbol: bool, is_updated: bool):
        self._is_from_party = csapatbol
        self._is_updated = is_updated

    @property
    def is_from_party(self) -> bool:
        return self._is_from_party

    @property
    def is_updated(self) -> bool:
        return self._is_updated

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, ShareOutcome):
            return False
        return self._is_from_party == other._is_from_party and self._is_updated == other._is_updated

    def __hash__(self) -> int:
        return hash((self._is_from_party, self._is_updated))

    def __repr__(self) -> str:
        honnan = 'party' if self._is_from_party else 'solo'
        return f'<{honnan} claim, {"changed" if self._is_updated else "unchanged"}>'


class Share(ABC):
    def __init__(self, zarolas_fajta):
        self._claim_object = None
        self._loot_claim_type = zarolas_fajta

    @abstractmethod
    def took_a_hit(self, sebzes_sor, party) -> None:
        ...

    def claim_object(self):
        return self._claim_object

    def claim_objects(self):
        if self._claim_object is None:
            return []
        return [self._claim_object]

    @property
    def loot_claim_type(self):
        return self._loot_claim_type


class ShareKind(Enum):
    PVE = 0
    PVP = 1
    ASTEROID_YIELD = 2
    OUTPOST = 3


class ShareStamp:
    def __init__(self, felszabadulasig: int):
        self._time_until_free = felszabadulasig
        self._last_claim_time = 0
        self._is_first = True
        self._dmg_done_by = None

    def update(self, current: int, sebzo_fel, party) -> ShareOutcome:
        egy_rajban = (self._is_first is False and party is not None
                      and party.is_in_party(self._dmg_done_by.pilot_id()))
        atveszi = (self._is_first
                   or egy_rajban
                   or self._dmg_done_by == sebzo_fel
                   or (self._last_claim_time + self._time_until_free) < current)
        if not atveszi:
            return ShareOutcome(False, False)

        self._is_first = False
        self._last_claim_time = current
        self._dmg_done_by = sebzo_fel
        return ShareOutcome(egy_rajban, True)

    @property
    def time_until_free(self) -> int:
        return self._time_until_free

    @property
    def dmg_done_by(self):
        return self._dmg_done_by


class OutpostShare(Share):
    def __init__(self, pilota_sebzese=None):
        super().__init__(ShareKind.OUTPOST)
        if pilota_sebzese is None:
            pilota_sebzese = {}
        self._player_damage_done = pilota_sebzese

    def took_a_hit(self, sebzes_sor, party) -> None:
        if not sebzes_sor.from_.is_player():
            return

        self._player_damage_done[sebzes_sor.from_.pilot_id()] = sebzes_sor.from_

    def claim_objects(self):
        return list(self._player_damage_done.values())

    def claim_object(self):
        raise RuntimeError('objects under claim')


class PvpShare(Share):
    def __init__(self, sebzes_kuszob: float, claim_lifetime: int, sebzes_elozmeny):
        super().__init__(ShareKind.PVP)
        self._object_damage_history = sebzes_elozmeny
        self._claim_time_until_free = claim_lifetime
        self._minimum_percentage_damage = f32(sebzes_kuszob)
        self._kill_shot_object = None

    def took_a_hit(self, sebzes_sor, party) -> None:
        if (highest := self._object_damage_history.highest_damage_dealer()) is not None:
            self._claim_object = highest.dealer

        if sebzes_sor.is_kill_shot:
            opt = self._object_damage_history.by_object_id(sebzes_sor.from_.id_in_space())
            if opt is not None:
                self._kill_shot_object = opt

    @property
    def kill_shot_object(self):
        return self._kill_shot_object

    @property
    def sorted_by_dmg(self):
        return self._object_damage_history.by_damage_dealt

    def damage_dealers(self, predicate):
        return self._object_damage_history.all(predicate)

    @property
    def minimum_percentage_damage(self) -> float:
        return self._minimum_percentage_damage

    @property
    def claim_time_until_free(self) -> int:
        return self._claim_time_until_free

    def assist_share_holders(self, max_hp: float, tick):
        claim_obj = self.claim_object()
        kill_shot = self.kill_shot_object
        olo = None if kill_shot is None else kill_shot.dealer
        kuszob = f32(max_hp * self.minimum_percentage_damage)

        def jar_neki(reszes) -> bool:
            if claim_obj is not None and reszes.dealer == claim_obj:
                return False
            if olo is not None and reszes.dealer == olo:
                return False
            if reszes.damage_so_far <= kuszob:
                return False
            return reszes.last_time + self.claim_time_until_free >= tick.time_stamp()

        return {reszes for reszes in self.sorted_by_dmg if jar_neki(reszes)}


class PveShare(Share):
    def __init__(self, zarolas_mp: int, zarolas_fajta):
        csak_orokosen_at(self, PveShare)
        super().__init__(zarolas_fajta)
        self._claim_time_stamp = ShareStamp(zarolas_mp * 1000)

    def took_a_hit(self, sebzes_sor, party) -> None:
        self._update_claim_time_stamp(sebzes_sor, party)

    def _update_claim_time_stamp(self, sebzes_sor, party) -> None:
        claim_update_result = self._claim_time_stamp.update(sebzes_sor.time_stamp(), sebzes_sor.from_, party)
        if claim_update_result.is_updated:
            if not claim_update_result.is_from_party:
                self._claim_object = self._claim_time_stamp.dmg_done_by


class AsteroidShare(PveShare):
    def __init__(self, zarolas_mp: int):
        super().__init__(zarolas_mp, ShareKind.ASTEROID_YIELD)


class GroupPveShare(PveShare):
    def __init__(self, zarolas_mp: int):
        super().__init__(zarolas_mp, ShareKind.PVE)


log = logging.getLogger(__name__)


class ShareBook(DepartureWatcher):
    def __init__(self, pilotak, loot_ownership, damage_log, spoils_split, tally_giver):
        szabalyok = claim_rules()
        self._pvp_hold_ms = szabalyok.pvp_hold_ms
        self._pvp_damage_share = f32(szabalyok.pvp_damage_share)
        self._asteroid_hold_seconds = szabalyok.asteroid_hold_seconds
        self._default_hold_seconds = szabalyok.default_hold_seconds
        self._solo_share_threshold = f32(szabalyok.solo_share_threshold)
        self._users = pilotak
        self._loot_claim_map = {}
        self._loot_ownership = loot_ownership
        self._damage_log = damage_log
        self._spoils_split = spoils_split
        self._tally_giver = tally_giver

    def update_claim(self, sebzes_sor, user) -> None:
        loot_claim = self._loot_claim_map.get(sebzes_sor.to)
        if loot_claim is None:
            loot_claim = self._get_default(sebzes_sor)

        party = user.pilot_of().party()
        loot_claim.took_a_hit(sebzes_sor, party)
        self._loot_claim_map[sebzes_sor.to] = loot_claim

    def _get_default(self, sebzes_sor):
        if sebzes_sor.to.is_player():
            dmg_history = self._damage_log.damage_history(sebzes_sor.to)
            return PvpShare(self._pvp_damage_share, self._pvp_hold_ms, dmg_history)
        entity_type = sebzes_sor.to.space_entity_type
        if entity_type == ObjectKind.Outpost:
            return OutpostShare()
        if entity_type == ObjectKind.Asteroid:
            return AsteroidShare(self._asteroid_hold_seconds)
        return GroupPveShare(self._default_hold_seconds)

    def claim(self, object_of_desire):
        return self._loot_claim_map.get(object_of_desire)

    def remove_claim(self, zarolt_objektum) -> None:
        if zarolt_objektum is None:
            return
        self._loot_claim_map.pop(zarolt_objektum, None)

    @property
    def loot_ownership(self):
        return self._loot_ownership

    def on_update(self, arg) -> None:
        removing_cause = arg.removal_cause_of()
        if not removing_cause.of_kind(DepartureCause.Death, DepartureCause.Collected):
            self.remove_claim(arg.departed_object)
            return
        departed_object = arg.departed_object

        claim = self.claim(departed_object)
        if claim is None:
            if departed_object.is_player():
                log.info('removal found no claim held by that pilot')
            return
        self.remove_claim(departed_object)

        claim_objects = claim.claim_objects()
        if len(claim_objects) == 0:
            return

        loot_claim_type = claim.loot_claim_type
        if loot_claim_type == ShareKind.PVP:
            self._handle_pvp_claim(claim, departed_object)
        elif loot_claim_type == ShareKind.OUTPOST:
            self._handle_outpost_claim(departed_object)
        elif loot_claim_type == ShareKind.PVE or loot_claim_type == ShareKind.ASTEROID_YIELD:
            self._handle_pve_asteroid_claim(claim_objects, departed_object)

    def _handle_pve_asteroid_claim(self, zarolt_objektumok, departed_object) -> None:
        tulajdonos = self._users.user(zarolt_objektumok[0].pilot_id())
        if tulajdonos is None:
            return

        masok_oltek = self._is_pve_too_much_dmg_done(departed_object)
        zsakmany = self._loot_ownership.take_out(departed_object)
        if masok_oltek:
            return

        self._tally_giver.npc_downed(tulajdonos, departed_object, zsakmany)
        if zsakmany is None:
            return
        self._spoils_split.npc_spoils(
            tulajdonos, departed_object, self._damage_log.damage_history(departed_object), zsakmany)

    def _handle_outpost_claim(self, departed_object) -> None:
        if (zsakmany := self._loot_ownership.take_out(departed_object)) is not None:
            self._spoils_split.outpost_spoils(
                departed_object, zsakmany, self._damage_log.damage_history(departed_object))
        self.remove_claim(departed_object)

    def _handle_pvp_claim(self, zarolas, departed_object) -> None:
        if not isinstance(zarolas, PvpShare):
            return

        if (zsakmany := self._loot_ownership.take_out(departed_object)) is not None:
            killed_player = departed_object
            self._spoils_split.pilot_spoils(zarolas, killed_player, zsakmany)

        self.remove_claim(departed_object)

    def _is_pve_too_much_dmg_done(self, departed_object) -> bool:
        dmg_history = self._damage_log.damage_history(departed_object)
        highest_dealer = dmg_history.highest_damage_dealer()
        if highest_dealer is None:
            return False

        highest_single_dmg = highest_dealer.damage_so_far
        if not highest_dealer.dealer.is_player():
            summed_up = dmg_history.sum_damage
            dmg_percentage_done = f32(fdiv(highest_single_dmg, summed_up))
            return dmg_percentage_done > self._solo_share_threshold
        return False
