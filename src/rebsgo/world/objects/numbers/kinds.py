# github.com/Shran21

from __future__ import annotations

from rebsgo.gamedata.library import Catalogue, fogyoeszkoz_kartya
from rebsgo.gamedata.reading import AbilityActionKind, ObjectStat, ObjectStats, apply_action_stat_multipliers
from rebsgo.geometry.maths.maths import Maths
from rebsgo.helpers.guarded import GuardedCount
from rebsgo.helpers.carrier_transponder_diagnostics import (
    carrier_transponder_debug_enabled,
    format_ship_aspects,
    has_ship_aspect,
    safe_call,
)
from rebsgo.helpers.floats import f32
from rebsgo.helpers.locks import ReentrantLock
from rebsgo.services import Services
from rebsgo.vocabulary.pilot import ShipTrait
from rebsgo.world.objects.numbers.pending.pending_changes import PendingChanges
from rebsgo.world.objects.numbers.watchers import StatEntry
from rebsgo.world.sectors.powers.nuclear_missile_stats import apply_to_ability_stats
import datetime
import logging


class CombatInfo:
    def __init__(self, utolso_harc_ideje: int = 0, under_fire: bool = False):
        self._last_combat_time = utolso_harc_ideje
        self._is_in_combat = under_fire

    def combat_status_moved(self, harc_hossza_mp: int, most_epoch_ms: int,
                            raketaval: bool) -> bool:
        sosem_utottek = self._last_combat_time == 0
        eltelt_ms = most_epoch_ms - self._last_combat_time
        meg_tart = eltelt_ms < harc_hossza_mp * 1000

        most_harcol = not sosem_utottek and (meg_tart or raketaval)
        valtozott = self._is_in_combat != most_harcol
        self._is_in_combat = most_harcol
        return valtozott

    def note_combat_moment(self, ekkor: int) -> None:
        self._last_combat_time = ekkor

    @property
    def is_in_combat(self) -> bool:
        return self._is_in_combat

    def __str__(self) -> str:
        return "<CombatInfo " + f"last_combat_time={self._last_combat_time}, is_in_combat={self._is_in_combat}" + ">"


class HullPower:
    def __init__(self, hull_points: float, power_points: float):
        self._hull_points = hull_points
        self._power_points = power_points

    @property
    def hull_points(self) -> float:
        return self._hull_points

    @hull_points.setter
    def hull_points(self, hull_points: float) -> None:
        self._hull_points = hull_points

    @property
    def power_points(self) -> float:
        return self._power_points

    @power_points.setter
    def power_points(self, power_points: float) -> None:
        self._power_points = power_points


class Owner:
    def __init__(self, owner_id: int, player_owned: bool):
        self._owner_id = owner_id
        self._is_user = player_owned

    @property
    def owner_id(self) -> int:
        return self._owner_id

    @property
    def is_user(self) -> bool:
        return self._is_user

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, Owner):
            return False
        return self._owner_id == other._owner_id and self._is_user == other._is_user

    def __hash__(self) -> int:
        return hash((self._owner_id, self._is_user))

    def __str__(self) -> str:
        return f'<{"pilot" if self._is_user else "npc"} {self._owner_id}>'


