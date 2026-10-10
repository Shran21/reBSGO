# github.com/Shran21

from __future__ import annotations

import logging
import shlex

from rebsgo import journal
from rebsgo.helpers.dice import Dice
from rebsgo.pilots.state.permissions import AdminPowers
from rebsgo.protocol.debug.console_commands import DebugProtocol, operator_aliases
from rebsgo.protocol.debug.debug_replies import DebugReplies
from rebsgo.protocol.debug.refunds import Refunds
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.runtime.server_handles import ServerHandles
from rebsgo.vocabulary.pilot import Faction, ServerRoles

log = logging.getLogger(__name__)


class _ArgsExhausted(Exception):
    pass


class _NeedsGameSession(Exception):
    pass


class _LineReader:
    def __init__(self, args):
        self._args = list(args)

    def read_string(self) -> str:
        if not self._args:
            raise _ArgsExhausted()
        return self._args.pop(0)


class _EchoWriter(DebugReplies):
    def message(self, msg):
        bw = super().message(msg)
        bw.echo_text = str(msg)
        return bw

    def command(self, msg):
        bw = super().command(msg)
        bw.echo_text = str(msg)
        return bw


class _AbsentProtocol:
    def __getattr__(self, name):
        raise _NeedsGameSession(name)


class _PaperPilot:
    def __init__(self, pilot_id: int, name: str, role_bits: int, faction_code: int):
        self._id = int(pilot_id)
        self.name = str(name)
        self.bgo_admin_roles = AdminPowers(int(role_bits or 0))
        self.faction = Faction.from_code(int(faction_code or 0))

    def user_id_of(self) -> int:
        return self._id

    @property
    def player_log(self) -> str:
        return f"[{self.name}:{self._id}]"


class _GhostSeat:
    def __init__(self, real_seat, player, lines: list):
        self._real = real_seat
        self._player = player
        self._lines = lines

    def pilot_of(self):
        return self._player

    def user_log(self) -> str:
        return f"[panel {self._player.name}:{self._player.user_id_of()}]"

    @property
    def user_log_simple(self) -> str:
        return self.user_log()

    def connection(self):
        return self._real.connection() if self._real is not None else None

    def is_connected(self) -> bool:
        return self._real is not None and self._real.is_connected()

    def send(self, kimenet) -> bool:
        text = getattr(kimenet, "echo_text", None)
        if text is not None:
            self._lines.append(text)
            return True
        if self._real is not None:
            return self._real.send(kimenet)
        return True

    def protocol_of(self, protocol_id):
        if self._real is not None:
            return self._real.protocol_of(protocol_id)
        raise _NeedsGameSession(str(protocol_id))


class _PanelConsole(DebugProtocol):
    def __init__(self, ctx, pilot_roster, sector_book, nemitas, visszaterito, lines):
        super().__init__(ctx, pilot_roster, sector_book, nemitas, visszaterito)
        self._writer = _EchoWriter()
        self._lines = lines

    def tell_console(self, szoveg) -> None:
        self._lines.append(str(szoveg))


class ConsoleGateway:
    def __init__(self, pilot_roster, sector_book, nemitas, catalogue,
                 server_config, timetable, merok, galaxy, data_source=None):
        self._pilot_roster = pilot_roster
        self._sector_book = sector_book
        self._chat_access_blocker = nemitas
        self._catalogue = catalogue
        self._server_config = server_config
        self._timetable = timetable
        self._merok = merok
        self._galaxy = galaxy
        self._data_source = data_source


    def _pilot_on_record(self, pilot_id: int):
        if self._data_source is None:
            return None
        conn = self._data_source.connection()
        try:
            sor = conn.execute(
                "SELECT name, roles_bits, faction FROM pilots WHERE id=?",
                (int(pilot_id),)).fetchone()
        finally:
            conn.close()
        if sor is None:
            return None
        return _PaperPilot(pilot_id, sor["name"], sor["roles_bits"], sor["faction"])

    def command_names(self) -> dict:
        return {
            "developer": sorted(DebugProtocol.DEV_PARANCSOK),
            "console": sorted(DebugProtocol.PARANCSOK),
            "aliases": dict(operator_aliases()),
        }


    def run(self, pilot_id: int, line: str) -> dict:
        try:
            words = shlex.split(str(line or ""))
        except ValueError as baj:
            return {"ok": False, "lines": [f"unbalanced quoting: {baj}"]}
        if not words:
            return {"ok": False, "lines": ["nothing to run"]}
        command, args = words[0], words[1:]

        seat = self._pilot_roster.by_id(int(pilot_id))
        if seat is not None and seat.pilot_of() is None:
            seat = None
        player = seat.pilot_of() if seat is not None else self._pilot_on_record(pilot_id)
        if player is None:
            return {"ok": False, "lines": ["no such pilot on record"]}

        roles = player.bgo_admin_roles
        is_console = roles.wears_role(ServerRoles.Console)
        is_moderator = roles.wears_role(ServerRoles.Mod)
        if not is_console or is_moderator:
            journal.audit().warning(
                'panel console refused for want of rank: [%s:%s] %s',
                player.name, player.user_id_of(), line)
            return {"ok": False, "lines": ["your rank does not cover the console"]}

        lines: list = []
        ghost = _GhostSeat(seat, player, lines)
        ctx = ServerHandles(None, self._catalogue, self._server_config,
                            self._timetable, self._merok, Dice(), self._galaxy, ghost)
        console = _PanelConsole(ctx, self._pilot_roster, self._sector_book,
                                self._chat_access_blocker, Refunds(self._catalogue),
                                lines)

        command = operator_aliases().get(command, command)
        journal.audit().info('[panel %s:%s] console command %s %s',
                             player.name, player.user_id_of(), command,
                             " ".join(args))

        if seat is not None:
            try:
                player_protocol = seat.protocol_of(ProtocolID.Pilot)
            except Exception:
                player_protocol = _AbsentProtocol()
        else:
            player_protocol = _AbsentProtocol()

        reader = _LineReader(args)
        talalt = False
        try:
            if roles.wears_role(ServerRoles.Developer):
                talalt = console.read_dev_command(reader, command)
            if console._parse_command(reader, command, player, roles, player_protocol):
                talalt = True
        except _ArgsExhausted:
            lines.append("the command wants more arguments than that")
            talalt = True
        except _NeedsGameSession:
            lines.append("that one only works from inside the game")
            talalt = True
        except Exception as trouble:
            log.exception('panel console command fell over: %s', command)
            lines.append(f"the command fell over: {trouble}")
            talalt = True
        if not talalt:
            lines.append(f"unknown command: {command}")
        return {"ok": True, "found": talalt, "lines": lines}
