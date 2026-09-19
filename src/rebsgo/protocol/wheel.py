# github.com/Shran21

from __future__ import annotations

from dataclasses import dataclass
import json

from datetime import datetime, timedelta, timezone
from enum import Enum
from rebsgo.gamedata.cards.misc_cards import TallyCardKind
from rebsgo.gamedata.from_json.game_data_loader import GameDataLoader
from rebsgo.gamedata.ship_parts.parts import CountableItem, ShipSystem
from rebsgo.helpers.small_helpers import WeightedPick
from rebsgo.protocol.wire_base import BgoProtocol
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.reply_base import ReplyBase
from rebsgo.vocabulary.pilot import ResourceKind
from rebsgo.wire.bytes.stamp import Stamp
import logging


class JackpotKind(Enum):
    Item = 1
    MapPart = 2

    @property
    def short_value(self) -> int:
        return self._value_

    def to_wire(self, bw) -> None:
        bw.write_uint16(self._value_)

    @classmethod
    def from_code(cls, value: int) -> "JackpotKind | None":
        return _jackpot_kind_BY_VALUE.get(value)
_jackpot_kind_BY_VALUE = {member.value: member for member in JackpotKind}


class WheelReply(Enum):
    ReplyInit = 2
    ReplyDraw = 4
    ReplyVisibleMaps = 6
    ReplyMapInfo = 9

    @property
    def short_value(self) -> int:
        return self._value_

    @classmethod
    def from_code(cls, value: int) -> "WheelReply | None":
        return _wheel_reply_BY_VALUE.get(value)
_wheel_reply_BY_VALUE = {member.value: member for member in WheelReply}


@dataclass(slots=True, eq=False)
class WheelSlice:
    jackpot: bool
    bonus_map_id: int
    cards: object
    gui_card_guid: int

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, WheelSlice):
            return False
        return (self.jackpot == other.jackpot and self.bonus_map_id == other.bonus_map_id
                and self.cards == other.cards and self.gui_card_guid == other.gui_card_guid)

    def __hash__(self) -> int:
        return hash((self.jackpot, self.bonus_map_id, tuple(self.cards) if self.cards is not None else None,
                     self.gui_card_guid))

    def __repr__(self) -> str:
        return (f'<wheel slice, gui card {self.gui_card_guid}: jackpot {self.jackpot}, '
                f'bonus map {self.bonus_map_id}, prizes {self.cards}>')


class WheelReplies(ReplyBase):
    UZENETEK = {
        "reply_visible_maps": (
            WheelReply.ReplyVisibleMaps.short_value,
            [("int32_collection", "visible_maps_ids")]),
    }

    def __init__(self):
        super().__init__(ProtocolID.Wof)

    def init(self, jackpot_type, jackpot_item_card_guid: int, amount: int, ingyenes_porgetes: bool,
             lepeskoltsegek):
        bw = self.new_message()
        bw.write_msg_type(WheelReply.ReplyInit.short_value)
        bw.write_desc(jackpot_type)
        bw.write_guid(jackpot_item_card_guid)
        bw.write_int32(amount)
        bw.write_boolean(ingyenes_porgetes)
        bw.write_length(len(lepeskoltsegek))
        for cost in lepeskoltsegek:
            bw.write_int32(cost)
        return bw

    def wof_draw_reply(self, jackpot_type, huzott_tetelek, jackpot_item, ingyenes_volt: bool):
        bw = self.new_message()
        bw.write_msg_type(WheelReply.ReplyDraw.short_value)
        bw.write_uint16(jackpot_type.short_value)
        bw.write_guid(jackpot_item.card_guid_of())
        if isinstance(jackpot_item, CountableItem):
            bw.write_int32(jackpot_item.count())
        else:
            bw.write_int32(1)
        bw.write_boolean(ingyenes_volt)
        bw.write_length(len(huzott_tetelek))
        for tetel in huzott_tetelek:
            bw.write_boolean(tetel.card_guid_of() == jackpot_item.card_guid_of())
            bw.write_guid(tetel.card_guid_of())
            if isinstance(tetel, CountableItem):
                bw.write_int32(tetel.count())
            else:
                bw.write_int32(1)
        bw.write_length(0)
        return bw

    @property
    def all_visible_maps(self):
        return self.reply_visible_maps([1, 2, 3, 4])


log = logging.getLogger(__name__)


class _ClientRequest(Enum):
    RequestInit = 1
    RequestDraw = 3
    RequestVisibleMaps = 5
    RequestMapStart = 7
    RequestMapInfo = 8

    @staticmethod
    def from_code(value: int):
        return _CR_BY_VALUE.get(value)
_CR_BY_VALUE = {member.value: member for member in _ClientRequest}


