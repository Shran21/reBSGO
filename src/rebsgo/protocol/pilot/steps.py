# github.com/Shran21

from __future__ import annotations

from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.cards.world_cards import GalaxyMapCard
from rebsgo.pilots.state.berthed_ship import HangarShip
from rebsgo.pilots.state.holdings.storages import Mail
from rebsgo.protocol.message_route import MessageRoute
from rebsgo.protocol.pilot.pilot_steps import ShipCardSwap
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.vocabulary.pilot import Faction, ResourceKind
from rebsgo.vocabulary.world import PlaceKind, WellKnownCard
from rebsgo.world.scanning.dradis_change import DradisChange
import logging
import time


log = logging.getLogger(__name__)


class DradisReply(MessageRoute):
    def __init__(self, user, dradis_data):
        self._user = user
        self._dradis_data = dradis_data

    def handle(self, br) -> None:
        detection_visual_radius = br.read_single()
        detection_inner_radius = br.read_single()
        detection_outer_radius = br.read_single()

        dradis_update = DradisChange(int(time.time() * 1000),
                                     detection_visual_radius, detection_inner_radius, detection_outer_radius)
        is_delay_okay = self._dradis_data.update_dradis(dradis_update)
        is_cheat = dradis_update.detection_outer_radius >= 10_000
        if is_cheat:
            log.warning("%s_dradis-Cheat! UserID:  %s current_ship %s",
                        self._user.user_log(), dradis_update,
                        self._user.pilot_of().hangar_of().active_ship().ship_card_of().card_guid_of())


class FactionSwitch(MessageRoute):
    def __init__(self, user, character_services, catalogue, dice):
        self._user = user
        self._character_services = character_services
        self._catalogue = catalogue
        self._dice = dice

    def handle(self, reader) -> None:
        self.switch_sides(True, -1)

    def switch_sides(self, arral: bool, cubits_price: float) -> None:
        log.info('%s is switching sides', self._user.user_log())
        if arral and not self._ar_levonasa(cubits_price):
            return
        if self._user.pilot_of().location.game_location != PlaceKind.Room:
            log.warning('%s side switch denied - not stationside', self._user.user_log())
            return

        self._hajok_atalakitasa()
        csillag = self._uj_bazis_csillaga()
        if csillag is None:
            log.error('side switch: the destination home star is unresolvable')
            return

        self._kotelekek_bontasa()
        self._masik_oldalra(csillag)
        log.info('%s finished switching sides', self._user.user_log())

    def _ar_levonasa(self, cubits_price: float) -> bool:
        from rebsgo.pilots.state.holdings.walks.hold_walk import HoldWalk

        ar = (int(self._character_services.cubits_price_faction)
              if cubits_price == -1 else int(cubits_price))
        raktar = HoldWalk(self._user, self._dice)
        if raktar.spend_resource(ResourceKind.Cubits, ar):
            return True
        log.warning('%s wants to switch sides but cannot pay for it', self._user.user_log())
        return False

    def _hajok_atalakitasa(self) -> None:
        from rebsgo.pilots.state.holdings.walks.slot_walk import SlotWalk

        hangar = self._user.pilot_of().hangar_of()
        rekesz_kezelo = SlotWalk(self._user, None)
        for hangar_ship in hangar.all_hangar_ships():
            for rekesz in hangar_ship.ship_slots.values():
                kivett = rekesz.take_item()
                if kivett is None or kivett.card_guid_of() == 0:
                    continue
                rekesz_kezelo.add_ship_item(kivett, self._user.pilot_of().locker)

        regi_kartyak = [hs.ship_card_of() for hs in hangar.all_hangar_ships()]
        parjuk = ShipCardSwap(self._user.pilot_of().faction).convert_cards(regi_kartyak)
        hangar.wipe_hangar()
        for kartya in parjuk:
            hangar.berth(HangarShip(
                self._user.pilot_of().user_id_of(),
                kartya.hangar_id, kartya.card_guid_of(), ""))
        hangar.choose_active_ship(1)

    def _uj_bazis_csillaga(self):
        masik = Faction.negated(self._user.pilot_of().faction)
        galaxis = self._catalogue.card_or_none(WellKnownCard.GalaxyMap, CardView.GalaxyMap)
        return galaxis.star(GalaxyMapCard.start_sector(masik))

    def _kotelekek_bontasa(self) -> None:
        jatekos = self._user.pilot_of()
        if (klan := jatekos.guild()) is not None:
            klan.remove_player(jatekos.user_id_of())
            jatekos.join_guild(None)
            kozosseg = self._user.protocol_of(ProtocolID.Community)
            kozosseg.guild_processing.tell_guild(
                klan, kozosseg.replies.guild_remove(jatekos.user_id_of(), True))

        if (raj := jatekos.party()) is not None:
            kozosseg = self._user.protocol_of(ProtocolID.Community)
            kozosseg.party_processing.eject_from_party(self._user, raj)
        if jatekos.party() is not None:
            log.error('still party-bound after the side switch: %s', self._user.user_log())

    def _masik_oldalra(self, csillag) -> None:
        jatekos = self._user.pilot_of()
        jatekos.tally_desk.mission_book.clear_keeping_moment()
        jatekos.faction = Faction.negated(jatekos.faction)
        jatekos.location.set_location(PlaceKind.Room, csillag.id, csillag.sector_guid)
        log.info('%s relocated to %s (%s)', self._user.user_log(), csillag.id, csillag.sector_guid)

        scene_protocol = self._user.protocol_of(ProtocolID.Scene)
        self._user.send(scene_protocol.push_disconnect())


class MailReading(MessageRoute):
    def __init__(self, user, writer):
        self._user = user
        self._writer = writer

    def handle(self, br) -> None:
        log.info("MailReading")
        mail_id = br.read_uint16()
        player = self._user.pilot_of()
        mail_box = player.mail_box
        mail = mail_box.by_id(mail_id)
        if mail is None:
            return
        mail.mail_status = Mail.MailState.Normal
        self._user.send(self._writer.mail_box(mail_box))
