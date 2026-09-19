# github.com/Shran21

from __future__ import annotations

from enum import Enum
from rebsgo.gamedata.from_json.small_readers import get_module_decoy_config
from rebsgo.gamedata.reading import AbilityActionKind, ShipSlotType
from rebsgo.helpers.guarded import GuardedFlag, GuardedCount
from rebsgo.helpers.locks import ReentrantLock
from rebsgo.vocabulary.pilot import ShipTrait
from rebsgo.vocabulary.world import VisibilityCause
from rebsgo.wire.bytes.incoming import Incoming
from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.gamedata.from_json.template_readers import module_bindings
from rebsgo.world.capitals.capital_roster import COLONIAL_CAPITAL_GUID, CYLON_CAPITAL_GUID
import logging
import threading
import time
from rebsgo.gamedata.from_json.template_readers import world_timers


class ModuleMount(Outgoing):
    def __init__(self, object_point_hash: int, modul_guid: int):
        self._object_point_hash = object_point_hash
        self._module = modul_guid

    @property
    def object_point_hash(self) -> int:
        return self._object_point_hash

    @property
    def module_guid(self) -> int:
        return self._module

    def to_wire(self, bw) -> None:
        bw.write_uint16(self._object_point_hash)
        bw.write_guid(self._module)


class ObjectState(Outgoing):
    def __init__(self, object_id: int, revision: int, carrier_flagged: bool, braced: bool,
                 is_cloaked: bool, emp_active: bool, cargo_volume: int, dock_underway: bool):
        self.changed = False
        self._object_id = object_id
        self._revision = revision
        self._is_marked_by_carrier = carrier_flagged
        self._is_fortified = braced
        self._is_cloaked = is_cloaked
        self._is_emp_on = emp_active
        self._cargo_volume = cargo_volume
        self._is_docking = dock_underway
        self._anchored_user_ids = set()
        self._anchored_lock = threading.Lock()
        self.lock = ReentrantLock()

    @staticmethod
    def create_for_object_id(object_id: int) -> "ObjectState":
        return ObjectState(object_id, 0, False, False, False, False, 0, False)

    def to_wire(self, bw) -> None:
        with self.lock:
            self._revision += 1
            bw.write_uint32(self._object_id)
            bw.write_uint32(self._revision)
            bw.write_boolean(self._is_marked_by_carrier)
            bw.write_boolean(self._is_fortified)
            bw.write_single(0.0)
            bw.write_boolean(self._is_cloaked)
            bw.write_boolean(self._is_emp_on)
            bw.write_byte(self._cargo_volume & 0xFF)
            self.changed = False

    def id_in_space(self) -> int:
        return self._object_id

    @property
    def is_marked_by_carrier(self) -> bool:
        return self._is_marked_by_carrier

    @property
    def is_fortified(self) -> bool:
        with self.lock:
            return self._is_fortified

    def anchor_to(self, player_id: int) -> None:
        with self._anchored_lock:
            self._anchored_user_ids.add(player_id)

    def unanchor(self, player_id: int) -> bool:
        with self._anchored_lock:
            if player_id in self._anchored_user_ids:
                self._anchored_user_ids.remove(player_id)
                return True
            return False

    def anchored_ids_snapshot(self) -> set[int]:
        with self._anchored_lock:
            return set(self._anchored_user_ids)

    @property
    def is_emp_on(self) -> bool:
        return self._is_emp_on

    def set_emp_on(self, emp_state: bool) -> None:
        with self.lock:
            if self._is_emp_on == emp_state:
                return
            self.changed = True
            self._is_emp_on = emp_state

    @property
    def is_cloaked(self) -> bool:
        with self.lock:
            return self._is_cloaked

    def cloak(self, cloaked: bool) -> None:
        with self.lock:
            if self._is_cloaked == cloaked:
                return
            self.changed = True
            self._is_cloaked = cloaked

    @property
    def is_docking(self) -> bool:
        return self._is_docking

    def mark_docking(self, docking: bool) -> None:
        self._is_docking = docking

    def set_marked_by_carrier(self, carrier_flag: bool) -> None:
        with self.lock:
            if self._is_marked_by_carrier == carrier_flag:
                return
            self.changed = True
            self._is_marked_by_carrier = carrier_flag

    def set_fortified(self, fortified: bool) -> None:
        with self.lock:
            if self._is_fortified == fortified:
                return
            self.changed = True
            self._is_fortified = fortified

    @property
    def is_changed(self) -> bool:
        with self.lock:
            return self.changed


