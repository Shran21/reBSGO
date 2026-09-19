# github.com/Shran21
from __future__ import annotations

import logging
from enum import Enum

from rebsgo.pilots.state.whereabouts import InSpace
from rebsgo.protocol.wire_base import BgoProtocol
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.vocabulary.pilot import Faction
from rebsgo.vocabulary.world import PlaceKind

log = logging.getLogger(__name__)


class _ClientMessage(Enum):
    Talk = 0
    NpcMarks = 2
    EnterDoor = 4
    Quit = 5
    Enter = 6

    @staticmethod
    def from_code(uzenet_kod: int):
        return _CM_BY_VALUE.get(uzenet_kod)


class _ServerMessage(Enum):
    Talk = 1
    NpcMarks = 3


_CM_BY_VALUE = {member.value: member for member in _ClientMessage}


class RoomProtocol(BgoProtocol):
    def __init__(self, ctx):
        super().__init__(ProtocolID.Room, ctx)

    def read_message(self, msg_type: int, br) -> None:
        client_message = _ClientMessage.from_code(msg_type)
        if client_message is None:
            raise TypeError(f'client message: {msg_type}')

        scene_protocol = self.user().protocol_of(ProtocolID.Scene)
        if client_message == _ClientMessage.Talk:
            npc = br.read_string()
            log.info('opening a conversation with %s', npc)
            frakcio = self.user().pilot_of().faction
            from rebsgo.services import Services
            from rebsgo.pilots.talking.dialog_trees import DialogTrees, TalkState
            trees = Services.get(DialogTrees)
            npc_key = trees.key_for_name(npc)
            tree = trees.get(npc_key) if npc_key else None
            if tree is None:
                try:
                    room_guid = self.user().pilot_of().location.room_guid()
                except Exception:
                    room_guid = 0
                if room_guid == 50000011:
                    npc_key, tree = "npc_humanoutpost", trees.get("npc_humanoutpost")
                elif room_guid == 50000010:
                    npc_key, tree = "npc_no8outpost", trees.get("npc_no8outpost")
            if tree is None:
                log.debug("No dialog tree for npc %s (key=%s)", npc, npc_key)
                return
            is_capital_npc = ((npc == "Adama" and frakcio == Faction.Colonial)
                              or (npc == "No1" and frakcio == Faction.Cylon))
            if is_capital_npc:
                from rebsgo.world.capitals.capital_roster import CapitalRoster
                Services.get(CapitalRoster).offer(self.user().pilot_of().user_id_of())
            Services.get(TalkState).start(self.user().pilot_of().user_id_of(), npc_key)
            self.user().send(self.write_talk(npc))
            dialog_protocol = self.user().protocol_of(ProtocolID.Dialog)
            dialog_protocol.send_tree_menu(tree)
            return
        elif client_message == _ClientMessage.Quit:
            if self.user().pilot_of().location.game_location != PlaceKind.Room:
                log.error('%s station exit from someone who is not stationed'
                          ' there; they are %s',
                          self.user().pilot_of().player_log,
                          self.user().pilot_of().location.game_location)
                return

            log.info('leaving the station rooms')
            try:
                ship = self.user().pilot_of().hangar_of().active_ship()
                if ship.ship_stats().hp == 0:
                    ship.ship_stats().set_hull(1)
            except Exception:
                log.exception('the station handler fell over')

            location = self.user().pilot_of().location
            self._redirect_capital_undock(location)
            location.switch_state(InSpace(location))
            scene_protocol.push_scene_change()
        elif client_message == _ClientMessage.Enter:
            pass
        else:
            log.warning(f'station protocol has no branch for: {msg_type}')

    def _redirect_capital_undock(self, location) -> None:
        try:
            from rebsgo.world.capitals.capital_roster import CAPITAL_SECTOR, CAPITAL_SLOT
            player = self.user().pilot_of()
            active = player.hangar_of().active_ship()
            if active is None or active.server_id != CAPITAL_SLOT:
                return
            home_sector = CAPITAL_SECTOR.get(player.faction, -1)
            if home_sector == -1:
                return
            csillag = self.ctx.galaxy.map_card.stars.get(home_sector)
            if csillag is None:
                return
            location.place_in_sector(home_sector, csillag.sector_guid, 0)
            log.info("Capital commander %s undocking into home sector %s",
                     self.user().user_log(), home_sector)
        except Exception:
            log.exception("capital undock redirect failed")

    def write_talk(self, npc: str):
        bw = self.new_message()
        bw.write_msg_type(_ServerMessage.Talk.value)
        bw.write_string(npc)
        return bw
