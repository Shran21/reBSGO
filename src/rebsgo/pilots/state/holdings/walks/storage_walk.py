# github.com/Shran21
from __future__ import annotations

import logging
import math

from rebsgo.gamedata.from_json.upgrade_rules_reader import upgrade_rules

from rebsgo.pilots.state.holdings.storages import StorageKind
from rebsgo.pilots.state.default_model_paint_updates import normalize_default_model_paints
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.protocol_book_replies import replies_for
from rebsgo.vocabulary.world import PlaceKind
from rebsgo.vocabulary.pilot import ResourceKind
from rebsgo.geometry.maths.maths import Maths
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.ship_parts.parts import (
    CountableItem,
    ItemType,
    one_item_of_guid,
    ShipSystem,
)
from rebsgo.gamedata.reading import AugmentActionKind, Price
from rebsgo.helpers.dice import Dice
from rebsgo.helpers.floats import fdiv
from rebsgo.helpers.log_tags import tag

log = logging.getLogger(__name__)


class RaktarGond(Exception):
    pass


class NincsIlyenTetel(RaktarGond):
    def __init__(self, item_id=None):
        reszlet = '' if item_id is None else f' ({item_id})'
        super().__init__('nincs ilyen tárgy-azonosító' + reszlet)
        self.item_id = item_id


class NemEladhato(RaktarGond):
    def __init__(self):
        super().__init__('a tárgy nem eladható')


def vezet_ide(*tarolok):
    def jelol(lepes):
        lepes._tarolok = tarolok
        return lepes
    return jelol


def deliver_item(user, ship_item, hova_tarolo) -> None:
    if ship_item is None or isinstance(ship_item, CountableItem) and ship_item.count() == 0:
        return
    erintett = hova_tarolo.add_ship_item(ship_item)
    player_protocol = user.protocol_of(ProtocolID.Pilot)
    user.send(player_protocol.push_item_added(hova_tarolo, erintett))


