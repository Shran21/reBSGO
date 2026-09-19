# github.com/Shran21

from __future__ import annotations

from rebsgo.pilots.state.watching import InfoBroadcast
from rebsgo.protocol.watching.watching import InfoKind
from rebsgo.vocabulary.pilot import Faction, AvatarItem
from types import MappingProxyType
from rebsgo.wire.bytes.incoming import Incoming
from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.vocabulary.combat import AssistMedal, KillerMedal, PvpMedal, TournamentMedal


class PilotAvatar(InfoBroadcast):
    def __init__(self, player_id: int, kezdo_avatar: AvatarLook):
        super().__init__(InfoKind.Avatar, player_id, kezdo_avatar)


class PilotClan(InfoBroadcast):
    def __init__(self, player_id: int, kezdo_adat):
        super().__init__(InfoKind.Wing, player_id, kezdo_adat)


class PilotFaction(InfoBroadcast):
    def __init__(self, player_id: int, kezdo_frakcio: Faction):
        super().__init__(InfoKind.Faction, player_id, kezdo_frakcio)


class PilotMedals(InfoBroadcast):
    def __init__(self, player_id: int, kezdo_ermek: MedalProgress):
        super().__init__(InfoKind.Medal, player_id, kezdo_ermek)


class PilotName(InfoBroadcast):
    def __init__(self, player_id: int, initial_name: str):
        super().__init__(InfoKind.Name, player_id, initial_name)

    @property
    def has_name(self) -> bool:
        return self.current_info != ""

    def __str__(self) -> str:
        return self.current_info


class AvatarItems(Incoming, Outgoing):
    def __init__(self):
        self.items: dict[AvatarItem, str] = {}

    def read(self, br) -> None:
        darab = br.read_length()
        for _ in range(darab):
            avatar_item = AvatarItem.from_code(br.read_byte())
            self.items[avatar_item] = br.read_string()

    def to_wire(self, bw) -> None:
        bw.write_length(len(self.items))
        for kulcs, value in self.items.items():
            bw.write_byte(kulcs.value)
            bw.write_string(value)


class MedalProgress:
    def __init__(self, pvp_medal: PvpMedal = PvpMedal.None_, tournament_medal: TournamentMedal = TournamentMedal.None_,
                 killer_medal: KillerMedal = KillerMedal.None_, assist_medal: AssistMedal = AssistMedal.None_):
        self._pvp_medal = pvp_medal
        self._tournament_medal = tournament_medal
        self._killer_medal = killer_medal
        self._assist_medal = assist_medal

    @property
    def pvp_medal(self) -> PvpMedal:
        return self._pvp_medal

    @property
    def tournament_medal(self) -> TournamentMedal:
        return self._tournament_medal

    @property
    def killer_medal(self) -> KillerMedal:
        return self._killer_medal

    @property
    def assist_medal(self) -> AssistMedal:
        return self._assist_medal

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if not isinstance(other, MedalProgress):
            return False
        return (self._pvp_medal == other._pvp_medal and self._tournament_medal == other._tournament_medal
                and self._killer_medal == other._killer_medal and self._assist_medal == other._assist_medal)

    def __hash__(self) -> int:
        return hash((self._pvp_medal, self._tournament_medal, self._killer_medal, self._assist_medal))


class AvatarLook(AvatarItems):
    def replace_avatar(self, map) -> None:
        self.items.clear()
        self.items.update(map)

    def read(self, br) -> None:
        super().read(br)
        szam = br.read_length()
        br.read_nbytes(szam)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_length(0)

    @property
    def unmodifiable_items(self):
        return MappingProxyType(self.items)