class ShipTraits(Outgoing):
    def __init__(self, *ship_aspects):
        if len(ship_aspects) == 1 and isinstance(ship_aspects[0], (set, frozenset)):
            self._ship_aspects = ship_aspects[0]
        else:
            self._ship_aspects = set(ship_aspects)

    def take_aspect(self, aspect: ShipTrait) -> None:
        self._ship_aspects.add(aspect)

    def to_wire(self, bw) -> None:
        bw.write_length(len(self._ship_aspects))
        for ship_aspect in self._ship_aspects:
            bw.write_byte(ship_aspect.value)

    def __str__(self) -> str:
        return "<ShipTraits " + f"ship_aspects={self._ship_aspects}" + ">"


class StickerMount(Outgoing, Incoming):
    def __init__(self):
        self._object_point_hash = 0
        self._sticker_id = 0

    def to_wire(self, bw) -> None:
        bw.write_uint16(self._object_point_hash)
        bw.write_uint16(self._sticker_id)

    def read(self, br) -> None:
        self._object_point_hash = br.read_uint16()
        self._sticker_id = br.read_uint16()

    @property
    def object_point_hash(self) -> int:
        return self._object_point_hash

    @property
    def sticker_id(self) -> int:
        return self._sticker_id


class VisibleSet(Outgoing):
    class GhostJumpPhase(Enum):
        NOT_STARTED = 0
        STARTED = 1
        FINISHED = 2

    def __init__(self, is_visible: bool, change_visibility_reason=None, szellemugras=None):
        if change_visibility_reason is None and szellemugras is None:
            change_visibility_reason = VisibilityCause.Default
            szellemugras = VisibleSet.GhostJumpPhase.NOT_STARTED
        if change_visibility_reason is None:
            raise TypeError('a visibility change has to say why')
        self._is_visible = is_visible
        self._change_visibility_reason = change_visibility_reason
        self._ghost_jump_state = szellemugras
        self._stealth_active = False
        self._anchored_object_id = GuardedCount()
        self._last_change_visibility = int(time.time() * 1000)
        self._visibility_changed = GuardedFlag()

    def switch_visibility(self, is_visible: bool, change_visibility_reason, anchored_target: int = 0) -> None:
        if change_visibility_reason is None:
            raise TypeError('visibility change carries no cause')
        self._change_visibility_reason = change_visibility_reason

        self._is_visible = is_visible
        self._anchored_object_id.set(anchored_target)

        self._last_change_visibility = int(time.time() * 1000)
        self._visibility_changed.set(True)

    @property
    def anchored_object_id(self) -> int:
        return self._anchored_object_id.get()

    def to_wire(self, bw) -> None:
        bw.write_boolean(self._is_visible)

    def is_visible(self) -> bool:
        return self._is_visible

    @property
    def change_visibility_reason(self):
        return self._change_visibility_reason

    UJRAPROBALKOZAS_MS = world_timers().visibility_retry_ms

    def jump_in_needed(self, mostani_ora) -> bool:
        return (not self._is_visible
                and not self._stealth_active
                and self._ghost_jump_state == VisibleSet.GhostJumpPhase.STARTED
                and self._change_visibility_reason == VisibilityCause.Default
                and (self._last_change_visibility + self.UJRAPROBALKOZAS_MS)
                < mostani_ora.time_stamp())

    def visibility_needs_push(self) -> bool:
        return self._visibility_changed.set_if(True, False)

    def begin_ghost_jump(self) -> bool:
        if self._ghost_jump_state != VisibleSet.GhostJumpPhase.NOT_STARTED:
            return False

        self._ghost_jump_state = VisibleSet.GhostJumpPhase.STARTED
        self.switch_visibility(False, VisibilityCause.Default)
        return True

    def start_stealth(self) -> bool:
        if self._stealth_active:
            return False

        self._stealth_active = True
        return True

    def finish_stealth(self) -> bool:
        if not self._stealth_active:
            return False

        self._stealth_active = False
        return True

    @property
    def is_stealth_active(self) -> bool:
        return self._stealth_active

    def settle_ghost_jump(self) -> None:
        if self._ghost_jump_state != VisibleSet.GhostJumpPhase.STARTED:
            return

        if self._stealth_active:
            return

        if self._change_visibility_reason != VisibilityCause.Default:
            return

        self.switch_visibility(True, VisibilityCause.Jump)
        self._ghost_jump_state = VisibleSet.GhostJumpPhase.FINISHED

    def __repr__(self) -> str:
        latszik = 'visible' if self._is_visible else 'hidden'
        return (f'<{latszik} ({self._change_visibility_reason}),'
                f' ghost jump {self._ghost_jump_state},'
                f' stealth {"on" if self._stealth_active else "off"},'
                f' last change {self._last_change_visibility},'
                f' pending {self._visibility_changed.get()}>')