class ShipTweaks:
    def __init__(self, modositok: dict | None = None):
        self._ship_modifiers: dict = {} if modositok is None else modositok
        self._last_id = 0

    def _get_free_server_id(self) -> int:
        self._last_id += 1
        return self._last_id

    TAVOLHATO_FAJTAK = {
        "add": ("remote_buff_add", 0.0, lambda jo, rossz: f32(jo + rossz)),
        "multiply": ("remote_buff_multiply", 1.0, lambda jo, rossz: f32((jo + rossz) * 0.5)),
    }

    def strongest_remote_add(self) -> dict:
        return self._tavolhato_eredoje("add")

    def strongest_remote_multiply(self) -> dict:
        return self._tavolhato_eredoje("multiply")

    def _tavolhato_eredoje(self, fajta: str) -> dict:
        mezo, semleges, osszeolvad = self.TAVOLHATO_FAJTAK[fajta]
        erositesek: dict = {}
        gyengitesek: dict = {}
        for modifier in self._ship_modifiers.values():
            for stat, ertek in getattr(modifier, mezo).all_stats.items():
                erosit = ertek > semleges
                cel = erositesek if erosit else gyengitesek
                if stat not in cel:
                    cel[stat] = ertek
                else:
                    cel[stat] = Maths.max(cel[stat], ertek) if erosit else Maths.min(cel[stat], ertek)

        for stat, gyenge in gyengitesek.items():
            if stat not in erositesek:
                erositesek[stat] = gyenge
            erositesek[stat] = osszeolvad(erositesek[stat], gyenge)
        return erositesek

    def attach_modifier(self, modosito) -> list:
        present_modifier = next(
            (mod for mod in self._ship_modifiers.values()
             if mod.ship_system.ship_system_card.card_guid_of()
             == modosito.ship_system.ship_system_card.card_guid_of()), None)
        if present_modifier is not None:
            self.remove_modifier(present_modifier.server_id)
            free_id = present_modifier.server_id
        else:
            free_id = self._get_free_server_id()
        modosito.server_id = free_id
        self._ship_modifiers[free_id] = modosito
        return [modosito]

    def ship_buff(self, id: int):
        return self._ship_modifiers.get(id)

    def reset(self) -> None:
        self._ship_modifiers.clear()

    def all(self) -> list:
        return list(self._ship_modifiers.values())

    def of_type(self, ability_action_type) -> list:
        return [buff for buff in self._ship_modifiers.values()
                if buff.ship_ability().ship_ability_card.ability_action_type == ability_action_type]

    def of_type_stream(self, ability_action_type):
        return iter(self.of_type(ability_action_type))

    def expired_ones(self) -> set:
        timeouted_modifiers = set()
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        for mod in self._ship_modifiers.values():
            tartam = mod.item_buff_add.stat(ObjectStat.Duration)
            last_time_used_plus_duration = (mod.time_of_activation_local_date_time()
                                            + datetime.timedelta(milliseconds=int(tartam * 1000)))
            if now > last_time_used_plus_duration:
                timeouted_modifiers.add(mod.server_id)
        return timeouted_modifiers

    def remove_modifier(self, server_id) -> None:
        if isinstance(server_id, (set, frozenset, list, tuple)):
            for sid in server_id:
                self._ship_modifiers.pop(sid, None)
        else:
            self._ship_modifiers.pop(server_id, None)

    def __str__(self) -> str:
        return "<ShipBuffs " + f"ship_buffs={self._ship_modifiers}" + ">"


log = logging.getLogger(__name__)


