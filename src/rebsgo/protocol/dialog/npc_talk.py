# github.com/Shran21
from __future__ import annotations

from contextlib import suppress

import logging
from enum import Enum

from rebsgo.protocol.wire_base import BgoProtocol
from rebsgo.protocol.dialog.assignment_giver import AssignmentGiver
from rebsgo.protocol.dialog.dialogue_line import Remark
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.protocol_book_replies import replies_for
from rebsgo.vocabulary.pilot import Faction

log = logging.getLogger(__name__)


class DialogProtocol(BgoProtocol):
    class ServerMessage(Enum):
        NpcRemark = 0
        PcRemarks = 1
        Stopped = 2
        Action = 3

        @staticmethod
        def from_code(value: int):
            return list(DialogProtocol.ServerMessage)[value]

    class ClientMessage(Enum):
        Say = 0
        Advance = 1
        Stop = 2

        @staticmethod
        def from_code(value: int):
            if value < 0 or value > 2:
                return None
            return list(DialogProtocol.ClientMessage)[value]

    def __init__(self, ctx):
        super().__init__(ProtocolID.Dialog, ctx)
        self._assignment_desk = None

    def seed_user(self, user) -> None:
        super().seed_user(user)
        self._assignment_desk = AssignmentGiver(self.user().pilot_of(), self.ctx.galaxy, self.ctx.rng)

    def read_message(self, msg_type: int, br) -> None:
        client_message = DialogProtocol.ClientMessage.from_code(msg_type)
        if client_message is None:
            return

        if client_message == DialogProtocol.ClientMessage.Say:
            sorszam = br.read_byte()
            log.debug('%sdialog line %s', self.user().user_log(), sorszam)
            if self._handle_tree_say(sorszam):
                return
            if self._try_take_capital_ship():
                return
            if sorszam != 1:
                log.warning('%sindex out of range %s', self.user().user_log(), sorszam)
                return
            self.user().send(self.push_talk_over())
            self._do_get_assignments()
        elif client_message == DialogProtocol.ClientMessage.Advance:
            log.debug("%s Dialog Advance (no-op - see comment)", self.user().user_log())
        elif client_message == DialogProtocol.ClientMessage.Stop:
            self._clear_capital_offer()
            self._clear_dialog_state()
            self.user().send(self.push_talk_over())
        else:
            log.warning('%sdialog protocol met an unsupported revision %s',
                        self.user().user_log(), msg_type)

    def _dialog_trees(self):
        from rebsgo.services import Services
        from rebsgo.pilots.talking.dialog_trees import DialogTrees
        return Services.get(DialogTrees)

    def _dialog_state(self):
        from rebsgo.services import Services
        from rebsgo.pilots.talking.dialog_trees import TalkState
        return Services.get(TalkState)

    def _clear_dialog_state(self) -> None:
        with suppress(Exception):
            self._dialog_state().clear(self.user().pilot_of().user_id_of())

    _ACTION_SYMBOL = {
        "get_assignments": "daily_missions",
        "dradis_contact": "dradis",
        "capital": "rent_battlestar",
    }

    _SYMBOL_DIALOG_ACTION = {
        "ship_repair": 2,
        "ship_item": 1,
        "ship_hangar": 6,
        "ship_customization": 5,
    }

    @staticmethod
    def _topic_symbol(topic) -> str:
        if topic.get("symbol"):
            return topic["symbol"]
        return DialogProtocol._ACTION_SYMBOL.get(topic.get("action"), "")

    def send_tree_menu(self, tree) -> None:
        greeting = tree.get("greeting")
        if greeting:
            self.user().send(self.push_npc_remark(Remark(0, greeting, "")))
        topics = tree.get("topics") or []
        if topics:
            remarks = [Remark(i, t["q"], self._topic_symbol(t)) for i, t in enumerate(topics)]
            self.user().send(self.push_pc_remarks(remarks))

    def _handle_tree_say(self, index: int) -> bool:
        try:
            user_id = self.user().pilot_of().user_id_of()
            npc_key = self._dialog_state().get(user_id)
            if npc_key is None:
                return False
            tree = self._dialog_trees().get(npc_key)
            topics = (tree or {}).get("topics") or []
            if not tree or index < 0 or index >= len(topics):
                return False
            topic = topics[index]
            action = topic.get("action")
            if action == "capital":
                if self._try_take_capital_ship():
                    self._clear_dialog_state()
                    return True
            elif action == "get_assignments":
                self._do_get_assignments()
            elif action == "shop":
                if (da := self._SYMBOL_DIALOG_ACTION.get(topic.get('symbol'))) is not None:
                    self.user().send(self.write_action(da))
                    self._clear_dialog_state()
                    return True
            valasz = topic.get("a")
            if valasz:
                self.user().send(self.push_npc_remark(Remark(0, valasz, "")))
            self.send_tree_menu(tree)
            return True
        except Exception:
            log.exception("dialog tree say failed")
            return False

    def _do_get_assignments(self) -> None:
        player = self.user().pilot_of()
        updated = self._assignment_desk.refresh_missions()
        log.debug('assignments moved on: %s', updated)
        if updated:
            pw = replies_for(ProtocolID.Pilot)
            self.user().send(pw.missions(player.tally_desk.mission_book))

    def _capital_desk(self):
        from rebsgo.services import Services
        from rebsgo.world.capitals.capital_roster import CapitalRoster
        return Services.get(CapitalRoster)

    def _clear_capital_offer(self) -> None:
        with suppress(Exception):
            self._capital_desk().clear_offer(self.user().pilot_of().user_id_of())

    def _try_take_capital_ship(self) -> bool:
        player = self.user().pilot_of()
        if not self._capital_desk().consume_offer(player.user_id_of()):
            return False
        player_protocol = self.user().protocol_of(ProtocolID.Pilot)
        status = "error"
        try:
            status = player_protocol.take_capital_ship()
        except Exception:
            log.exception("capital ship take failed")
        if status == "error":
            return True
        colonial = player.faction == Faction.Colonial
        if status == "poor":
            kulcs = ("%$bgo.npc_adama.Phrase__ac043882-f184-4036-a8f4-2a0abc98d4db__0%" if colonial
                   else "%$bgo.npc_no1.Phrase__17772a8a-7a05-44c4-aad5-70f5178f7c35__0%")
        else:
            kulcs = ("%$bgo.npc_adama.Phrase__cc0d3112-1e80-4db8-b9f8-74efa760fa6d__2%" if colonial
                   else "%$bgo.npc_no1.Phrase__50100902-f5dc-41d3-8d09-1b0035b20485__0%")
        self.user().send(self.push_npc_remark(Remark(1, kulcs, "")))
        self.user().send(self.push_talk_over())
        return True

    def push_talk_over(self):
        bw = self.new_message()
        bw.write_msg_type(DialogProtocol.ServerMessage.Stopped.value)
        return bw

    def push_npc_remark(self, remark):
        bw = self.new_message()
        bw.write_msg_type(DialogProtocol.ServerMessage.NpcRemark.value)
        bw.write_desc(remark)
        return bw

    def push_pc_remarks(self, megjegyzesek):
        bw = self.new_message()
        bw.write_msg_type(DialogProtocol.ServerMessage.PcRemarks.value)
        bw.write_desc_collection(megjegyzesek)
        return bw

    def write_action(self, dialog_action: int):
        bw = self.new_message()
        bw.write_msg_type(DialogProtocol.ServerMessage.Action.value)
        bw.write_byte(int(dialog_action))
        return bw
