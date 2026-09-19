# github.com/Shran21
from __future__ import annotations

import datetime
import logging

from rebsgo.wire.bytes.stamp import Stamp
from rebsgo.services import Services
from rebsgo.pilots.state.permissions import AdminPowers, ResourceLimit
from rebsgo.pilots.state.pilot_parts import AvatarLook, MedalProgress, PilotAvatar, PilotFaction, PilotClan, PilotMedals, PilotName
from rebsgo.pilots.state.holdings.storages import BlackHole, EventShop, Hold, Locker, MailBox, Shop
from rebsgo.pilots.state.tallies import TallyDesk, Tallies
from rebsgo.pilots.state.boosts.boosts import Boosts
from rebsgo.pilots.state.pilot_bits import Friends
from rebsgo.pilots.state.berths import Hangar
from rebsgo.pilots.state.berthed_ship import HangarShip
from rebsgo.pilots.state.whereabouts import Place
from rebsgo.pilots.state.options.preferences import Settings
from rebsgo.pilots.state.training.skill_sheet import SkillSheet
from rebsgo.pilots.state.pilot_bits import AreaPasses
from rebsgo.vocabulary.pilot import ServerRoles, Faction, ResourceKind
from rebsgo.vocabulary.world import WellKnownCard
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.library import Catalogue
from rebsgo.helpers.locks import ReentrantLock
from rebsgo.helpers.log_tags import tag

log = logging.getLogger(__name__)