class SpaceFeed:
    def __init__(self, owner_id: int, vegso_statok, hull_points=0.0,
                 power_points=0.0, *, owner_is_pilot: bool = False):
        self._owner = Owner(owner_id, owner_is_pilot)
        self.stats_final = vegso_statok
        self.modified_for_stats_buff = ObjectStats()
        self.hull_power_points = HullPower(hull_points, power_points)
        self._subscribers: dict = {}
        self.lock = ReentrantLock()
        self.movement_update_subscriber = None
        self._ship_aspects = None
        self._has_pending_property_buffers = False

    def _mark_property_buffers_dirty(self) -> None:
        if self._subscribers:
            self._has_pending_property_buffers = True

    @property
    def has_pending_space_property_buffer(self) -> bool:
        return self._has_pending_property_buffers

    def on_movement_update(self, mozgas_figyelo) -> None:
        self.movement_update_subscriber = mozgas_figyelo

    def reset_stats(self) -> None:
        self.stats_final.wipe()

    def restore_watcher(self, alap_valtozas_puffer) -> None:
        self._subscribers[alap_valtozas_puffer.stats_protocol_subscriber] = alap_valtozas_puffer
        alap_valtozas_puffer.on_stat_moved(self, StatEntry.Hp)
        alap_valtozas_puffer.on_stat_moved(self, StatEntry.Pp)
        alap_valtozas_puffer.on_stat_moved(self, StatEntry.Stats)
        self._mark_property_buffers_dirty()

    def watch_with(self, stat_figyelo) -> None:
        with self.lock:
            atmeneti = PendingChanges.create(self._owner, stat_figyelo)
            if atmeneti is None:
                return
            self._subscribers[stat_figyelo] = atmeneti
            atmeneti.on_stat_moved(self, StatEntry.Combat)
            atmeneti.on_stat_moved(self, StatEntry.Stats)
            atmeneti.on_stat_moved(self, StatEntry.Hp)
            atmeneti.on_stat_moved(self, StatEntry.Pp)
            if (rekeszek := self.ship_slots) is not None:
                for slot_id in rekeszek.pairs:
                    atmeneti.on_slot_update(self, slot_id[0])
            if self._ship_aspects is not None:
                if (carrier_transponder_debug_enabled()
                    and has_ship_aspect(self._ship_aspects, ShipTrait.TransponderJump)):
                    log.info(
                        "CARRIER_TRANSPONDER_DIAG ship_aspects_add_subscriber owner=%s owner_is_user=%s "
                        "subscriber_protocol=%s aspects=%s",
                        safe_call(self._owner, "owner_id"),
                        safe_call(self._owner, "is_user"),
                        safe_call(stat_figyelo, "protocol_id_of"),
                        format_ship_aspects(self._ship_aspects))
                atmeneti.push_ship_aspect_update(self._ship_aspects)
            self._mark_property_buffers_dirty()

    def take_aspects(self, ship_aspects) -> None:
        with self.lock:
            self._ship_aspects = ship_aspects
            if ship_aspects is None:
                return
            if carrier_transponder_debug_enabled() and has_ship_aspect(ship_aspects, ShipTrait.TransponderJump):
                log.info(
                    "CARRIER_TRANSPONDER_DIAG set_ship_aspects owner=%s owner_is_user=%s "
                    "subscriber_count=%s aspects=%s",
                    safe_call(self._owner, "owner_id"),
                    safe_call(self._owner, "is_user"),
                    len(self._subscribers),
                    format_ship_aspects(ship_aspects))
            for puffer in self._subscribers.values():
                puffer.push_ship_aspect_update(ship_aspects)
            self._mark_property_buffers_dirty()

    def remove_subscriber(self, stat_figyelo) -> None:
        with self.lock:
            self._subscribers.pop(stat_figyelo, None)

    def clear_watchers(self) -> None:
        with self.lock:
            self._subscribers.clear()

    def set_hull(self, uj_hp: float) -> None:
        with self.lock:
            self.hull_power_points.hull_points = uj_hp
            self.limit_hull()
            for ertek in self._subscribers.values():
                ertek.on_stat_moved(self, StatEntry.Hp)
            self._mark_property_buffers_dirty()

    def set_power(self, uj_pp: float) -> None:
        self.hull_power_points.power_points = uj_pp
        self._pp_updated()

    def _pp_updated(self) -> None:
        self.refresh_generic(StatEntry.Pp)

    def refresh_generic(self, stat_adat) -> None:
        with self.lock:
            for ertek in self._subscribers.values():
                ertek.on_stat_moved(self, stat_adat)
            self._mark_property_buffers_dirty()

    @property
    def hp(self) -> float:
        return self.hull_power_points.hull_points

    @property
    def pp(self) -> float:
        return self.hull_power_points.power_points

    def limit_hull(self) -> None:
        current_hp = self.hp
        if current_hp > self.stat_or_default(ObjectStat.MaxHullPoints):
            self.fill_hull()

    def cap_hull_and_power(self) -> None:
        self.fill_hull()
        self.fill_power()

    def fill_power(self) -> None:
        self.set_power(self.stats_final.stat_or_default(ObjectStat.MaxPowerPoints))

    def fill_hull(self) -> None:
        self.set_hull(self.stats_final.stat_or_default(ObjectStat.MaxHullPoints))

    @property
    def combat_info(self):
        return None

    @property
    def is_in_combat(self) -> bool:
        combat_info = self.combat_info
        if combat_info is None:
            return False
        return combat_info.is_in_combat

    def holds_stat(self, stat) -> bool:
        return self.stats_final.holds_stat(stat)

    @property
    def subscribers(self) -> dict:
        with self.lock:
            return self._subscribers

    def set_hp_pp(self, uj_hp: float, uj_pp: float) -> None:
        self.set_hull(uj_hp)
        self.set_power(uj_pp)

    def note_combat_moment(self, ekkor: int) -> None:
        if (combat_info := self.combat_info) is not None:
            combat_info.note_combat_moment(ekkor)

    def refresh_combat_state(self, harc_ora: int, most_ms: int, raketaval: bool) -> None:
        combat_info = self.combat_info
        if combat_info is None:
            return
        valtozott = combat_info.combat_status_moved(harc_ora, most_ms, raketaval)
        if valtozott:
            for subscriber in self._subscribers.values():
                subscriber.on_stat_moved(self, StatEntry.Combat)
            self._mark_property_buffers_dirty()

    def stat(self, stat):
        return self.stats_final.stat(stat)

    def stat_or_default(self, stat, alapertelmezett: float = 0.0) -> float:
        return self.stats_final.stat_or_default(stat, alapertelmezett)

    @property
    def stats_of(self) -> ObjectStats:
        return self.stats_final

    def fold_in_stats(self) -> None:
        self.reset_stats()

    def fold_in_mod_bonus(self) -> None:
        for stat, ertek in self.modified_for_stats_buff.all_stats.items():
            if not self.stats_final.holds_stat(stat):
                continue
            mostani = self.stats_final.stat(stat)
            new_stat = f32(mostani * f32(1.0 + ertek))
            self.stats_final.set_stat(stat, new_stat)

    @property
    def ship_modifiers(self):
        return None

    def take_modifier(self, modosito) -> None:
        modifiers = self.ship_modifiers
        if modifiers is None:
            return
        new_modifiers = modifiers.attach_modifier(modosito)
        for sub in self._subscribers.values():
            sub.on_modifier_add(self, new_modifiers)
        self._mark_property_buffers_dirty()
        self.fold_in_stats()

    def remove_modifiers(self, levonandok) -> None:
        modifiers = self.ship_modifiers
        if modifiers is None:
            return
        modifiers.remove_modifier(levonandok)
        for sub in self._subscribers.values():
            sub.on_modifier_remove(self, levonandok)
        self._mark_property_buffers_dirty()
        self.fold_in_stats()

    @property
    def target_object_id(self):
        return None

    @target_object_id.setter
    def target_object_id(self, new_target_object_id: int) -> None:
        with self.lock:
            if (celpont := self.target_object_id) is not None:
                celpont.set(new_target_object_id)
                for sub in self._subscribers.values():
                    sub.on_stat_moved(self, StatEntry.Target)
                self._mark_property_buffers_dirty()

    @property
    def ship_slots(self):
        return None

    @property
    def skill_book(self):
        return None

    @skill_book.setter
    def skill_book(self, skill_book) -> None:
        pass

    @property
    def modifiers(self):
        return None

    @ship_slots.setter
    def ship_slots(self, slots) -> None:
        pass

    def flush_property_buffer(self) -> int:
        if not self._has_pending_property_buffers:
            return 0
        pending = []
        with self.lock:
            if not self._has_pending_property_buffers:
                return 0
            self._has_pending_property_buffers = False
            for subscriber, puffer in self._subscribers.items():
                if puffer.is_updated:
                    pending.append((subscriber, puffer))

        to_remove = set()
        for subscriber, puffer in pending:
            send_result = subscriber.flush_property_buffer(puffer)
            if not send_result:
                to_remove.add(subscriber)

        if not to_remove:
            return len(pending)
        with self.lock:
            for stats_protocol_subscriber in to_remove:
                self._subscribers.pop(stats_protocol_subscriber, None)
        return len(pending)

    def drop_subscriber(self, player_id: int) -> None:
        for_removal = []
        with self.lock:
            for subscriber in self._subscribers.keys():
                if subscriber.user_id() == player_id:
                    for_removal.append(subscriber)
            for subscriber in for_removal:
                self._subscribers.pop(subscriber, None)

    @property
    def owner(self) -> Owner:
        return self._owner


