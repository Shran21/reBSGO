# github.com/Shran21

from __future__ import annotations

from datetime import timezone
from enum import Enum
from rebsgo.helpers.floats import f32
from rebsgo.pilots.state.whereabouts import AreaPlace
from rebsgo.protocol.wire_base import BgoProtocol
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.reply_base import ReplyBase
from rebsgo.vocabulary.world import PlaceKind
from rebsgo.wire.bytes.outgoing import Outgoing
import logging


class AreaInfo(Outgoing):
    def __init__(self, area_card_guid: int, end_date):
        self._zone_card_guid = area_card_guid
        self._end_date = end_date

    @property
    def zone_card_guid(self) -> int:
        return self._zone_card_guid

    @property
    def end_date(self):
        return self._end_date

    @staticmethod
    def timed_zone(area_card_guid: int, end_date) -> "AreaInfo":
        return AreaInfo(area_card_guid, end_date)

    @staticmethod
    def endless_zone(area_card_guid: int) -> "AreaInfo":
        return AreaInfo(area_card_guid, None)

    def to_wire(self, bw) -> None:
        bw.write_guid(self._zone_card_guid)
        local_end_seconds_unix = 0 if self._end_date is None \
            else int(self._end_date.replace(tzinfo=timezone.utc).timestamp())
        bw.write_uint32(local_end_seconds_unix)

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, AreaInfo):
            return False
        return self._zone_card_guid == other._zone_card_guid and self._end_date == other._end_date

    def __hash__(self) -> int:
        return hash((self._zone_card_guid, self._end_date))


class ServerMessage(Enum):
    ActiveZones = 1
    UpcomingZones = 2
    ScoreKillspam = 3
    ScoreNemesisUpdate = 4
    ScoreSpreeUpdate = 5
    ScoreLeaderUpdate = 6
    ScoreboardUpdate = 7
    FactionBoardUpdate = 8
    FactionBoardTickets = 9
    AdmissionStatus = 10

    def to_wire(self, bw) -> None:
        bw.write_msg_type(self._value_)

    @classmethod
    def from_code(cls, value: int) -> "ServerMessage | None":
        return _BY_VALUE.get(value)


class TournamentStanding(Outgoing):
    def __init__(self, player_id: int, join_rank: int, score: float, kills: int, deaths: int):
        self._player_id = player_id
        self._join_rank = join_rank
        self._score = f32(score)
        self._kills = kills
        self._deaths = deaths

    @property
    def player_id(self) -> int:
        return self._player_id

    @property
    def join_rank(self) -> int:
        return self._join_rank

    @property
    def score(self) -> float:
        return self._score

    @property
    def kills(self) -> int:
        return self._kills

    @property
    def deaths(self) -> int:
        return self._deaths

    def to_wire(self, bw) -> None:
        (bw
         .write_uint32(self._player_id)
         .write_uint32(self._join_rank)
         .write_single(self._score)
         .write_uint32(self._kills)
         .write_uint32(self._deaths))

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, TournamentStanding):
            return False
        return (self._player_id == other._player_id and self._join_rank == other._join_rank
                and self._score == other._score and self._kills == other._kills
                and self._deaths == other._deaths)

    def __hash__(self) -> int:
        return hash((self._player_id, self._join_rank, self._score, self._kills, self._deaths))

    def __repr__(self) -> str:
        return (f'<#{self._join_rank} pilot {self._player_id}: {self._score} points, '
                f'{self._kills} kills, {self._deaths} deaths>')


class ZoneReplies(ReplyBase):
    UZENETEK = {
        "active_zones": (ServerMessage.ActiveZones.value, [('desc_collection', 'zone_descs')]),
        "upcoming_zones": (ServerMessage.UpcomingZones.value, [('desc_collection', 'upcoming_zone_descs')]),
        "score_kill_spam": (ServerMessage.ScoreKillspam.value, [('desc', 'kill_spam_server_message')]),
        "score_nemesis_update": (ServerMessage.ScoreNemesisUpdate.value, [('boolean', 'add_nemesis'), ('uint32_collection', 'player_ids')]),
        "score_spree_update": (ServerMessage.ScoreSpreeUpdate.value, [('boolean', 'add_spree'), ('uint32_collection', 'player_ids')]),
        "score_leader_update": (ServerMessage.ScoreLeaderUpdate.value, [('uint32', 'player_tournament_leader_id')]),
        "scoreboard_update": (ServerMessage.ScoreboardUpdate.value, [('desc_collection', 'tournament_ranking_datas')]),
        "admission_status": (ServerMessage.AdmissionStatus.value, [('guid', 'guid'), ('boolean', 'has_paid_admission')]),
    }

    def __init__(self):
        super().__init__(ProtocolID.Zone)


log = logging.getLogger(__name__)


class _ClientMessage(Enum):
    Join = 1
    Leave = 2
    ScoreboardSubscribe = 3
    ScoreboardUnsubscribe = 4
    UseFtlOverride = 5
    AdmissionStatus = 6

    @staticmethod
    def from_code(uzenet_kod: int):
        return _CM_BY_VALUE.get(uzenet_kod)


_BY_VALUE = {tag.value: tag for tag in _ClientMessage}
_CM_BY_VALUE = {member.value: member for member in _ClientMessage}


class ZoneProtocol(BgoProtocol):
    def __init__(self, ctx):
        super().__init__(ProtocolID.Zone, ctx)
        self._writer = ZoneReplies()

    @property
    def replies(self) -> ZoneReplies:
        return self._writer

    def read_message(self, msg_type: int, br) -> None:
        client_message = _ClientMessage.from_code(msg_type)
        if client_message is None:
            return

        log.info('zone channel: %s', client_message)

        if client_message == _ClientMessage.AdmissionStatus:
            zone_guid = br.read_guid()
            log.info('admission status asked: %s %s', self.user().user_log_simple, zone_guid)
        elif client_message == _ClientMessage.Join:
            zone_guid = br.read_guid()
            log.info('zone entry %s %s', self.user().user_log_simple, zone_guid)

            if self.user().pilot_of().location.game_location != PlaceKind.Room:
                log.warning('%s station exit from someone who is not stationed'
                            ' there; they are %s',
                            self.user().pilot_of().player_log,
                            self.user().pilot_of().location.game_location)
                return

            try:
                ship = self.user().pilot_of().hangar_of().active_ship()
                if ship.ship_stats().hp == 0:
                    ship.ship_stats().set_hull(1)
            except Exception:
                log.exception('the zone handler fell over')

            location = self.user().pilot_of().location
            location.switch_state(AreaPlace(location))
            scene_protocol = self.user().protocol_of(ProtocolID.Scene)
            scene_protocol.push_scene_change()
        elif client_message == _ClientMessage.Leave:
            log.info("Leave zone %s", self.user().user_log_simple)
        elif client_message in (_ClientMessage.ScoreboardSubscribe, _ClientMessage.ScoreboardUnsubscribe):
            self._scoreboard_handling(client_message == _ClientMessage.ScoreboardSubscribe)
        else:
            log.warning("ZoneProtocol: could not find msg_type: %s", msg_type)

    def _scoreboard_handling(self, is_subscribe: bool) -> None:
        if is_subscribe:
            pass
        else:
            pass
