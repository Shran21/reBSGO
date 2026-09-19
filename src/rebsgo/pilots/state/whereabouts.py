# github.com/Shran21

from __future__ import annotations

from abc import abstractmethod
from rebsgo.pilots.state.watching import InfoBroadcast
from rebsgo.protocol.watching.watching import InfoKind
from rebsgo.vocabulary.pilot import Faction
from rebsgo.gamedata.from_json.template_readers import world_places
from rebsgo.vocabulary.world import PlaceKind, WellKnownCard, SceneChange
from rebsgo.wire.bytes.outgoing import Outgoing


class PlaceState(Outgoing):
    def __init__(self, location, game_location, trans_scene_type):
        self._location = location
        self._game_location = game_location
        self._trans_scene_type = trans_scene_type

    def to_wire(self, bw) -> None:
        bw.write_byte(self._trans_scene_type.value)
        bw.write_byte(self._game_location.value)

    @abstractmethod
    def process(self, bw) -> None:
        ...

    def notify_place_watcher(self, bw) -> None:
        bw.write_byte(self._game_location.value)

    @property
    def game_location(self):
        return self._game_location

    @property
    def location(self):
        return self._location


class ArenaLocation(PlaceState):
    def __init__(self, location, faction_group_flag: int):
        super().__init__(location, PlaceKind.Arena, SceneChange.Undock)
        self._faction_group_flag = 1 if faction_group_flag else 0

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_uint32(self._location.sector_id)
        bw.write_guid(self._location.sector_guid)
        bw.write_byte(self._faction_group_flag)

    def process(self, bw) -> None:
        self.to_wire(bw)

    def notify_place_watcher(self, bw) -> None:
        super().notify_place_watcher(bw)
        bw.write_guid(self._location.sector_guid)


class AtAvatar(PlaceState):
    def __init__(self, location):
        super().__init__(location, PlaceKind.Avatar, SceneChange.FirstStory)

    def process(self, bw) -> None:
        self.to_wire(bw)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_length(0)
        bw.write_boolean(False)


class Offline(PlaceState):
    def __init__(self, location, elozo_szinter):
        super().__init__(location, PlaceKind.Disconnect, elozo_szinter)

    def process(self, bw) -> None:
        pass


class InRoom(PlaceState):
    def __init__(self, location, trans_scene_type):
        super().__init__(location, PlaceKind.Room, trans_scene_type)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_guid(self.room_guid())
        bw.write_uint32(self._location.sector_id)

    def process(self, bw) -> None:
        self.to_wire(bw)

    @abstractmethod
    def room_guid(self) -> int:
        ...

    def notify_place_watcher(self, bw) -> None:
        super().notify_place_watcher(bw)
        bw.write_guid(self._location.sector_guid)
        bw.write_guid(self._location.room_guid())


class InSpace(PlaceState):
    def __init__(self, location):
        super().__init__(location, PlaceKind.Space, SceneChange.Undock)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_uint32(self._location.sector_id)
        bw.write_guid(self._location.sector_guid)

    def process(self, bw) -> None:
        self.to_wire(bw)

    def notify_place_watcher(self, bw) -> None:
        super().notify_place_watcher(bw)
        bw.write_guid(self._location.sector_guid)


class AtStarter(PlaceState):
    _KOZOS_AJANDEK = WellKnownCard.NeutralRewardCard.value

    def __init__(self, location, colonial_bonus_guid=_KOZOS_AJANDEK,
                 cylon_bonus_guid=_KOZOS_AJANDEK):
        super().__init__(location, PlaceKind.Starter, SceneChange.Teaser)
        self._colonial_bonus_guid = colonial_bonus_guid
        self._cylon_bonus_guid = cylon_bonus_guid

    def process(self, bw) -> None:
        self.to_wire(bw)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_guid(self._colonial_bonus_guid)
        bw.write_guid(self._cylon_bonus_guid)


class AreaPlace(PlaceState):
    def __init__(self, location):
        super().__init__(location, PlaceKind.Zone, SceneChange.Tournament)

    def to_wire(self, bw) -> None:
        super().to_wire(bw)
        bw.write_uint32(self._location.sector_id)
        bw.write_guid(self._location.sector_guid)
        bw.write_guid(self._location.zone_guid)

    def process(self, bw) -> None:
        self.to_wire(bw)