class ShipFeed(SpaceFeed):
    def __init__(self, owner_id, vegso_statok, owner_is_pilot: bool = False):
        super().__init__(owner_id, vegso_statok.copy(), 1.0, 1.0,
                         owner_is_pilot=owner_is_pilot)
        self.catalogue: Catalogue = Services.get(Catalogue)
        self.stats_base = vegso_statok.copy()
        self.stats_with_slots = vegso_statok.copy()
        self._ship_modifiers = ShipTweaks()
        self._combat_info = CombatInfo()
        self._target_object_id = GuardedCount(0)
        self._ship_slots = None

    def reset_stats(self) -> None:
        super().reset_stats()
        self.stats_final.merge_in(self.stats_base.copy())
        self.stats_with_slots.merge_in(self.stats_base.copy())

    def fold_in_slot_systems(self) -> None:
        if self._ship_slots is None:
            return
        for rekesz in self._ship_slots.values():
            ship_system_card = rekesz.ship_system.ship_system_card
            if ship_system_card is None:
                continue
            static_buffs = ObjectStats.as_stats(ship_system_card.static_buffs)
            ObjectStats.add_into(static_buffs, self.stats_with_slots)
            mult_buffs = ObjectStats.as_stats(ship_system_card.multiply_buffs)
            ObjectStats.scale_into(mult_buffs, self.stats_with_slots)

    def fold_in_abilities(self) -> None:
        rekeszek = self.ship_slots
        if rekeszek is None:
            return
        for rekesz in rekeszek.values():
            if rekesz.ship_system is not None and rekesz.ship_ability() is not None:
                self.fold_in_ability_slots(rekesz)
                for internal_slots in rekeszek.values():
                    if (internal_slots.ship_system is None
                        or internal_slots.ship_system.ship_system_card is None):
                        continue
                    kepesseg = rekesz.ship_ability()
                    rendszer = internal_slots.ship_system
                    system_card = rendszer.ship_system_card
                    system_mults_on_guns = system_card.multiply_buffs
                    action_type = kepesseg.ship_ability_card.ability_action_type
                    apply_action_stat_multipliers(action_type, system_mults_on_guns, kepesseg.item_buff_add)
                for ertek in self.subscribers.values():
                    ertek.on_slot_update(self, rekesz.ship_system.server_id)
        self._mark_property_buffers_dirty()

    def fold_in_stats(self) -> None:
        super().fold_in_stats()
        self.fold_in_slot_systems()
        self.fold_in_abilities()
        self.stats_final.merge_in(self.stats_with_slots)
        self.fold_in_mod_bonus()
        self.fold_in_modifiers()
        for puffer in self.subscribers.values():
            puffer.on_stat_moved(self, StatEntry.Stats)
        self._mark_property_buffers_dirty()
        if (ud := self.movement_update_subscriber) is not None:
            ud.take_movement_stats(self)

    def fold_in_modifiers(self) -> None:
        best_buff_remote_modifiers = ObjectStats(self._ship_modifiers.strongest_remote_add())
        ObjectStats.add_into(best_buff_remote_modifiers, self.stats_final)
        strongest_multipliers = ObjectStats(self._ship_modifiers.strongest_remote_multiply())
        stats_multiply_bonus = ObjectStats.stats_multiply_bonus(self.stats_with_slots, strongest_multipliers)
        ObjectStats.add_into(stats_multiply_bonus, self.stats_final)

    def fold_in_ability_slots(self, slot) -> None:
        if slot is None:
            log.warning('slot stats requested where no slot exists')
            return
        kepesseg = slot.ship_ability()
        kepesseg.reset_stats()
        current_consumable = slot.current_consumable.item_countable

        if (skill_book := self.skill_book) is not None:
            mult_skill_stats = skill_book.as_object_stats(
                kepesseg.ship_ability_card.ability_action_type)
            ObjectStats.scale_into(mult_skill_stats, kepesseg.item_buff_add)

        base_stats = kepesseg.item_buff_add.copy()
        consumable_bonus_stats = ObjectStats()
        ship_consumable_card = None

        if current_consumable.card_guid_of() != 0:
            ship_consumable_card = fogyoeszkoz_kartya(current_consumable)
            tmp_bonus = ObjectStats.scale_where_bonus_applies(
                ship_consumable_card.item_buff_add, base_stats)
            consumable_bonus_stats.take_stats(tmp_bonus)
            from rebsgo.gamedata.reading import ObjectStat as _Stat
            for _szivo in (_Stat.DrainLow, _Stat.DrainHigh):
                if (ship_consumable_card.item_buff_add.holds_stat(_szivo)
                        and not base_stats.holds_stat(_szivo)):
                    consumable_bonus_stats.set_stat(
                        _szivo, ship_consumable_card.item_buff_add.stat(_szivo))

        if (modifiers := self.ship_modifiers) is not None:
            best = modifiers.strongest_remote_multiply()
            buffs = ObjectStats(best)
            if kepesseg.ship_ability_card.ability_action_type == AbilityActionKind.FireMissle:
                buffs.drop_stat(ObjectStat.BoostSpeed)
                buffs.drop_stat(ObjectStat.TurnSpeed)
                buffs.drop_stat(ObjectStat.Speed)
            apply_action_stat_multipliers(
                kepesseg.ship_ability_card.ability_action_type, buffs, base_stats)
            kepesseg.item_buff_add.take_stats(base_stats)

        if len(consumable_bonus_stats.all_stats) != 0:
            ObjectStats.add_into(consumable_bonus_stats, kepesseg.item_buff_add)

        if ship_consumable_card is not None:
            apply_to_ability_stats(kepesseg.item_buff_add, kepesseg.ship_ability_card,
                                   ship_consumable_card)

    @property
    def modifiers(self):
        return self._ship_modifiers

    @property
    def combat_info(self):
        return self._combat_info

    @SpaceFeed.target_object_id.getter
    def target_object_id(self):
        return self._target_object_id

    @property
    def ship_slots(self):
        return self._ship_slots

    @ship_slots.setter
    def ship_slots(self, ship_slots) -> None:
        if ship_slots is None:
            raise TypeError('ship slots are required')
        self._ship_slots = ship_slots

    @property
    def ship_modifiers(self):
        return self._ship_modifiers


