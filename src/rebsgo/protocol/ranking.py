# github.com/Shran21

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from rebsgo.protocol.wire_base import BgoProtocol
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.reply_base import ReplyBase
from rebsgo.vocabulary.pilot import StandingGroup, StandingKind
from rebsgo.wire.bytes.outgoing import Outgoing
import logging


class RankInfo(Outgoing):
    def __init__(self, rank: int, player_id: int, name: str, faction,
                 score1: float, score2: float, score3: float):
        self._rank = rank
        self._player_id = player_id
        self._name = name
        self._faction = faction
        self._score1 = score1
        self._score2 = score2
        self._score3 = score3

    @property
    def rank(self) -> int:
        return self._rank

    @property
    def player_id(self) -> int:
        return self._player_id

    def name(self) -> str:
        return self._name

    def faction(self):
        return self._faction

    @property
    def score1(self) -> float:
        return self._score1

    @property
    def score2(self) -> float:
        return self._score2

    @property
    def score3(self) -> float:
        return self._score3

    def to_wire(self, bw) -> None:
        bw.write_uint32(self._rank)
        bw.write_uint32(self._player_id)
        bw.write_string(self._name)
        bw.write_uint32(self._faction.value)
        bw.write_double(self._score1)
        bw.write_double(self._score2)
        bw.write_double(self._score3)

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, RankInfo):
            return False
        return (self._rank == other._rank and self._player_id == other._player_id and self._name == other._name
                and self._faction == other._faction and self._score1 == other._score1
                and self._score2 == other._score2 and self._score3 == other._score3)

    def __hash__(self) -> int:
        return hash((self._rank, self._player_id, self._name, self._faction,
                     self._score1, self._score2, self._score3))


class ServerMessage(Enum):
    ReplyRankingTab = 4
    ReplyPlayerRank = 6
    ReplyRankingCounter = 8
    ReplyRankingCounterPlayer = 10
    ReplyRankingTournament = 12
    ReplyRankingTournamentPlayer = 14

    @property
    def short_value(self) -> int:
        return self._value_

    @classmethod
    def from_code(cls, value: int) -> "ServerMessage | None":
        return _BY_VALUE.get(value)


@dataclass
class StandingRow(Outgoing):
    ranking_group: object
    ranking_type: object
    rank_descriptions: list = field(default_factory=list)
    total_entries: int = 0
    last_update: object = None

    def to_wire(self, bw) -> None:
        bw.write_uint16(self.ranking_group.value)
        bw.write_uint16(self.ranking_type.value)
        bw.write_desc_collection(self.rank_descriptions)
        bw.write_uint32(self.total_entries)
        bw.write_date_time(self.last_update)


@dataclass
class TournamentRow(Outgoing):
    ranking_group: int
    ranking_type: int
    bracket_id: int
    rank_descriptions: list = field(default_factory=list)
    total_entries: int = 0
    last_update: object = None

    def to_wire(self, bw) -> None:
        bw.write_uint16(int(self.ranking_group))
        bw.write_uint16(int(self.ranking_type) & 0xFFFF)
        bw.write_uint16(int(self.bracket_id))
        bw.write_desc_collection(self.rank_descriptions)
        bw.write_uint32(self.total_entries)
        bw.write_date_time(self.last_update)


class RankingReplies(ReplyBase):
    UZENETEK = {
        "ranking_group": (
            ServerMessage.ReplyRankingCounter.short_value,
            [("desc", "ranking_group_record")]),
        "reply_ranking_counter_player": (
            ServerMessage.ReplyRankingCounterPlayer.short_value,
            [("uint32", "rank"), ("uint32", "position"), ("double", "score1"),
             ("double", "score2"), ("double", "score3")]),
        "ranking_tournament": (
            ServerMessage.ReplyRankingTournament.short_value,
            [("desc", "tournament_record")]),
        "reply_ranking_tournament_player": (
            ServerMessage.ReplyRankingTournamentPlayer.short_value,
            [("uint32", "rank"), ("uint32", "position"), ("double", "score1"),
             ("double", "score2"), ("double", "score3")]),
    }

    def __init__(self):
        super().__init__(ProtocolID.Ranking)