class WofProtocol(BgoProtocol):
    def __init__(self, ctx):
        super().__init__(ProtocolID.Wof, ctx)
        self._writer = WheelReplies()

        self._cost_list_per_step = []
        self._build_cost_list()
        self._part_lottery = WeightedPick(ctx.rng)
        self.jackpot_item = None
        self._last_wof_game_session = None

        self._build_wheel_items()

    def _jackpot_pool_of(self):
        jack_pot_items = []
        jack_pot_items.append(CountableItem.from_guid(ResourceKind.Cubits, 10_000))
        jack_pot_items.append(CountableItem.from_guid(ResourceKind.TuningKit, 10))
        jack_pot_items.append(CountableItem.from_guid(ResourceKind.Strikerx20Nuke, 5))
        jack_pot_items.append(CountableItem.from_guid(ResourceKind.Escortx20Nuke, 5))
        jack_pot_items.append(CountableItem.from_guid(ResourceKind.Linerx20Nuke, 5))
        return jack_pot_items

    def _build_cost_list(self) -> None:
        for i in range(1, 7):
            self._cost_list_per_step.append(200 * i + (i - 1) * 60)

    def _build_jackpot(self) -> None:
        jackpot_items = self._jackpot_pool_of()
        idx = datetime.now(timezone.utc).timetuple().tm_yday % len(jackpot_items)
        self.jackpot_item = jackpot_items[idx]

    def _build_wheel_items(self) -> None:
        self._build_jackpot()
        self._part_lottery.add(self.jackpot_item, 1)

        for dij in _wheel_prizes():
            self._part_lottery.add(CountableItem.from_guid(dij["what"], dij["count"]),
                                   dij["weight"])

    @staticmethod
    def last_free_wof_played(user):
        return user.pilot_of().last_free_wof_game

    def push_opening_state(self) -> None:
        mennyiseg = self.jackpot_item.count() if isinstance(self.jackpot_item, CountableItem) else 1

        bw = self._writer.init(
            JackpotKind.Item,
            self.jackpot_item.card_guid_of(),
            mennyiseg,
            self._free_spin_due(),
            self._cost_list_per_step)

        self.user().send(bw)

    def _free_spin_due(self) -> bool:
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        last_free_wof_game_ts = WofProtocol.last_free_wof_played(self.user())

        if last_free_wof_game_ts is None:
            return True
        return last_free_wof_game_ts.local_date < start_of_day

    def read_message(self, msg_type: int, br) -> None:
        client_request = _ClientRequest.from_code(msg_type)
        if client_request == _ClientRequest.RequestInit:
            self._build_jackpot()
            self.push_opening_state()
            self.user().send(self._writer.all_visible_maps)
        elif client_request == _ClientRequest.RequestDraw:
            draw_count = br.read_int32()
            debug_protocol = self.user().protocol_of(ProtocolID.Debug)
            min_level = _wheel_min_level()
            if self.user().pilot_of().skill_book.get() < min_level:
                debug_protocol.tell_console(f'this needs at least level {min_level}')
                return
            last_game = Stamp(datetime.now() - timedelta(days=1)) if self._last_wof_game_session is None \
                else self._last_wof_game_session
            now = Stamp.now()
            duration_millis = last_game.span_ms(now)
            if duration_millis < 2000:
                log.warning("Cheat from_user[%s], Dradiscontact wofspam duration: %s",
                            self.user().user_log(), duration_millis)
            from rebsgo.pilots.state.holdings.walks.shop_walk import ShopWalk
            shop_walker = ShopWalk(self.user(), None, self.ctx.rng)
            self._last_wof_game_session = now

            if draw_count < 1 or draw_count > 6:
                log.warning('%sDraw Request of not allowed draw_count -> Client modification ',
                            self.user().user_log())
                return

            hold = self.user().pilot_of().hold

            is_free_wof_game = self._free_spin_due()
            num_reduction = 2 if is_free_wof_game else 1
            if is_free_wof_game:
                self.user().pilot_of().last_free_wof_game = datetime.now(timezone.utc)
            cubits = hold.holds_stack_of(ResourceKind.Cubits.guid)
            if cubits is None and not is_free_wof_game:
                log.warning('%shold cannot cover the cubit cost - flagging as cheat',
                            self.user().user_log())
                return

            if is_free_wof_game and draw_count == 1:
                costs = 0
            else:
                costs = self._cost_list_per_step[draw_count - num_reduction]

            if costs > 0:
                reduce_successfully = shop_walker.spend_resource(ResourceKind.Cubits, costs)
                if not reduce_successfully:
                    log.warning('dradis anomaly flagged for %s', self.user().user_log())
                    return

            ship_items_to_add = []
            for _i in range(draw_count):
                ship_items_to_add.append(self._part_lottery.random_item())
            self.user().pilot_of().tally_desk.bump_counter(
                TallyCardKind.wof_played, 0, draw_count)

            ship_items_to_add_cleaned = []
            for ship_item in ship_items_to_add:
                if isinstance(ship_item, CountableItem):
                    new_item = CountableItem.from_guid(ship_item.card_guid_of(), ship_item.count())
                else:
                    new_item = ShipSystem.from_guid(ship_item.card_guid_of())
                shop_walker.add_ship_item(new_item, hold)
                ship_items_to_add_cleaned.append(new_item)

            self.user().send(self._writer.wof_draw_reply(JackpotKind.Item, ship_items_to_add_cleaned,
                                                         self.jackpot_item, False))
            log.info('%s has spun the wheel %s times', self.user().user_log_simple, draw_count)
            self.ctx.merok.wof_played(self.user().pilot_of().faction, draw_count)
        else:
            log.info('wheel protocol: nothing handles %s', client_request)

_dijak_cache: list | None = None
_szintkapu_cache: int | None = None


def _wheel_tabla() -> dict:
    return json.loads(GameDataLoader("GameData/templates/wheel_prizes.json")
                      .template_path.read_text(encoding="utf-8"))


def _wheel_min_level() -> int:
    global _szintkapu_cache
    if _szintkapu_cache is None:
        _szintkapu_cache = int(_wheel_tabla().get("minLevel", 5))
    return _szintkapu_cache


def _wheel_prizes() -> list:
    global _dijak_cache
    if _dijak_cache is None:
        nyers = _wheel_tabla()
        _dijak_cache = [
            {"what": (ResourceKind[sor["resource"]] if "resource" in sor else sor["guid"]),
             "count": sor["count"], "weight": sor["weight"]}
            for sor in nyers["prizes"]
        ]
    return _dijak_cache