class PilotFeed(ShipFeed):
    def __init__(self, owner_id, object_stats):
        super().__init__(owner_id, object_stats, owner_is_pilot=True)
        self._skill_book = None

    def fold_in_stats(self) -> None:
        with self.lock:
            self.reset_stats()
            self.fold_in_slot_systems()
            self.fold_in_abilities()
            self.stats_final.merge_in(self.stats_with_slots)
            self.fold_in_modifiers()
            self._apply_skills()
            for sub in self.subscribers.values():
                sub.on_stat_moved(self, StatEntry.Stats)
            self._mark_property_buffers_dirty()
            if (ud := self.movement_update_subscriber) is not None:
                ud.take_movement_stats(self.stats_of)

    def _apply_skills(self) -> None:
        skill_book = self.skill_book
        if skill_book is None:
            return
        for skill in skill_book.all_skills.values():
            static_buffs = skill.static_buff
            mult_buffs = skill.multiply_buff
            ObjectStats.add_into(static_buffs, self.stats_final)
            add_bonus = ObjectStats.stats_multiply_bonus(self.stats_with_slots, mult_buffs)
            ObjectStats.add_into(add_bonus, self.stats_final)

    @property
    def skill_book(self):
        return self._skill_book

    @skill_book.setter
    def skill_book(self, skill_book) -> None:
        with self.lock:
            self._skill_book = skill_book
        self.fold_in_stats()