class StorageWalk:
    def __init__(self, user, transfer_request=None, dice=None):
        if isinstance(transfer_request, Dice) and dice is None:
            dice = transfer_request
            transfer_request = None
        from rebsgo.services import Services
        from rebsgo.gamedata.library import Catalogue
        self.catalogue = Services.get(Catalogue)
        self.user = user
        self.transfer_request = transfer_request
        self.player_protocol = user.protocol_of(ProtocolID.Pilot)
        self.debug_protocol = user.protocol_of(ProtocolID.Debug)
        self.dice = dice if dice is not None else Dice()
        tag("userID", str(user.pilot_of().user_id_of()))


    LEPESEK: dict = {}

    def __init_subclass__(cls, **kw) -> None:
        super().__init_subclass__(**kw)
        lepesek = dict(getattr(cls, "LEPESEK", {}))
        for lepes in vars(cls).values():
            for fajta in getattr(lepes, "_tarolok", ()):
                lepesek[fajta] = lepes
        cls.LEPESEK = lepesek

    def _nem_ide(self) -> None:
        self.debug_protocol.tell_console('there is no step from here to that container')

    def step_into(self, container) -> None:
        for fajta, lepes in self.LEPESEK.items():
            if isinstance(container, fajta):
                lepes(self, container)
                return
        self.debug_protocol.tell_console('there is no step from here to that container')


    def take_item(self, ship_item, honnan_tarolo) -> None:
        honnan_tarolo.take_item(ship_item.server_id)
        self.user.send(self.player_protocol.push_item_removed(honnan_tarolo, ship_item.server_id))

    def add_ship_item(self, ship_item, hova_tarolo) -> None:
        deliver_item(self.user, ship_item, hova_tarolo)

    def shift_item(self, ship_item, from_, hova_tarolo) -> None:
        self.take_item(ship_item, from_)
        self.add_ship_item(ship_item, hova_tarolo)

    def hold_into_slot(self, honnan_tarolo, cel_rekesz) -> None:
        rendszer = self._beepitheto(honnan_tarolo, cel_rekesz)
        if rendszer is None:
            return

        if cel_rekesz.ship_system.ship_system_card is not None:
            self.unslot_the_item(cel_rekesz, honnan_tarolo, refill_default_paint=False)

        log.info('%s mounting a system: source=%s slot=%s', self.user.user_log_simple,
                 honnan_tarolo.container_id.container_type, cel_rekesz.container_id)
        self.slot_the_item(rendszer, cel_rekesz, honnan_tarolo)

    def _beepitheto(self, honnan_tarolo, cel_rekesz):
        darab = self._kezben_van_a_rendszer(honnan_tarolo)
        if darab is None:
            return None
        return darab if self._hajotest_elfogadja(darab, honnan_tarolo, cel_rekesz) else None

    def _kezben_van_a_rendszer(self, honnan_tarolo):
        jatekos = self.user.pilot_of()
        if jatekos.location.game_location != PlaceKind.Room:
            log.error('%s tried mounting gear away from a station', self.user.user_log())
            return None
        darab = honnan_tarolo.by_id(self.transfer_request.item_id)
        if darab is None:
            log.warning('%s tried mounting an item id that resolves to nothing: %s',
                        jatekos.player_log, self.transfer_request.item_id)
            return None
        if isinstance(darab, ShipSystem):
            return darab
        log.warning('%s pushed a non-system into a slot, namely %s',
                    self.user.user_log(), darab.item_type)
        self.debug_protocol.tell_console('slot placement failed (L1) - please report it')
        return None

    def _hajotest_elfogadja(self, darab, honnan_tarolo, cel_rekesz) -> bool:
        aktiv = self.user.pilot_of().hangar_of().active_ship()
        if aktiv.server_id != cel_rekesz.container_id.ship_id:
            log.warning('%s fitted gear onto a ship that is not their active one (%s -> %s)', self.user.user_log(),
                        honnan_tarolo.container_id, cel_rekesz.container_id)
            return False
        if darab.ship_system_card.object_key_barred(aktiv.ship_card_of().ship_object_key):
            log.warning('%s mounted a system this hull rejects: %s / %s',
                        self.user.user_log(), darab.ship_system_card, aktiv.ship_card_of())
            return False
        return True

    def slot_the_item(self, mozgatando, ship_slot, honnan_tarolo=None):
        if honnan_tarolo is not None:
            self.take_item(mozgatando, honnan_tarolo)
        hangar_ship = self.user.pilot_of().hangar_of().by_server_id(ship_slot.container_id.ship_id)
        ship_slot.add_ship_item(mozgatando)
        from rebsgo.world.capitals.capital_roster import CAPITAL_SLOT
        if hangar_ship.server_id == CAPITAL_SLOT:
            self.player_protocol.load_capital_ammo_into_slot(ship_slot)
        self._normalize_default_model_paints(hangar_ship)
        self.user.send(self.player_protocol.replies.ship_slots(hangar_ship))
        hangar_ship.ship_stats().fold_in_stats()

    def relocate_into_slot(self, mozgatando, other, ship_slot, kilovo_fajta) -> None:
        current_slot_system = ship_slot.ship_system
        if current_slot_system.ship_system_card is not None:
            self.unslot_the_item(ship_slot, other, refill_default_paint=False)
        if kilovo_fajta == StorageKind.Shop:
            self.slot_the_item(mozgatando, ship_slot)
        else:
            self.slot_the_item(mozgatando, ship_slot, other)

    def unslot_the_item(self, ship_slot, hova_tarolo=None, refill_default_paint=True):
        active_ship = self.user.pilot_of().hangar_of().active_ship()
        if active_ship.server_id != ship_slot.container_id.ship_id:
            self.debug_protocol.tell_console(
                'a slot was emptied on a ship nobody is flying - please report it')
            return None

        ship_system = ship_slot.ship_system
        removed_item = ship_slot.take_item(ship_system.server_id)
        if hova_tarolo is not None:
            self.add_ship_item(ship_system, hova_tarolo)
        if refill_default_paint:
            self._normalize_default_model_paints(active_ship)
        self.user.send(self.player_protocol.replies.ship_slots(active_ship))
        return removed_item

    def _normalize_default_model_paints(self, hangar_ship) -> None:
        updates = normalize_default_model_paints(self.user.pilot_of(), hangar_ship)
        for tarolo, server_id in updates.removed_from_locker:
            self.user.send(self.player_protocol.push_item_removed(tarolo, server_id))
        for tarolo, ship_item in updates.added_to_locker:
            self.user.send(self.player_protocol.push_item_added(tarolo, ship_item))


    @staticmethod
    def enough_held(price, container, buy_count) -> bool:
        for guid, ertek in price.items().items():
            price_count = int(math.ceil(ertek * buy_count))
            countable = container.holds_stack_of(guid)
            if countable is not None:
                ex_countable = countable
                if ex_countable.count() < price_count:
                    return False
            else:
                return price_count == 0
        return True

    def spend_resource(self, resource, count) -> bool:
        guid = resource.guid if isinstance(resource, ResourceKind) else resource
        hold = self.user.pilot_of().hold
        tetel = hold.by_guid(guid)
        if tetel is None:
            return False
        try:
            self.take_from_stack(tetel, count, hold)
        except ValueError:
            log.info('%s came up short of %s x%s', self.user.user_log_simple, guid, count)
            return False
        log.info('%s spent %s x%s', self.user.user_log_simple, guid, count)
        return True

    def take_from_stack(self, current_item_consumable, count, honnan_tarolo) -> None:
        if current_item_consumable.count() < count:
            raise ValueError("The CountableItem is less than the count to be decreased!")
        new_count = current_item_consumable.count() - count
        current_item_consumable.update_count(new_count)
        if new_count > 0:
            self.user.send(self.player_protocol.push_item_added(honnan_tarolo, current_item_consumable))
        else:
            self.take_item(current_item_consumable, honnan_tarolo)

    def take_payment(self, price, fizeto_tarolo, buy_count) -> None:
        log.info('%s pays %s out of %s, pieces=%s', self.user.user_log_simple,
                 StorageWalk._ar_szovege(price), fizeto_tarolo.container_id.container_type,
                 buy_count)
        for guid, ertek in price.items().items():
            tetel = fizeto_tarolo.by_guid(guid)
            if tetel is None:
                continue
            if isinstance(tetel, CountableItem):
                ex_countable = tetel
                sum_count = int(math.ceil(ertek * buy_count))
                self.take_from_stack(ex_countable, sum_count, fizeto_tarolo)


    def upgrade_system(self, forras_tarolo, hold, fejlesztendo, new_level) -> bool:
        lanc = self._fejlesztesi_lanc(fejlesztendo.ship_system_card, new_level)
        if lanc is None:
            return False
        vegso_kartya, teljes_ar = lanc

        if not StorageWalk.enough_held(teljes_ar, hold, 1):
            log.info('%s cannot afford system %s up to level %s (%s)', self.user.user_log_simple,
                     fejlesztendo.card_guid_of(), new_level, StorageWalk._ar_szovege(teljes_ar))
            return False
        self.take_payment(teljes_ar, hold, 1)
        sikerult = self._fejlesztettre_cserel(forras_tarolo, fejlesztendo, vegso_kartya)
        log.info('%s upgraded system %s to level %s -> %s', self.user.user_log_simple,
                 fejlesztendo.card_guid_of(), new_level,
                 'in place' if sikerult else 'PAID BUT NOT SWAPPED')
        return sikerult

    def _fejlesztesi_lanc(self, kartya, kert_szint):
        teljes_ar = Price()
        while kartya is not None and kartya.level < kert_szint:
            ar_kartya = self.catalogue.card_of(kartya.card_guid_of(), CardView.Price)
            lepes_ara = ar_kartya.upgrade_price if ar_kartya is not None else None
            if lepes_ara is None:
                return None
            teljes_ar.take_price(lepes_ara)
            kartya = self.catalogue.card_of(kartya.next_card_guid, CardView.ShipSystem)
        return None if kartya is None else (kartya, teljes_ar)

    def _fejlesztettre_cserel(self, honnan, regi_rendszer, uj_kartya) -> bool:
        fejlesztett = ShipSystem.from_guid(uj_kartya.card_guid_of())
        if honnan.container_id.container_type == StorageKind.ShipSlot:
            if self.unslot_the_item(honnan) is None:
                return False
            self.slot_the_item(fejlesztett, honnan)
            return True

        self.take_item(regi_rendszer, honnan)
        fejlesztett.note_use(regi_rendszer.time_of_last_use_local_date_time)
        self.add_ship_item(fejlesztett, honnan)
        return True

    def upgrade_with_pack(self, forras_tarolo, hold, fejlesztendo, pack_count) -> bool:
        esely = self._csomag_eselye(fejlesztendo, pack_count)
        if esely is None:
            return False

        if not self._keszletek_levonasa(hold, pack_count):
            return False

        sikerult = self.dice.passes(esely)
        log.info('%s spent %s tuning kits on system %s at odds %.2f -> %s',
                 self.user.user_log_simple, pack_count, fejlesztendo.card_guid_of(),
                 esely, 'upgraded' if sikerult else 'no luck')
        ertesito = replies_for(ProtocolID.Notification)
        self.user.send(ertesito.system_upgrade_result(sikerult))
        if not sikerult:
            return False

        return self._fejlesztettre_csere(forras_tarolo, fejlesztendo)

    def _csomag_eselye(self, fejlesztendo, pack_count):
        arkartya = self.catalogue.card_of(fejlesztendo.card_guid_of(), CardView.Price)
        if arkartya is None:
            return None
        kockaban = arkartya.upgrade_price.items().get(ResourceKind.Cubits.guid)
        keszlet_ara = fdiv(kockaban, upgrade_rules().cubits_per_tuning_kit())
        return Maths.min(1.0, fdiv(pack_count, keszlet_ara))

    def _keszletek_levonasa(self, hold, pack_count) -> bool:
        keszletek = hold.by_guid(ResourceKind.TuningKit.guid)
        if keszletek is None or keszletek.item_type != ItemType.Countable:
            return False

        ar = Price()
        ar.add_item(keszletek.card_guid_of(), pack_count)
        if not StorageWalk.enough_held(ar, hold, 1):
            return False
        self.take_payment(ar, hold, 1)
        return True

    def _fejlesztettre_csere(self, forras_tarolo, fejlesztendo) -> bool:
        fejlesztett = ShipSystem.from_guid(fejlesztendo.ship_system_card.next_card_guid)
        fejlesztett.server_id = fejlesztendo.server_id
        fejlesztett.note_use(fejlesztendo.time_of_last_use_local_date_time)

        if forras_tarolo.container_id.container_type != StorageKind.ShipSlot:
            self.take_item(fejlesztendo, forras_tarolo)
            self.add_ship_item(fejlesztett, forras_tarolo)
            return True

        if self.unslot_the_item(forras_tarolo) is None:
            return False
        self.slot_the_item(fejlesztett, forras_tarolo)
        return True

    def sell_item(self, from_, proceeds_container, item_id, count) -> None:
        item_to_sell = from_.by_id(item_id)
        if item_to_sell is None:
            raise NincsIlyenTetel(item_id)

        ar_kartya = self.catalogue.card_of(item_to_sell.card_guid_of(), CardView.Price)
        if ar_kartya is None:
            log.warning('sale item %s carries no price card', item_to_sell.card_guid_of())
            return
        if not ar_kartya.sellable:
            log.warning('%s attempted to sell the unsellable', self.user.user_log())
            raise NemEladhato()

        ar = ar_kartya.sell_price
        log.info('%s selling guid=%s out of %s for %s, pieces=%s',
                 self.user.user_log_simple, item_to_sell.card_guid_of(),
                 from_.container_id.container_type, ar, count)

        if not self._eladott_kivetele(item_to_sell, count, from_):
            return
        for jussa in StorageWalk.sell_items(ar, count):
            self.add_ship_item(jussa, proceeds_container)

    def _eladott_kivetele(self, item_to_sell, count, from_) -> bool:
        if not isinstance(item_to_sell, CountableItem):
            if from_.container_id.container_type == StorageKind.ShipSlot:
                self.unslot_the_item(from_)
            else:
                self.take_item(item_to_sell, from_)
            return True
        try:
            self.take_from_stack(item_to_sell, count, from_)
        except ValueError:
            log.warning('sale exceeds the stack: %s, pieces=%s', item_to_sell, count)
            return False
        return True

    def shift_stack(self, item_countable, from_, hova_tarolo) -> None:
        kert = self.transfer_request.count()
        keszlet = item_countable.count()
        if kert > keszlet:
            log.error('%s asked to move %s out of a stack holding %s',
                      self.user.user_log(), kert, keszlet)
            return
        if kert == keszlet:
            self.shift_item(item_countable, from_, hova_tarolo)
            return

        item_countable.shrink_count(kert)
        self._keszlet_hirdetese(from_, item_countable)
        self._keszlet_hirdetese(hova_tarolo, hova_tarolo.add_ship_item(
            CountableItem.from_guid(item_countable.card_guid_of(), kert)))

    def _keszlet_hirdetese(self, tarolo, keszlet) -> None:
        self.user.send(self.player_protocol.push_item_added(tarolo, keszlet))

    @staticmethod
    def _ar_szovege(price) -> str:
        return ", ".join(f"{guid}:{ertek:g}" for guid, ertek in price.items().items()) or "nothing"

    @staticmethod
    def sell_items(sell_prices, count):
        sell_items = []
        for price_guid, ertek in sell_prices.items().items():
            try:
                sell_item = one_item_of_guid(price_guid)
                if isinstance(sell_item, CountableItem):
                    sell_item.update_count(int(ertek * count))
                    sell_items.append(sell_item)
            except ValueError:
                log.exception("a sell price would not turn into an item")
        return sell_items


    def use_augment(self) -> bool:
        honnan = self.transfer_request.source_container
        darab = honnan.by_id(self.transfer_request.item_id)
        if not isinstance(darab, CountableItem) or darab.item_type != ItemType.Countable:
            return False

        kartya = self.catalogue.card_of(darab.card_guid_of(), CardView.ShipConsumable)
        if kartya is None or kartya.augment_action_type != AugmentActionKind.None_:
            return False

        self.take_from_stack(darab, 1, honnan)
        return True

    def consume_for_bulk_augment(self, iterations) -> bool:
        honnan = self.transfer_request.source_container
        elemzendo = self._elemezheto_targy(honnan, iterations)
        if elemzendo is None:
            return False

        hold = self.user.pilot_of().hold
        keszletek = hold.holds_stack_of(ResourceKind.TechnicalAnalysisKit.guid)
        if keszletek is None or iterations > keszletek.count():
            return False

        self.take_from_stack(elemzendo, iterations, honnan)
        self.take_from_stack(keszletek, iterations, hold)
        return True

    def _elemezheto_targy(self, honnan, iterations):
        targy = honnan.by_id(self.transfer_request.item_id)
        if targy is None or targy.item_type != ItemType.Countable or iterations > targy.count():
            return None
        kartya = self.catalogue.card_of(targy.card_guid_of(), CardView.ShipConsumable)
        if kartya is None or kartya.augment_action_type != AugmentActionKind.LootItem:
            return None
        return targy

    def purchase_price(self, vasarolando, fizeto_tarolo, buy_count):
        if vasarolando is None:
            raise NincsIlyenTetel(self.transfer_request.item_id)

        arcedula = self.catalogue.card_of(vasarolando.card_guid_of(), CardView.Price)
        if arcedula is None:
            self.user.protocol_of(ProtocolID.Debug).tell_console(
                'this item lacks a price card - please report it')
            return None
        if not StorageWalk.enough_held(arcedula.buy_price, fizeto_tarolo, buy_count):
            return None
        fizetendo = Price()
        fizetendo.take_price(arcedula.buy_price)
        return fizetendo