class InCic(InRoom):
    def __init__(self, location, trans_scene_type=None):
        if trans_scene_type is None:
            trans_scene_type = SceneChange.CIC
        super().__init__(location, trans_scene_type)

    def room_guid(self) -> int:
        frakcio = self._location.faction
        return (WellKnownCard.CiCColonial.value if frakcio == Faction.Colonial
                else WellKnownCard.CiCCylon.value)


class AtOutpost(InRoom):
    def __init__(self, location, trans_scene_type=None):
        if trans_scene_type is None:
            trans_scene_type = SceneChange.Outpost
        super().__init__(location, trans_scene_type)

    def room_guid(self) -> int:
        frakcio = self._location.faction
        return (WellKnownCard.RoomOutpostColonial.value if frakcio == Faction.Colonial
                else WellKnownCard.RoomOutpostCylon.value)


class Place(InfoBroadcast):
    def __init__(self, player_id: int, faction):
        self._sector_id = 0
        self._faction = faction
        self._previous_location = None
        self._sector_guid = 0
        self._zone_guid = 0
        super().__init__(InfoKind.Place, player_id, None)
        self.switch_state(AtStarter(self))

    @property
    def faction(self):
        return self._faction.get()

    @property
    def sector_id(self) -> int:
        return self._sector_id

    @property
    def sector_guid(self) -> int:
        return self._sector_guid

    @property
    def zone_guid(self) -> int:
        return self._zone_guid

    @property
    def previous_location(self):
        return self._previous_location

    def place_in_sector(self, sector_id: int, star_guid: int, zone_guid: int) -> None:
        self._sector_id = sector_id
        self._sector_guid = star_guid
        self._zone_guid = zone_guid

    def to_wire(self, bw) -> None:
        self.current_info.process(bw)

    def switch_state(self, hely_allapot) -> None:
        self.set(hely_allapot)

    def set(self, uj_adat) -> None:
        if self.current_info is not None:
            self._set_previous_location(self.current_info.game_location)
        super().set(uj_adat)

    @property
    def game_location(self):
        return self.current_info.game_location

    def non_disconnect_location(self):
        mostani = self.game_location
        if mostani == PlaceKind.Disconnect:
            return self._previous_location
        return mostani

    _NON_RESTORABLE_LOCATIONS = (PlaceKind.Disconnect, PlaceKind.Arena,
                                 PlaceKind.BattleSpace, PlaceKind.Tournament)

    def _set_previous_location(self, game_location) -> None:
        if game_location not in Place._NON_RESTORABLE_LOCATIONS:
            self._previous_location = game_location

    def set_location(self, game_location, sector_id: int, star_guid: int, zone_guid: int = 0) -> None:
        self.place_in_sector(sector_id, star_guid, zone_guid)
        if game_location == PlaceKind.Room:
            if world_places().is_home_station(sector_id):
                self.switch_state(InCic(self))
            else:
                self.switch_state(AtOutpost(self))
        elif game_location == PlaceKind.Space:
            self.switch_state(InSpace(self))
        elif game_location == PlaceKind.Starter:
            self.switch_state(AtStarter(self))
        elif game_location == PlaceKind.Avatar:
            self.switch_state(AtAvatar(self))
        elif game_location == PlaceKind.Zone:
            self.switch_state(AreaPlace(self))
        else:
            raise ValueError(f'PlaceKind {game_location} has no implementation')

    def set_arena_location(self, sector_id: int, star_guid: int, faction_group_flag: int) -> None:
        self.place_in_sector(sector_id, star_guid, 0)
        self.switch_state(ArenaLocation(self, faction_group_flag))

    def room_guid(self) -> int:
        if isinstance(self.current_info, InRoom):
            return self.current_info.room_guid()
        return 0

    def note_guild_place(self, bw) -> None:
        self.current_info.notify_place_watcher(bw)

    def in_space_together(self, location: "Place") -> bool:
        is_space = location.game_location == PlaceKind.Space
        if not is_space:
            return False
        return self._sector_id == location.sector_id

    @property
    def is_in_room(self) -> bool:
        return self.game_location == PlaceKind.Room