log = logging.getLogger(__name__)
_KOTESEK = module_bindings(AbilityActionKind)


class ShipHardpoints(Outgoing):
    def __init__(self, modul_kotesek=None, matrica_kotesek=None,
                 is_syfy: bool = False, ship_system_paint_card=None):
        if modul_kotesek is None and matrica_kotesek is None:
            self._module_binding_list = []
            self._sticker_binding_list = []
            self._is_syfy = False
            self._ship_system_paint_card = None
            return

        if modul_kotesek is None or modul_kotesek is None:
            raise TypeError('module bindings list is required')
        if matrica_kotesek is None or matrica_kotesek is None:
            raise TypeError('sticker bindings list is required')

        self._module_binding_list = modul_kotesek
        self._sticker_binding_list = matrica_kotesek
        self._is_syfy = is_syfy
        self._ship_system_paint_card = ship_system_paint_card

    def take_slots(self, ship_slots, tier: int, is_capital: bool = False, ship_guid: int | None = None,
                  is_stealth: bool = False, prefab_name: str | None = None) -> None:
        if tier < 1 or tier > 4:
            log.debug("WRONG TIER: %s", tier)
            return

        self._module_binding_list.clear()

        allowed_slot_types = (ShipSlotType.weapon,)
        if is_capital:
            allowed_slot_types = (ShipSlotType.weapon, ShipSlotType.gun,
                                  ShipSlotType.launcher, ShipSlotType.defensive_weapon)
        elif is_stealth:
            allowed_slot_types = (ShipSlotType.weapon, ShipSlotType.gun, ShipSlotType.launcher)

        for rekesz in ship_slots.values():
            system_card = rekesz.ship_system.ship_system_card
            if system_card is None:
                continue
            if system_card.ship_slot_type in allowed_slot_types:
                if (kepesseg := rekesz.ship_ability()) is not None:
                    action_type = kepesseg.ship_ability_card.ability_action_type
                    if is_capital:
                        module_guid = self._capital_module_guid(ship_guid, action_type)
                    else:
                        module_guid = _KOTESEK.guid_for(action_type, tier)
                    if module_guid == 0:
                        continue
                    hash_ = rekesz.ship_slot_card().object_point_server_hash
                    ship_module_binding = ModuleMount(hash_, module_guid)
                    self.mount_module(ship_module_binding)

        self._prepend_visibility_decoy(prefab_name)

    def _prepend_visibility_decoy(self, prefab_name: str | None) -> None:
        if not self._module_binding_list:
            return
        decoy_config = get_module_decoy_config()
        if not decoy_config.should_apply(prefab_name):
            return
        first_hash = self._module_binding_list[0].object_point_hash
        self._module_binding_list.insert(
            0, ModuleMount(first_hash, decoy_config.decoy_module_guid))

    @staticmethod
    def _capital_module_guid(ship_guid: int | None, action_type) -> int:
        if ship_guid not in (COLONIAL_CAPITAL_GUID, CYLON_CAPITAL_GUID):
            return 0
        return _KOTESEK.guid_for(action_type, _KOTESEK.capital_tier)

    def paint_with(self, ship_system_paint_card) -> None:
        self._ship_system_paint_card = ship_system_paint_card

    def mount_module(self, modul_kotes) -> None:
        if modul_kotes is None:
            raise TypeError('a module mount is required')
        self._module_binding_list.append(modul_kotes)

    def to_wire(self, bw) -> None:
        sum_len = len(self._module_binding_list) + len(self._sticker_binding_list)
        if self._is_syfy:
            sum_len += 1
        if self._ship_system_paint_card is not None:
            sum_len += 1

        bw.write_length(sum_len)
        for sticker_binding in self._sticker_binding_list:
            bw.write_byte(1)
            bw.write_desc(sticker_binding)
        for ship_module_binding in self._module_binding_list:
            bw.write_byte(2)
            bw.write_desc(ship_module_binding)
        if self._is_syfy:
            bw.write_byte(3)
        if self._ship_system_paint_card is not None:
            bw.write_byte(4)
            bw.write_guid(self._ship_system_paint_card.card_guid_of())

    @property
    def module_binding_list(self):
        return self._module_binding_list

    @property
    def sticker_binding_list(self):
        return self._sticker_binding_list

    @property
    def is_syfy(self) -> bool:
        return self._is_syfy

    @property
    def ship_system_paint_card(self):
        return self._ship_system_paint_card