log = logging.getLogger(__name__)


class _ClientMessage(Enum):
    RequestRankingTab = 3
    RequestPlayerRank = 5
    RequestRankingCounter = 7
    RequestRankingCounterPlayer = 9
    RequestRankingTournament = 11
    RequestRankingTournamentPlayer = 13

    @staticmethod
    def from_code(value: int):
        return _CM_BY_VALUE.get(value)


_BY_VALUE = {tag.value: tag for tag in _ClientMessage}
_CM_BY_VALUE = {member.value: member for member in _ClientMessage}


class RankingProtocol(BgoProtocol):
    def __init__(self, ctx):
        super().__init__(ProtocolID.Ranking, ctx)
        self._writer = RankingReplies()

    @property
    def replies(self) -> RankingReplies:
        return self._writer

    def read_message(self, msg_type: int, br) -> None:
        client_message = _ClientMessage.from_code(msg_type)
        if client_message is None:
            log.warning('%s standings met a client message it cannot read: %s',
                        self.user().pilot_of().player_log, msg_type)
            return

        if client_message == _ClientMessage.RequestRankingCounter:
            raw_ranking_group = br.read_uint16()
            raw_ranking_type = br.read_uint16()
            page = br.read_uint32()
            br.read_byte()

            send_values_invalid = False
            if raw_ranking_group > 13:
                send_values_invalid = True
            if raw_ranking_type > 1:
                send_values_invalid = True
            if send_values_invalid:
                log.warning('standings request carried unusable values %s',
                            self.user().pilot_of().player_log)
                return

            ranking_group = StandingGroup.from_code(raw_ranking_group)
            ranking_type = StandingKind.from_code(raw_ranking_type)
            if ranking_group is None or ranking_type is None:
                return
            feljegyzes = self._ranking_history().ranking_group_record(ranking_group, ranking_type, page)
            self.user().send(self._writer.ranking_group(feljegyzes))
        elif client_message == _ClientMessage.RequestRankingCounterPlayer:
            raw_ranking_group = br.read_uint16()
            raw_ranking_type = br.read_uint16()
            br.read_byte()
            if raw_ranking_group > 13 or raw_ranking_type > 1:
                return
            ranking_group = StandingGroup.from_code(raw_ranking_group)
            if ranking_group is None:
                return
            rank, helyzet, score1, score2, score3 = self._ranking_history().player_entry(
                ranking_group, self.user().pilot_of().user_id_of(),
                StandingKind.from_code(raw_ranking_type))
            self.user().send(self._writer.reply_ranking_counter_player(
                rank, helyzet, score1, score2, score3))

        elif client_message == _ClientMessage.RequestRankingTournament:
            osztaly = br.read_int16()
            szezon = br.read_int16()
            bracket = br.read_uint16()
            page = br.read_uint32()
            br.read_byte()
            sorok, osszes, mikor = self._tournament_log().board(osztaly, szezon, page)
            self.user().send(self._writer.ranking_tournament(
                TournamentRow(osztaly, szezon, bracket, sorok, osszes, mikor)))
        elif client_message == _ClientMessage.RequestRankingTournamentPlayer:
            osztaly = br.read_int16()
            szezon = br.read_int16()
            br.read_uint16()
            br.read_byte()
            rank, helyzet, score1, score2, score3 = self._tournament_log().player_entry(
                osztaly, szezon, self.user().pilot_of().user_id_of())
            self.user().send(self._writer.reply_ranking_tournament_player(
                rank, helyzet, score1, score2, score3))

    @staticmethod
    def _tournament_log():
        from rebsgo.services import Services
        from rebsgo.pilots.standings.tournament_log import TournamentLog
        return Services.get(TournamentLog)

    @staticmethod
    def _ranking_history():
        from rebsgo.services import Services
        from rebsgo.pilots.standings.ranking_log import RankingLog
        return Services.get(RankingLog)