class Pilot:
    def __init__(self, user_id: int, server_config, mission_book):
        if user_id < 0:
            raise ValueError('pilot id below zero is invalid')
        self._catalogue: Catalogue = Services.get(Catalogue)
        self._user_id = user_id
        tag("userID", str(user_id))
        log.info("init user...%s", user_id)

        self._name = PilotName(self._user_id, "")
        self._faction = PilotFaction(self._user_id, Faction.Neutral)

        self._settings = Settings(user_id)

        self._hold = Hold(user_id)
        self._locker = Locker(user_id)
        self._shop = Shop(user_id)
        self._event_shop = EventShop(user_id)
        self._black_hole = BlackHole()
        self._zones_admissions = AreaPasses()

        self._merits_cap_farmed = ResourceLimit(ResourceKind.Token.guid,
                                              server_config.starter_params.daily_token_cap)

        self._hangar = Hangar(user_id)
        self._bgo_admin_roles = AdminPowers(ServerRoles.None_.value)
        self._factors = Boosts(user_id)
        self._player_avatar = PilotAvatar(self._user_id, AvatarLook())
        self._mail_box = MailBox()
        self._counters = Tallies.create(user_id)
        self._player_guild = PilotClan(self._user_id, None)
        self._player_medals = PilotMedals(self._user_id, MedalProgress())
        self._location = Place(self._user_id, self._faction)

        self._skill_book = SkillSheet(player_id=self._user_id)
        self._mission_book = mission_book
        self._friends = Friends()
        self._tally_desk = TallyDesk(self._counters, self._mission_book)

        self._party = None
        self._party_lock = ReentrantLock()
        self._last_logout = None
        self._last_free_wof_game = None
        self._daily_streak_day = 0
        self._daily_streak_date = ""
        self._daily_offer_guid = None
        self._last_remote_address = None
        self._jump_arrival_transform = None

        self._location.set_location(self._location.game_location, -1, 0)
        log.info('player bootstrap complete')


    def user_id_of(self) -> int:
        return self._user_id

    @property
    def name(self) -> str:
        return self._name.get()

    @name.setter
    def name(self, name: str) -> None:
        log.info("user %s set_name [%s]", self._user_id, name)
        self._name.set(name)

    @property
    def faction(self) -> Faction:
        return self._faction.get()

    @faction.setter
    def faction(self, faction: Faction) -> None:
        if faction is None:
            raise TypeError('a faction is required here')
        if not (faction == Faction.Colonial or faction == Faction.Cylon):
            raise ValueError(f'only the two playable factions are accepted {faction}')
        self._faction.set(faction)
        if self._location.sector_id == -1:
            map_card = self._catalogue.card_or_none(WellKnownCard.GalaxyMap, CardView.GalaxyMap)
            map_star_desc = map_card.starter_sector_for_faction(faction)
            self._location.set_location(self._location.game_location, map_star_desc.id,
                                        map_star_desc.sector_guid)

    @property
    def avatar_description(self) -> PilotAvatar:
        return self._player_avatar

    @property
    def player_log(self) -> str:
        return str(self._user_id) + " " + str(self._name)

    @property
    def bgo_admin_roles(self) -> AdminPowers:
        return self._bgo_admin_roles

    @property
    def player_medals(self) -> PilotMedals:
        return self._player_medals


    @property
    def location(self) -> Place:
        return self._location

    @property
    def sector_id(self) -> int:
        return self._location.sector_id

    def arrive_at(self, transform) -> None:
        self._jump_arrival_transform = None if transform is None else transform.copy()

    def consume_jump_arrival_transform(self):
        transform = self._jump_arrival_transform
        self._jump_arrival_transform = None
        return None if transform is None else transform.copy()


    def hangar_of(self) -> Hangar:
        return self._hangar

    def seed_hangar(self) -> None:
        guid = (WellKnownCard.ColonialStarterShip.value if self._faction.get() == Faction.Colonial
                else WellKnownCard.CylonStarterShip.value)
        hangar_ship = HangarShip(self._user_id, 1, guid, "")
        hangar_ship.ship_stats().fold_in_stats()
        hangar_ship.ship_stats().fill_hull()
        self._hangar.berth(hangar_ship)

    @property
    def hold(self) -> Hold:
        return self._hold

    @property
    def locker(self) -> Locker:
        return self._locker

    @property
    def shop(self) -> Shop:
        return self._shop

    @property
    def event_shop(self) -> EventShop:
        return self._event_shop

    @property
    def black_hole(self) -> BlackHole:
        return self._black_hole

    @property
    def mail_box(self) -> MailBox:
        return self._mail_box


    @property
    def skill_book(self) -> SkillSheet:
        return self._skill_book

    @property
    def factors(self) -> Boosts:
        return self._factors

    @property
    def tally_desk(self) -> TallyDesk:
        return self._tally_desk

    @property
    def merits_cap_farmed(self) -> ResourceLimit:
        return self._merits_cap_farmed

    @property
    def last_free_wof_game(self):
        return self._last_free_wof_game

    @last_free_wof_game.setter
    def last_free_wof_game(self, idopont) -> None:
        self._last_free_wof_game = Stamp(idopont)

    @property
    def daily_streak_day(self) -> int:
        return self._daily_streak_day

    @daily_streak_day.setter
    def daily_streak_day(self, nap: int) -> None:
        self._daily_streak_day = int(nap)

    @property
    def daily_streak_date(self) -> str:
        return self._daily_streak_date

    @daily_streak_date.setter
    def daily_streak_date(self, datum: str) -> None:
        self._daily_streak_date = str(datum or "")

    @property
    def daily_offer_guid(self):
        return self._daily_offer_guid

    @daily_offer_guid.setter
    def daily_offer_guid(self, guid) -> None:
        self._daily_offer_guid = guid


    def party(self):
        with self._party_lock:
            return self._party

    def join_party(self, party) -> None:
        with self._party_lock:
            self._party = party

    def guild(self):
        return self._player_guild.get()

    def join_guild(self, guild) -> None:
        self._player_guild.set(guild)

    @property
    def player_guild(self) -> PilotClan:
        return self._player_guild

    @property
    def friends(self) -> Friends:
        return self._friends


    @property
    def settings(self) -> Settings:
        return self._settings


    @property
    def last_logout(self):
        return self._last_logout

    def note_logout(self, last_logout=None) -> None:
        if last_logout is None:
            self.note_logout(Stamp(datetime.datetime.now(datetime.timezone.utc)))
            return
        if last_logout is None:
            raise TypeError('a last-logout timestamp is required')
        if self._last_logout is None:
            self._last_logout = last_logout
        else:
            self._last_logout.set(last_logout.local_date)

    def note_remote_address(self, vonal_cime, vonalbontasbol: bool) -> None:
        if not vonalbontasbol and vonal_cime is None:
            self._last_remote_address = vonal_cime
        if vonal_cime is not None:
            self._last_remote_address = vonal_cime

    @property
    def last_remote_address(self):
        return self._last_remote_address


    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self._user_id == other._user_id

    def __hash__(self) -> int:
        return hash(self._user_id)
