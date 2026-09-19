# github.com/Shran21
from __future__ import annotations

from rebsgo.protocol.messages import PilotReply

from contextlib import suppress

import datetime as _dt
import logging
from enum import Enum

from rebsgo.world.carriers.carrier_mode import get_carrier_mode_config, is_carrier_space_object
from rebsgo.world.scanning.dradis_contacts import DradisContacts
from rebsgo.pilots.state.pilot_parts import AvatarLook
from rebsgo.pilots.state.permissions import Capability
from rebsgo.pilots.state.holdings.storages import StorageKind, MailName, Hold
from rebsgo.pilots.state.berthed_ship import HangarShip
from rebsgo.pilots.state.whereabouts import AtAvatar, InCic
from rebsgo.protocol.wire_base import BgoProtocol
from rebsgo.protocol.pilot.orders import WearCost
from rebsgo.protocol.pilot.steps import FactionSwitch, MailReading, DradisReply
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.protocol_book_replies import replies_for
from rebsgo.pilots.together.clan import ClanInfoReply
from rebsgo.pilots.state.boosts.boost import Boost
from rebsgo.vocabulary.pilot import ServerRoles, BoostSource, BoostKind, Faction, ResourceKind
from rebsgo.vocabulary.world import PlaceKind
from rebsgo.gamedata.from_json.template_readers import capital_rules
from rebsgo.gamedata.upgrades import AugmentBoostSpec, AugmentExperienceSpec, AugmentLootSpec, augment_template_for
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.cards.misc_cards import TallyCardKind
from rebsgo.gamedata.ship_parts.parts import CountableItem, ItemType
from rebsgo.gamedata.reading import ObjectStat
from rebsgo.pilots.state.tallies import Assignment
from rebsgo.world.objects.attachments import StickerMount
from rebsgo.gamedata.from_json.template_readers import world_timers


log = logging.getLogger(__name__)

_UTC = _dt.timezone.utc

_SHIP_LOADOUTS = None


def _get_ship_loadouts():
    global _SHIP_LOADOUTS
    if _SHIP_LOADOUTS is None:
        from rebsgo.gamedata.from_json.small_readers import ShipLoadoutTemplateReader
        _SHIP_LOADOUTS = ShipLoadoutTemplateReader().fetch()
    return _SHIP_LOADOUTS


class _ClientMessage(Enum):
    MoveItem = 1
    BuySkill = 2
    SelectTitle = 3
    BindSticker = 4
    SelectConsumable = 5
    UnbindSticker = 6
    AddShip = 7
    RemoveShip = 8
    SelectShip = 9
    UpgradeShip = 10
    RepairSystem = 11
    RepairShip = 12
    ScrapShip = 13
    CreateAvatar = 14
    SelectFaction = 15
    UpgradeSystem = 16
    SetShipName = 17
    UseAugment = 18
    ChooseDailyBonus = 20
    UpgradeSystemByPack = 21
    MoveAll = 22
    ReadMail = 23
    RemoveMail = 24
    MailAction = 25
    RepairAll = 26
    CheckNameAvailability = 28
    PopupSeen = 30
    ChooseName = 32
    CreateAvatarFactionChange = 33
    InstantSkillBuy = 35
    ReduceSkillLearnTime = 36
    SubmitMission = 37
    AugmentMassActivation = 38
    SendDradisData = 39
    RequestCharacterServices = 40
    ChangeFaction = 41
    ChangeName = 42
    ChangeAvatar = 43
    ResourceHardcap = 44
    DeselectTitle = 45

    @staticmethod
    def from_code(uzenet_kod: int):
        return _CM_BY_VALUE.get(uzenet_kod)


_CM_BY_VALUE = {member.value: member for member in _ClientMessage}


class PlayerProtocol(BgoProtocol):
    REPAIR_DOCK_DELAY_TIME_SECONDS = world_timers().repair_undock_block_seconds

    def __init__(self, ctx, pilot_roster, guild_registry, character_services, data_store, level_curve):
        super().__init__(ProtocolID.Pilot, ctx)
        self._handlers = {}
        self._catalogue = ctx.catalogue
        self._merok = ctx.merok
        self._level_curve = level_curve
        self._data_store = data_store
        self._dradis_data = DradisContacts()
        self._pilot_roster = pilot_roster
        self._guild_registry = guild_registry
        self._writer = replies_for(ProtocolID.Pilot)
        self._character_services = character_services

    def mount_handlers(self) -> None:
        self._handlers[_ClientMessage.ChangeFaction] = FactionSwitch(
            self.user(), self._character_services, self._catalogue, self.ctx.rng)
        self._handlers[_ClientMessage.ReadMail] = MailReading(self.user(), self._writer)
        self._handlers[_ClientMessage.SendDradisData] = DradisReply(self.user(), self._dradis_data)

    def seed_user(self, user) -> None:
        super().seed_user(user)

    @property
    def replies(self):
        return self._writer

    KEZELOK = {
        _ClientMessage.PopupSeen: "_on_popup_seen",
        _ClientMessage.SelectFaction: "_on_select_faction",
        _ClientMessage.SelectTitle: "_on_select_title",
        _ClientMessage.CheckNameAvailability: "_on_check_name_availability",
        _ClientMessage.ChooseName: "_on_choose_name",
        _ClientMessage.ChangeAvatar: "_on_change_avatar",
        _ClientMessage.CreateAvatar: "_on_create_avatar",
        _ClientMessage.RepairShip: "_on_repair_ship",
        _ClientMessage.RepairSystem: "_on_repair_system",
        _ClientMessage.RepairAll: "_on_repair_all",
        _ClientMessage.RequestCharacterServices: "_on_request_character_services",
        _ClientMessage.ResourceHardcap: "_on_resource_hardcap",
        _ClientMessage.MoveItem: "_on_move_item",
        _ClientMessage.BindSticker: "_on_bind_sticker",
        _ClientMessage.UnbindSticker: "_on_unbind_sticker",
        _ClientMessage.SetShipName: "_on_set_ship_name",
        _ClientMessage.ScrapShip: "_on_scrap_ship",
        _ClientMessage.BuySkill: "_on_buy_skill",
        _ClientMessage.InstantSkillBuy: "_on_instant_skill_buy",
        _ClientMessage.MoveAll: "_on_move_all",
        _ClientMessage.AddShip: "_on_add_ship",
        _ClientMessage.SelectShip: "_on_select_ship",
        _ClientMessage.UpgradeShip: "_on_upgrade_ship",
        _ClientMessage.SelectConsumable: "_on_select_consumable",
        _ClientMessage.UpgradeSystem: "_on_upgrade_system",
        _ClientMessage.UpgradeSystemByPack: "_on_upgrade_system_by_pack",
        _ClientMessage.UseAugment: "_on_use_augment",
        _ClientMessage.SubmitMission: "_on_submit_mission",
        _ClientMessage.ChooseDailyBonus: "_on_choose_daily_bonus",
        _ClientMessage.AugmentMassActivation: "_on_augment_mass_activation",
    }

    def read_message(self, msg_type, br) -> None:
        client_message = _ClientMessage.from_code(msg_type)
        if (handler := self._handlers.get(client_message)) is not None:
            handler.handle(br)
            return
        kezelo = self.KEZELOK.get(client_message)
        if kezelo is None:
            log.error(f'PlayerProtocol Could not handle reply_type: {client_message}')
            return
        getattr(self, kezelo)(msg_type, br)

    def _on_popup_seen(self, msg_type, br) -> None:
        popup_id = br.read_uint32()
        log.info('%s popup acknowledged: %s', self.user().user_log(), popup_id)

    def _on_select_faction(self, msg_type, br) -> None:
        faction = Faction.from_code(br.read_byte())
        log.info('%s picking a side %s', self.user().user_log(), faction)
        if faction != Faction.Colonial and faction != Faction.Cylon:
            self.user().attach_link(None)
            return
        player = self.user().pilot_of()
        if player.location.game_location == PlaceKind.Starter:
            player.faction = faction
            player.seed_hangar()
            self.user().send(self._writer.faction(faction))
            player.location.switch_state(AtAvatar(player.location))
            self.user().protocol_of(ProtocolID.Scene).push_scene_change()
        else:
            log.warning('%s cheat: faction pick arrived outside the starter flow; state was%s',
                        self.user().user_log(), player.location.game_location)

    def _on_select_title(self, msg_type, br) -> None:
        duty_id = br.read_uint16()

    def _on_check_name_availability(self, msg_type, br) -> None:
        requested_name = br.read_string()
        log.info('%s name lookup asked for %s', self.user().user_log(), requested_name)
        is_free = self._pilot_roster.name_available(requested_name, self.user().pilot_of().user_id_of())
        self.user().send(self.push_name_verdict(is_free))

    def _on_choose_name(self, msg_type, br) -> None:
        name_chosen = br.read_string()
        player = self.user().pilot_of()
        if len(player.name) != 0:
            log.error('%s Cheat Pilot tried to change name even though the name was already set! %s',
                      self.user().user_log(), name_chosen)
            return
        is_present = self._pilot_roster.reserved_name_for(
            name_chosen, player.user_id_of())
        if is_present:
            player.name = name_chosen
            self.user().send(self._writer.name(name_chosen))
            community_protocol = self.user().protocol_of(ProtocolID.Community)
            if community_protocol is not None:
                community_protocol.resend_chat_session_id()

    def _on_change_avatar(self, msg_type, br) -> None:
        player = self.user().pilot_of()
        avatar_description = AvatarLook()
        avatar_description.read(br)
        player.avatar_description.set(avatar_description)
        self.user().send(self._writer.avatar_description(player.avatar_description.get()))
        self._data_store.refresh_avatar(player.user_id_of(), avatar_description)

    def _on_create_avatar(self, msg_type, br) -> None:
        self._handle_create_avatar(br, self.user().protocol_of(ProtocolID.Scene))

    def _on_repair_ship(self, msg_type, br) -> None:
        self._handle_repair_ship(br)

    def _on_repair_system(self, msg_type, br) -> None:
        self._handle_repair_system(br)

    def _on_repair_all(self, msg_type, br) -> None:
        self._handle_repair_all(br)

    def _on_request_character_services(self, msg_type, br) -> None:
        self.user().send(self._writer.character_services(self._character_services))

    def _on_resource_hardcap(self, msg_type, br) -> None:
        guid = br.read_uint32()
        is_token = ResourceKind.Token.guid == guid
        if not is_token:
            log.error('%s hardcap request on a non-token resource - smells like a modified client',
                      self.user().user_log())
            return
        token_cap = self.user().pilot_of().merits_cap_farmed
        is_same_date = (token_cap.last_reset.local_date.timetuple().tm_yday
                        == _dt.datetime.now(_UTC).timetuple().tm_yday)
        if not is_same_date:
            token_cap.reset_cap()
        self.user().send(self._writer.merits_cap(token_cap))

    def _on_move_item(self, msg_type, br) -> None:
        log.debug('item move')
        self._handle_move_item(br)

    def _on_bind_sticker(self, msg_type, br) -> None:
        ship_id = br.read_uint16()
        with suppress(Exception):
            player = self.user().pilot_of()
            log.warning(f'sticker attach asked on a ship {ship_id}')
            sticker_binding = br.read_desc(StickerMount)
            hangar_ship = player.hangar_of().by_server_id(ship_id)
            hangar_ship.take_sticker(sticker_binding)
            self.user().send(self._writer.ship_sticker_binding(hangar_ship))

    def _on_unbind_sticker(self, msg_type, br) -> None:
        ship_id = br.read_uint16()
        spot_id = br.read_uint16()
        player = self.user().pilot_of()
        hangar_ship = player.hangar_of().by_server_id(ship_id)
        for sticker in list(hangar_ship.stickers):
            if sticker.object_point_hash == spot_id:
                hangar_ship.peel_sticker(sticker)

    def _on_set_ship_name(self, msg_type, br) -> None:
        ship_id = br.read_uint16()
        ship_name = br.read_string()
        player = self.user().pilot_of()
        if (hangar_ship := player.hangar_of().by_server_id(ship_id)) is not None:
            log.info('ship renamed to %s', ship_name)
            hangar_ship.name = ship_name
            self.user().send(self.push_ship_name(hangar_ship))

    def _on_scrap_ship(self, msg_type, br) -> None:
        ship_id = br.read_uint16()
        log.warning('%s cheat: scrap request that no client should send, id%s',
                    self.user().user_log(), ship_id)

    def _on_buy_skill(self, msg_type, br) -> None:
        skill_id = br.read_uint16()
        player = self.user().pilot_of()
        skill_book = player.skill_book
        is_enough = skill_book.experience_reaches_next_level(skill_id)
        if not is_enough:
            log.warning('%s skill purchase exceeds the free experience available or no such training exists - wrong id, or unlisted',
                        self.user().user_log())
            return
        self.raise_skill(skill_id)

    def _on_instant_skill_buy(self, msg_type, br) -> None:
        skill_id = br.read_uint16()
        log.error('%s instant skill purchase reached code that should be dead: %s',
                  self.user().user_log(), skill_id)
        debug_protocol = self.user().protocol_of(ProtocolID.Debug)
        debug_protocol.tell_console('instant skill purchase reached dead code')

    def _on_move_all(self, msg_type, br) -> None:
        self._handle_move_all(br)

    def _on_add_ship(self, msg_type, br) -> None:
        ship_guid = br.read_guid()
        self.berth_ship(ship_guid)

    def _on_select_ship(self, msg_type, br) -> None:
        ship_id = br.read_uint16()
        self.activate_ship(ship_id)

    def _on_upgrade_ship(self, msg_type, br) -> None:
        self._handle_upgrade_ship(br)

    def _on_select_consumable(self, msg_type, br) -> None:
        self._handle_select_consumable(br)

    def _on_upgrade_system(self, msg_type, br) -> None:
        self._handle_upgrade_system(br)

    def _on_upgrade_system_by_pack(self, msg_type, br) -> None:
        self._handle_upgrade_system_by_pack(br)

    def _on_use_augment(self, msg_type, br) -> None:
        self._handle_use_augment(br)

    def _on_submit_mission(self, msg_type, br) -> None:
        self._handle_submit_mission(br)

    def _on_augment_mass_activation(self, msg_type, br) -> None:
        self._handle_augment_mass_activation(br)


    def _handle_create_avatar(self, br, scene_protocol) -> None:
        avatar_description = br.read_desc(AvatarLook)
        player = self.user().pilot_of()

        if avatar_description is not None:
            self._data_store.refresh_avatar(player.user_id_of(), avatar_description)
            player.avatar_description.set(avatar_description)

        setting_protocol = self.user().protocol_of(ProtocolID.Setting)
        setting_protocol.push_settings()

        self.user().send(self._writer.avatar_description(player.avatar_description.get()))

        self.user().send(self._writer.write_id(player.user_id_of()))

        self.push_shared_experience()

        self.user().send(self._writer.faction(player.faction))

        self.push_hangar()
        self.user().send(self._writer.active_player_ship(player.hangar_of().active_ship().server_id))
        self.push_durability()
        self.push_ship_slots()
        self.push_ship_names()


        self.user().send(self._writer.skills(player.skill_book))

        factors = player.factors
        self.user().send(self._writer.factors(factors))

        player.tally_desk.counters().wake_all()
        self.user().send(self._writer.counters(player.tally_desk.counters()))

        starter_params = self.ctx.server_config.starter_params
        start_cubits = CountableItem.from_guid(ResourceKind.Cubits.guid, starter_params.start_cubits)
        start_tylium = CountableItem.from_guid(ResourceKind.Tylium.guid, starter_params.start_tylium)
        start_titanium = CountableItem.from_guid(ResourceKind.Titanium.guid, starter_params.start_titanium)
        start_merits = CountableItem.from_guid(ResourceKind.Token.guid, starter_params.start_token)

        player.hold.add_ship_item(start_tylium)
        player.hold.add_ship_item(start_cubits)
        player.hold.add_ship_item(start_titanium)
        player.hold.add_ship_item(start_merits)

        self.user().send(self._writer.all_container_items(player.hold))

        if self.ctx.server_config.starter_params.testing_mode:
            exp = 10_000_000
            self.earn_experience(exp)

        active_ship = player.hangar_of().active_ship()
        self.user().send(self.hangar_ship_stats(active_ship))

        player.location.switch_state(InCic(player.location))
        scene_protocol.push_scene_change()

    def _is_repair_location_allowed(self) -> bool:
        player = self.user().pilot_of()
        if player.location.game_location == PlaceKind.Room:
            return True

        carrier_config = get_carrier_mode_config()
        if not carrier_config.repair_enabled:
            return False

        try:
            game_protocol = self.user().protocol_of(ProtocolID.Game)
            sec_player_ship = game_protocol._locate_ship_in_sector()
        except Exception:
            log.exception("Could not resolve sector player ship for carrier repair")
            return False

        if not sec_player_ship.pair_complete():
            return False

        player_ship = sec_player_ship.player_ship
        visibility = player_ship.visibility_of()
        anchored_object_id = visibility.anchored_object_id
        if visibility.is_visible() or anchored_object_id == 0:
            return False

        carrier = sec_player_ship.sector().ctx.space_objects().get(anchored_object_id)
        if carrier is None or carrier.is_removed() or not is_carrier_space_object(carrier):
            return False
        if (carrier_config.require_fortified_for_anchor
            and not carrier.world_state_of().is_fortified):
            return False

        party = player.party()
        return party is not None and party.is_in_party(carrier.pilot_id())

    def _handle_repair_ship(self, br) -> None:
        ship_id = br.read_uint16()
        repair_value = br.read_single()
        use_cubits = br.read_boolean()

        if not self._is_repair_location_allowed():
            log.warning('cheat {}: ship repair issued from the wrong place ({})'.format(
                self.user().user_log(), self.user().pilot_of().location.game_location))
            return

        wear_cost = WearCost(self._catalogue.world_card)
        hangar_ship_to_repair = self.user().pilot_of().hangar_of().by_server_id(ship_id)
        costs = wear_cost.ship_hull_repair_costs(hangar_ship_to_repair, use_cubits)

        resource_type = ResourceKind.repair_type(use_cubits)

        from rebsgo.pilots.state.holdings.walks.hold_walk import HoldWalk
        hold_walker = HoldWalk(self.user(), self.ctx.rng)
        reduction_successfully = hold_walker.spend_resource(resource_type, int(costs))
        if not reduction_successfully:
            log.warning('%s repair charge did not add up', self.user().user_log())
            return

        hangar_ship_to_repair.restore_durability()

        self.user().send(self._writer.ship_info_durability(hangar_ship_to_repair))
        self.user().send(self._writer.ship_slots(hangar_ship_to_repair))
        hangar_ship_to_repair.ship_stats().cap_hull_and_power()

        self.push_undock_block(self.REPAIR_DOCK_DELAY_TIME_SECONDS)

    def _handle_repair_system(self, br) -> None:
        from rebsgo.pilots.state.holdings.move_request import MoveRequest
        transfer_request = MoveRequest(br, self.user().pilot_of())
        transfer_request.read_repair()

        if not self._is_repair_location_allowed():
            log.warning("Cheat {} cheats, repair_system, wrong location for repair process location={}".format(
                self.user().user_log(), self.user().pilot_of().location.game_location))
            return

        from_container = transfer_request.source_container
        server_id = br.read_uint16()
        repair_value = br.read_single()
        use_cubits = br.read_boolean()
        container_type = from_container.container_id.container_type
        if container_type == StorageKind.Hold or container_type == StorageKind.Locker:
            log.info(f'repairing from hold or locker {server_id} {use_cubits} {repair_value}')
        elif container_type == StorageKind.ShipSlot:
            log.info(f'repairing a mounted system {server_id} {use_cubits} {repair_value}')
        else:
            log.warning('suspicious pilot %s would repair an item held in %s',
                        self.user().pilot_of().player_log, container_type)
            return

        hangar = self.user().pilot_of().hangar_of()
        active_ship = hangar.active_ship()
        slot = active_ship.ship_slots.slot(server_id)
        if slot is None or slot.ship_system is None or slot.ship_system.card_guid_of() == 0:
            log.warning("Cheating user %s attempted to repair empty/missing slot %s",
                        self.user().pilot_of().player_log, server_id)
            return
        wear_cost = WearCost(self._catalogue.world_card)
        costs = int(wear_cost.cost_of_system(slot.ship_system, use_cubits))
        resource_type = ResourceKind.repair_type(use_cubits)

        from rebsgo.pilots.state.holdings.walks.hold_walk import HoldWalk
        hold_walker = HoldWalk(self.user(), self.ctx.rng)
        reduction_successfully = hold_walker.spend_resource(resource_type, costs)
        if not reduction_successfully:
            return

        wear_cost.repair_system(slot)

        self.user().send(self._writer.ship_info_durability(active_ship))
        self.user().send(self._writer.ship_slots(active_ship))
        self.push_undock_block(self.REPAIR_DOCK_DELAY_TIME_SECONDS)

    def _handle_repair_all(self, br) -> None:
        ship_id = br.read_uint16()
        use_cubits = br.read_boolean()
        player = self.user().pilot_of()
        hangar_ship = player.hangar_of().by_server_id(ship_id)
        if hangar_ship is None:
            return

        if not self._is_repair_location_allowed():
            log.warning('cheat {}: repair-all issued from the wrong place ({})'.format(
                self.user().user_log(), self.user().pilot_of().location.game_location))
            return

        wear_cost = WearCost(self._catalogue.world_card)
        total_repair_costs = wear_cost.repair_all_costs(hangar_ship, use_cubits)

        resource_type = ResourceKind.repair_type(use_cubits)
        dbg_msg = self.user().pilot_of().name + 'total price ' + str(total_repair_costs) + " type " + str(resource_type)

        from rebsgo.pilots.state.holdings.walks.hold_walk import HoldWalk
        hold_walker = HoldWalk(self.user(), self.ctx.rng)
        try:
            reduction_successfully = hold_walker.spend_resource(resource_type, total_repair_costs)
            if not reduction_successfully:
                return
        except ValueError as hibas_ertek:
            log.warning('%s repair-all met a value it cannot use%s', self.user().user_log(),
                        hibas_ertek)
            return

        hangar_ship.restore_durability()
        for rekesz in hangar_ship.ship_slots.values():
            wear_cost.repair_system(rekesz)

        self.user().send(self._writer.ship_info_durability(hangar_ship))
        self.user().send(self._writer.ship_slots(hangar_ship))
        hangar_ship.ship_stats().cap_hull_and_power()

        if not self._catalogue.map_card.is_base_sector(player.faction, player.location.sector_id):
            self.push_undock_block(self.REPAIR_DOCK_DELAY_TIME_SECONDS)

    def _handle_move_all(self, br) -> None:
        player = self.user().pilot_of()
        from rebsgo.pilots.state.holdings.move_request import MoveRequest
        transfer_request = MoveRequest(br, player)
        try:
            transfer_request.read_move_all()
        except IOError:
            return
        except ValueError as hibas_ertek:
            log.warning('%s claiming every attachment from the mail: %s', self.user().user_log(),
                        hibas_ertek)
            return

        from_container = transfer_request.source_container
        to = transfer_request.to

        items_to_send = []

        if isinstance(from_container.container_id, MailName):
            mail_container_id = from_container.container_id
            mail_removed = player.mail_box.remove_item(mail_container_id.mail_id)
            self.user().send(self.items_taken_out(from_container, from_container.all_items_ids()))
            items_to_send.extend(mail_removed.mail_container.all_ship_items)
        for item_to_send in items_to_send:
            if isinstance(item_to_send, CountableItem):
                countable = item_to_send
                if (existing_countable_opt := to.holds_stack_of(countable)) is not None:
                    existing_countable = existing_countable_opt
                    self.user().send(self.push_item_removed(to, existing_countable.server_id))
                    to.take_item(existing_countable.server_id)
                    countable.grow_count(existing_countable.count())
            to.add_ship_item(item_to_send)

        self.user().send(self.push_items_added(to, items_to_send))

    def _handle_upgrade_ship(self, br) -> None:
        ship_id = br.read_uint16()
        player = self.user().pilot_of()
        location = player.location
        is_in_room = location.game_location == PlaceKind.Room
        if not is_in_room:
            log.warning('%s upgraded a ship with no station around - refused', self.user().user_log())
            return

        hangar = player.hangar_of()
        ship_to_upgrade = hangar.by_server_id(ship_id)
        if ship_to_upgrade is None:
            log.warning('no ship by that id to upgrade')
            return
        shop_item_card = ship_to_upgrade.shop_item_card
        ship_card = ship_to_upgrade.ship_card_of()
        if ship_card.next_ship_card_guid == 0:
            log.warning('this hull has no upgrade path')
            return
        upgraded_ship_card = self._catalogue.card_of(ship_card.next_ship_card_guid, CardView.Ship)

        if upgraded_ship_card is None:
            log.warning(f'upgraded hull card missing: {ship_card.card_guid_of()}')
            return

        from rebsgo.pilots.state.holdings.walks.shop_walk import ShopWalk
        shop_walker = ShopWalk(self.user(), None, self.ctx.rng)
        is_enough_in_hangar = ShopWalk.enough_held(shop_item_card.upgrade_price, player.hold, 1)
        if not is_enough_in_hangar:
            log.warning('%s hull upgrade without the funds to pay it - flagging as cheat',
                        self.user().user_log())
            return
        shop_walker.take_payment(shop_item_card.upgrade_price, player.hold, 1)

        upgraded_hangar_ship = HangarShip(player.user_id_of(), upgraded_ship_card.hangar_id,
                                          upgraded_ship_card.card_guid_of(), ship_to_upgrade.name)
        upgraded_hangar_ship.take_slots(ship_to_upgrade.ship_slots)
        upgraded_hangar_ship.ship_stats().set_hull(
            upgraded_hangar_ship.ship_stats().stat(ObjectStat.MaxHullPoints))
        upgraded_hangar_ship.ship_stats().set_power(
            upgraded_hangar_ship.ship_stats().stat(ObjectStat.MaxPowerPoints))
        upgraded_hangar_ship.ship_stats().fold_in_stats()

        old_subscribers = ship_to_upgrade.ship_stats().subscribers
        failed_subscribers = set()
        for sub_key, sub_value in list(old_subscribers.items()):
            upgraded_hangar_ship.ship_stats().restore_watcher(sub_value)
            send_successfull = sub_key.flush_property_buffer(sub_value)
            if not send_successfull:
                failed_subscribers.add(sub_key)
        old_subscribers.clear()
        for sub in failed_subscribers:
            upgraded_hangar_ship.ship_stats().remove_subscriber(sub)

        hangar.berth(upgraded_hangar_ship)

        self.user().send(self.push_ship_added(upgraded_hangar_ship))
        self.user().send(self._writer.ship_slots(upgraded_hangar_ship))
        self.user().send(self._writer.ship_info_durability(upgraded_hangar_ship))
        self.activate_ship(ship_id)

    def _handle_select_consumable(self, br) -> None:
        ship_id = br.read_uint16()
        consumable_guid = br.read_guid()
        slot_id = br.read_uint16()
        player = self.user().pilot_of()

        hangar = player.hangar_of()
        ship = hangar.by_server_id(ship_id)
        if ship is None:
            return

        hold = player.hold
        if (consumable := hold.by_guid(consumable_guid)) is not None:
            item_countable = consumable
            slot = ship.ship_slots.slot(slot_id)
            if slot is None:
                return
            slot.current_consumable = item_countable
            space_subscribe_info = ship.ship_stats()
            space_subscribe_info.fold_in_stats()

            self.user().send(self._writer.ship_slots(ship))

    def _handle_upgrade_system(self, br) -> None:
        player = self.user().pilot_of()
        from rebsgo.pilots.state.holdings.move_request import MoveRequest
        transfer_request = MoveRequest(br, player)
        tarolo = transfer_request.read_container
        item_id = br.read_uint16()
        new_level = br.read_byte() & 0xFF

        item_to_upgrade = tarolo.by_id(item_id)

        if item_to_upgrade is None:
            log.info('%s upgrade target absent from the container', self.user().user_log())
            return
        if item_to_upgrade.item_type != ItemType.System:
            log.info('%s upgrade target is not a ship system', self.user().user_log())
            return
        ship_system_to_upgrade = item_to_upgrade
        item_card = ship_system_to_upgrade.ship_system_card
        if item_card is None:
            log.info('%s asked about an item with no card behind it', self.user().user_log())
            return

        log.info('%s upgrading a system: %s %s %s', self.user().user_log(),
                 tarolo.container_id.container_type, item_id, new_level)
        log.info("UpgradeSystem [{}] container: {}, itemID: {}, current_level: {}, new_level: {}".format(
            self.user().user_log(),
            tarolo.container_id.container_type,
            item_id,
            ship_system_to_upgrade.ship_system_card.level,
            new_level))

        if not item_card.player_may_upgrade:
            log.info('%s cheat: upgrade on an item that never upgrades', self.user().user_log())
            return
        if item_card.next_card_guid == 0:
            log.info('%s cheat: upgrade with no successor card to move to',
                     self.user().user_log())
            return
        if item_card.level >= new_level:
            log.info('%s cheat: requested level does not exceed the current one',
                     self.user().user_log())
            return
        if new_level > 10:
            log.info('%s cheat: system level pushed past the 10 ceiling', self.user().user_log())
            return
        if tarolo.container_id.container_type == StorageKind.Shop:
            log.info('%s someone poked the shop system update path', self.user().user_log())
            return

        skill_hashes = ship_system_to_upgrade.ship_system_card.skill_hashes
        skills_allow_upgrade = self.user().pilot_of().skill_book.skills_allow_upgrade(
            skill_hashes, item_card.level + 1)
        if not skills_allow_upgrade:
            log.warning('cheat ({}): upgrade attempted with the gating skill missing'.format(self.user().user_log()))
            return

        from rebsgo.pilots.state.holdings.walks.walker_source import walker_for
        storage_walker = walker_for(
            tarolo.container_id.container_type, self.user(), transfer_request, self.ctx.rng)

        successfull = storage_walker.upgrade_system(tarolo, player.hold, ship_system_to_upgrade, new_level)

        log.info(f'system upgrade went through: {successfull}')

    def _handle_upgrade_system_by_pack(self, br) -> None:
        player = self.user().pilot_of()
        from rebsgo.pilots.state.holdings.move_request import MoveRequest
        transfer_request = MoveRequest(br, player)
        tarolo = transfer_request.read_container
        item_id = br.read_uint16()
        pack_count = br.read_uint32()

        ship_system_to_upgrade = tarolo.by_id(item_id)
        if ship_system_to_upgrade is None or ship_system_to_upgrade.item_type != ItemType.System:
            return
        item_card = ship_system_to_upgrade.ship_system_card

        akadalyok = (
            (not item_card.player_may_upgrade, 'upgrade on a non-upgradeable item'),
            (item_card.next_card_guid == 0, 'upgrade with nowhere to go - no successor card'),
            (tarolo.container_id.container_type == StorageKind.Shop,
             'someone poked the shop system update path'),
        )
        for all_utjaban, miert in akadalyok:
            if all_utjaban:
                log.info('%s %s', self.user().user_log(), miert)
                return

        skill_hashes = ship_system_to_upgrade.ship_system_card.skill_hashes
        skills_allow_upgrade = self.user().pilot_of().skill_book.skills_allow_upgrade(
            skill_hashes, item_card.level + 1)
        if not skills_allow_upgrade:
            log.warning('cheat ({}): upgrade attempted with the gating skill missing'.format(self.user().user_log()))
            return

        log.info("UpgradeSystemByPack system {} current {} pack_count {}".format(
            ship_system_to_upgrade.card_guid_of(),
            ship_system_to_upgrade.ship_system_card.level,
            pack_count))

        from rebsgo.pilots.state.holdings.walks.walker_source import walker_for
        storage_walker = walker_for(
            tarolo.container_id.container_type, self.user(), transfer_request, self.ctx.rng)
        upgrade_result = storage_walker.upgrade_with_pack(
            tarolo, player.hold, ship_system_to_upgrade, pack_count)

    def _handle_use_augment(self, br) -> None:
        player = self.user().pilot_of()
        from rebsgo.pilots.state.holdings.move_request import MoveRequest
        transfer_request = MoveRequest(br, player)
        transfer_request.read_augment_use()
        tarolo = transfer_request.source_container

        tetel = tarolo.by_id(transfer_request.item_id)
        if tetel is None:
            return

        augment_template = augment_template_for(tetel.card_guid_of())
        if augment_template is None:
            log.error(f'augment fired without any template behind it {tetel.card_guid_of()}')
            return
        if isinstance(augment_template, AugmentExperienceSpec):
            from rebsgo.pilots.state.holdings.walks.walker_source import walker_for
            storage_walker = walker_for(
                tarolo.container_id.container_type, self.user(), transfer_request, self.ctx.rng)
            if not storage_walker.use_augment():
                return
            self.earn_experience(augment_template.experience)
            log.info('%s used an experience accelerator: +%s xp',
                     self.user().user_log(), augment_template.experience)
            return
        if not isinstance(augment_template, AugmentBoostSpec):
            log.error('factor template absent')
            return
        augment_factor_template = augment_template

        new_factors_lst = Boost.of_template(augment_factor_template)
        factors = player.factors
        korlatok = factors.multiplicators_for_limit_left(augment_factor_template.factor_source)
        can_activate = True
        for szorzo in new_factors_lst:
            korlat = korlatok.get(szorzo.factor_type, factors.boost_limiter)
            if szorzo.value > korlat:
                can_activate = False
                break
        if not can_activate:
            self.user().send(self._writer.cannot_stack_boosters())
            return

        from rebsgo.pilots.state.holdings.walks.walker_source import walker_for
        storage_walker = walker_for(
            tarolo.container_id.container_type, self.user(), transfer_request, self.ctx.rng)
        operation_is_okay = storage_walker.use_augment()
        if not operation_is_okay:
            return

        self.light_augment(tetel.card_guid_of())

    def _handle_submit_mission(self, br) -> None:
        mission_id = br.read_uint16()
        mission_book = self.user().pilot_of().tally_desk.mission_book
        log.info('turning in assignment {}'.format(mission_id))
        mission = mission_book.by_id(mission_id)
        if mission is None:
            return
        if mission.mission_state is None or mission.mission_state != Assignment.AssignmentState.Completed:
            log.warning('cheat: {} turned in a mission in state {}'.format(
                self.user().user_log(), mission.mission_state))
            return
        mission_cards_fetch_result = self._catalogue.mission_cards(mission.mission_card_guid)
        if not mission_cards_fetch_result.usable:
            log.warning("AssignmentCardRow was invalid!")
            return
        mission.mark_mission(Assignment.AssignmentState.Submitting)
        reward_card = mission_cards_fetch_result.reward_card
        exp = reward_card.experience
        loot_all = reward_card.ship_items
        faction_loot = reward_card.ship_items_for_faction(self.user().pilot_of().faction)
        result_item_lst = []
        result_item_lst.extend(loot_all)
        result_item_lst.extend(faction_loot)

        from rebsgo.vocabulary.pilot import BoostKind
        from rebsgo.gamedata.ship_parts.parts import CountableItem as _ItemCountable
        reward_mult = self.user().pilot_of().factors.multiplier_for(BoostKind.MissionReward)
        if reward_mult > 1:
            result_item_lst = [
                _ItemCountable.from_guid(i.card_guid_of(), int(i.count() * reward_mult))
                if isinstance(i, _ItemCountable) else i
                for i in result_item_lst]

        notification_writer = replies_for(ProtocolID.Notification)
        self.user().send(notification_writer.mission_completed(mission_id))
        self.user().send(notification_writer.mission_reward(mission.mission_card_guid, result_item_lst))
        self.user().send(self._writer.remove_missions([mission_id]))
        mission_book.remove_item(mission_id)
        self.earn_experience(exp)
        self._merok.assignment_handed_in(self.user().pilot_of().faction)
        self.user().pilot_of().tally_desk.bump_counter(TallyCardKind.missions_completed, 0)
        from rebsgo.pilots.state.holdings.walks.storage_walk import deliver_item
        for tetel in result_item_lst:
            deliver_item(self.user(), tetel, self.user().pilot_of().hold)

    def _on_choose_daily_bonus(self, msg_type, br) -> None:
        valasztott = br.read_uint32()
        player = self.user().pilot_of()
        felajanlott = player.daily_offer_guid
        if isinstance(felajanlott, int):
            felajanlott = [felajanlott]
        if not felajanlott or valasztott not in felajanlott:
            log.warning('%s claimed login reward %s that was never offered',
                        self.user().user_log(), valasztott)
            return
        reward_card = self._catalogue.card_of(valasztott, CardView.Reward)
        if reward_card is None:
            log.error('login reward card %s is missing from the catalogue', valasztott)
            return

        from rebsgo.services import Services
        from rebsgo.runtime.daily_bonus_service import LoginStreakService
        streak_service = Services.get(LoginStreakService)
        nap = streak_service.day_for(player)
        if nap <= 0:
            log.warning('%s claimed a login reward twice today', self.user().user_log())
            return

        tetelek = []
        tetelek.extend(reward_card.ship_items)
        tetelek.extend(reward_card.ship_items_for_faction(player.faction))
        from rebsgo.pilots.state.holdings.walks.storage_walk import deliver_item
        for tetel in tetelek:
            deliver_item(self.user(), tetel, player.hold)
        if reward_card.experience:
            self.earn_experience(reward_card.experience)

        import datetime as _sdt
        player.daily_streak_day = nap
        player.daily_streak_date = _sdt.datetime.now(_sdt.timezone.utc).date().isoformat()
        player.daily_offer_guid = None
        player.tally_desk.bump_counter(TallyCardKind.daily_login, 0)
        log.info('%s collected login day %s: %s item kind(s), %s xp',
                 self.user().user_log(), nap, len(tetelek), reward_card.experience)

    def _handle_augment_mass_activation(self, br) -> None:
        player = self.user().pilot_of()
        from rebsgo.pilots.state.holdings.move_request import MoveRequest
        transfer_request = MoveRequest(br, player)
        iterations = transfer_request.read_bulk_augment()
        log.info(f'bulk augment: {transfer_request.source_container} {transfer_request.item_id} {iterations}')
        item_to_analyse = transfer_request.source_container.by_id(transfer_request.item_id)

        from rebsgo.pilots.state.holdings.walks.walker_source import walker_for
        storage_walker = walker_for(
            transfer_request.source_container.container_id.container_type,
            self.user(), transfer_request, self.ctx.rng)

        operation_is_okay = storage_walker.consume_for_bulk_augment(iterations)
        if not operation_is_okay:
            return

        self.identify_unknown(item_to_analyse.card_guid_of(), iterations)


    def push_undock_block(self, tiltas_mp: int) -> None:
        self.user().send(self.push_capability_value(
            Capability.Undock, _dt.datetime.now(_UTC) + _dt.timedelta(seconds=tiltas_mp)))

        def _delayed_capability_reset():
            self.user().send(self.push_capability_reset(Capability.Undock))

        self.ctx.timetable.after(tiltas_mp, _delayed_capability_reset)

    def light_augment(self, targy_guid: int, egyedi_orak: int = -1) -> None:
        factors = self.user().pilot_of().factors
        augment_template = augment_template_for(targy_guid)
        if augment_template is None:
            log.error('augment {} vanished before activation for player {}'.format(
                targy_guid, self.user().user_log()))
            self.tell_debug('augment activation could not locate the augment')
            return
        if not isinstance(augment_template, AugmentBoostSpec):
            self.tell_debug('augment activation on a non-factor kind - refusing')
            return
        augment_factor_template = augment_template
        log.info('{} activated augment item {}'.format(
            self.user().user_log(), augment_factor_template.associated_item_guid))
        factor_lst = Boost.of_template(augment_factor_template, egyedi_orak)
        for szorzo in factor_lst:
            factors.take_boost(szorzo)
        self.user().send(self._writer.factors(factor_lst))

    def tell_debug(self, msg: str) -> None:
        debug_protocol = self.user().protocol_of(ProtocolID.Debug)
        debug_protocol.tell_console(msg)

    def berth_ship(self, ship_guid: int) -> None:
        player = self.user().pilot_of()
        if not player.location.is_in_room:
            log.warning('cheat={}: ship added while not stationside'.format(self.user().user_log()))
            return

        ship_card = self._catalogue.card_of(ship_guid, CardView.Ship)
        shop_item_card = self._catalogue.card_of(ship_guid, CardView.Price)

        if ship_card is None or shop_item_card is None:
            log.error(f'Pilot {player.user_id_of()} named a ship or shop guid that resolves to nothing: {ship_guid}')
            return

        if ship_card.level > 1:
            log.error(f'ship granted at a level above one: {ship_card.level}')
            return

        if not player.bgo_admin_roles.holds_any_role(ServerRoles.Developer):
            current_player_level = player.skill_book.get()
            if ship_card.level_requirement > current_player_level:
                log.warning('cheat: {} under-levelled for this hull (at {}, needs {})'.format(
                    self.user().user_log(), current_player_level, ship_card.level_requirement))
                return
            if shop_item_card.faction != player.faction:
                log.warning('cheat: {} shopping across factions (theirs {}, needed {})'.format(
                    self.user().user_log(), player.faction, shop_item_card.faction))
                return

        from rebsgo.world.capitals.capital_roster import is_capital_guid
        if is_capital_guid(ship_guid):
            self.deploy_capital_ship(ship_card, shop_item_card)
            return

        buy_price = shop_item_card.buy_price
        from rebsgo.pilots.state.holdings.walks.shop_walk import ShopWalk
        from rebsgo.pilots.state.holdings.walks.storage_walk import StorageWalk
        shop_walker = ShopWalk(self.user(), None, self.ctx.rng)
        is_enough_in_hangar = StorageWalk.enough_held(buy_price, player.hold, 1)
        if is_enough_in_hangar:
            log.info('%s bought a ship for %s', self.user().user_log(), buy_price)
            shop_walker.take_payment(buy_price, player.hold, 1)
            hangar = player.hangar_of()
            new_ship = HangarShip(player.user_id_of(), ship_card.hangar_id, ship_guid, "")
            self._install_default_loadout(new_ship, ship_guid)
            new_ship.ship_stats().skill_book = player.skill_book
            new_ship.ship_stats().fold_in_stats()
            new_ship.ship_stats().set_hull(new_ship.ship_stats().stat_or_default(ObjectStat.MaxHullPoints))
            new_ship.ship_stats().set_power(new_ship.ship_stats().stat_or_default(ObjectStat.MaxPowerPoints))
            hangar.berth(new_ship)
            self.user().send(self.push_ship_added(new_ship))
            self.user().send(self._writer.ship_slots(new_ship))
            self.user().send(self._writer.ship_info_durability(new_ship))

    def _install_default_loadout(self, hangar_ship, ship_guid: int) -> None:
        loadout = _get_ship_loadouts().loadout_for(ship_guid)
        if not loadout:
            return
        from rebsgo.gamedata.ship_parts.parts import ShipSystem
        rekeszek = hangar_ship.ship_slots
        installed = 0
        for slot_id, system_guid in loadout:
            slot = rekeszek.slot(slot_id)
            if slot is None:
                log.warning("default loadout for ship %s references missing slot %s", ship_guid, slot_id)
                continue
            try:
                slot.add_ship_item(ShipSystem.from_guid(system_guid))
                installed += 1
                self.load_capital_ammo_into_slot(slot)
            except Exception:
                log.exception("could not install default module %s into ship %s slot %s",
                              system_guid, ship_guid, slot_id)
        log.info("Installed default loadout on ship %s: %s/%s modules", ship_guid, installed, len(loadout))

    _CAPITAL_DEFAULT_AMMO = capital_rules().default_ammo
    _CAPITAL_EXTRA_AMMO = capital_rules().ammo_counts

    def load_capital_ammo_into_slot(self, slot) -> None:
        from rebsgo.gamedata.reading import ShipConsumableOption
        try:
            kepesseg = slot.ship_ability()
            if kepesseg is None:
                return
            ac = kepesseg.ship_ability_card
            if ac is None or ac.consumable_option_of() != ShipConsumableOption.Using:
                return
            if (loszer := self._CAPITAL_DEFAULT_AMMO.get(ac.consumable_type)) is not None:
                slot.current_consumable = CountableItem.from_guid(loszer, 9999)
        except Exception:
            log.exception("could not load capital ammo into slot")

    def _capital_desk(self):
        from rebsgo.services import Services
        from rebsgo.world.capitals.capital_roster import CapitalRoster
        return Services.get(CapitalRoster)

    def deploy_capital_ship(self, ship_card, shop_item_card) -> None:
        import time as _time
        from rebsgo.world.capitals.capital_roster import (
            CAPITAL_SECTOR, DURATION_SECONDS, capital_guid_for)
        player = self.user().pilot_of()
        frakcio = player.faction
        guid = ship_card.card_guid_of()
        if capital_guid_for(frakcio) != guid:
            log.warning("Capital faction mismatch: %s tried guid %s", frakcio, guid)
            return
        hangar = player.hangar_of()
        capital_slot = ship_card.hangar_id
        previous_active_ship_id = self._capital_desk().previous_active_ship(player.user_id_of())
        try:
            active_before_capital = hangar.active_ship()
            if active_before_capital is not None and active_before_capital.server_id != capital_slot:
                previous_active_ship_id = active_before_capital.server_id
        except Exception:
            log.exception("could not remember pre-capital active ship for %s", self.user().user_log())
        if hangar.by_server_id(capital_slot) is not None:
            hangar.remove_hangar_ship(capital_slot)
        buy_price = shop_item_card.buy_price
        from rebsgo.pilots.state.holdings.walks.shop_walk import ShopWalk
        from rebsgo.pilots.state.holdings.walks.storage_walk import StorageWalk
        shop_walker = ShopWalk(self.user(), None, self.ctx.rng)
        if not StorageWalk.enough_held(buy_price, player.hold, 1):
            log.info('%s cannot afford the capital ship at %s', self.user().user_log(), buy_price)
            return
        shop_walker.take_payment(buy_price, player.hold, 1)
        new_ship = HangarShip(player.user_id_of(), capital_slot, guid, "")
        self._install_default_loadout(new_ship, guid)
        try:
            for _ammo in set(self._CAPITAL_DEFAULT_AMMO.values()):
                player.hold.add_ship_item(CountableItem.from_guid(_ammo, 9999))
            for _ammo, _count in self._CAPITAL_EXTRA_AMMO.items():
                player.hold.add_ship_item(CountableItem.from_guid(_ammo, _count))
            self.user().send(self._writer.all_container_items(player.hold))
        except Exception:
            log.exception("could not grant capital ammo")
        new_ship.ship_stats().skill_book = player.skill_book
        new_ship.ship_stats().fold_in_stats()
        new_ship.ship_stats().set_hull(new_ship.ship_stats().stat_or_default(ObjectStat.MaxHullPoints))
        new_ship.ship_stats().set_power(new_ship.ship_stats().stat_or_default(ObjectStat.MaxPowerPoints))
        hangar.berth(new_ship)
        try:
            from rebsgo.world.capitals.capital_ship_cards import send_capital_ship_cards
            cat_proto = self.user().protocol_of(ProtocolID.Catalogue)
            send_capital_ship_cards(self.user(), guid)
            _loadout = _get_ship_loadouts().loadout_for(guid)
            _seen = set()
            for _slot_id, _sys_guid in (_loadout or []):
                if _sys_guid in _seen:
                    continue
                _seen.add(_sys_guid)
                _mod = self._catalogue.card_of(_sys_guid, CardView.ShipSystem)
                for _v in (CardView.ShipSystem, CardView.GUI):
                    _c = self._catalogue.card_of(_sys_guid, _v)
                    if _c is not None:
                        self.user().send(cat_proto.write_card(_c))
                if _mod is not None:
                    for _ab_guid in (_mod.ship_ability_cards or []):
                        for _v in (CardView.ShipAbility, CardView.GUI):
                            _c = self._catalogue.card_of(_ab_guid, _v)
                            if _c is not None:
                                self.user().send(cat_proto.write_card(_c))
            for _ammo in (*self._CAPITAL_DEFAULT_AMMO.values(), *self._CAPITAL_EXTRA_AMMO):
                for _v in (CardView.ShipConsumable, CardView.GUI, CardView.Price):
                    if (_c := self._catalogue.card_of(_ammo, _v)) is not None:
                        self.user().send(cat_proto.write_card(_c))
        except Exception:
            log.exception("could not pre-send capital ship cards")
        self.user().send(self.push_ship_added(new_ship))
        self.user().send(self._writer.ship_slots(new_ship))
        self.user().send(self._writer.ship_info_durability(new_ship))
        try:
            self.activate_ship(capital_slot)
        except Exception:
            log.exception("could not select capital ship as active")
        self._capital_desk().register(
            player.user_id_of(), _time.time() + DURATION_SECONDS, previous_active_ship_id,
            frakcio)
        self._send_capital_galaxy_update(frakcio, CAPITAL_SECTOR.get(frakcio, -1), DURATION_SECONDS)
        log.info("Capital ship %s deployed for %s (%ss)", guid, self.user().user_log(), int(DURATION_SECONDS))

    def update_capital_galaxy_sector(self, sector_id: int) -> None:
        try:
            from rebsgo.world.capitals.capital_roster import CAPITAL_SLOT
            player = self.user().pilot_of()
            active = player.hangar_of().active_ship()
            if active is None or active.server_id != CAPITAL_SLOT:
                return
            hatralevo = self._capital_desk().remaining_seconds(player.user_id_of())
            if hatralevo <= 0:
                return
            self._send_capital_galaxy_update(player.faction, sector_id, hatralevo)
        except Exception:
            log.exception("could not update capital galaxy sector")

    def revoke_capital_ship(self) -> bool:
        from rebsgo.world.capitals.capital_roster import CAPITAL_SLOT
        player = self.user().pilot_of()
        hangar = player.hangar_of()
        if hangar.by_server_id(CAPITAL_SLOT) is None:
            return True
        active = hangar.active_ship()
        flying_capital = (active is not None and active.server_id == CAPITAL_SLOT
                          and not player.location.is_in_room)
        if flying_capital:
            return False
        if active is not None and active.server_id == CAPITAL_SLOT:
            previous_id = self._capital_desk().previous_active_ship(player.user_id_of())
            if (fallback_id := self._capital_fallback_ship_id(previous_id)) is not None:
                self.activate_ship(fallback_id)
        hangar.remove_hangar_ship(CAPITAL_SLOT)
        self.user().send(self.write_remove_ship(CAPITAL_SLOT))
        self._send_capital_galaxy_update(player.faction, -1, 0)
        self._capital_desk().unregister(player.user_id_of())
        log.info("Capital ship revoked for %s", self.user().user_log())
        return True

    def release_capital_ship_after_death(self) -> bool:
        from rebsgo.world.capitals.capital_roster import CAPITAL_SLOT
        player = self.user().pilot_of()
        hangar = player.hangar_of()
        if hangar.by_server_id(CAPITAL_SLOT) is None:
            return False
        active = hangar.active_ship()
        if active is None or active.server_id != CAPITAL_SLOT:
            return False

        previous_id = self._capital_desk().previous_active_ship(player.user_id_of())
        fallback_id = self._capital_fallback_ship_id(previous_id)
        if fallback_id is not None:
            self.activate_ship(fallback_id)
        hangar.remove_hangar_ship(CAPITAL_SLOT)
        self.user().send(self.write_remove_ship(CAPITAL_SLOT))
        self._send_capital_galaxy_update(player.faction, -1, 0)
        self._capital_desk().unregister(player.user_id_of())
        log.info("Destroyed capital ship removed for %s; restored ship slot %s",
                 self.user().user_log(), fallback_id)
        return True

    def _capital_fallback_ship_id(self, preferred_ship_id: int | None = None) -> int | None:
        from rebsgo.world.capitals.capital_roster import CAPITAL_SLOT
        hangar = self.user().pilot_of().hangar_of()
        if preferred_ship_id is not None:
            preferred = hangar.by_server_id(preferred_ship_id)
            if preferred is not None and preferred.server_id != CAPITAL_SLOT:
                return preferred.server_id
        for other in hangar.all_hangar_ships():
            if other.server_id != CAPITAL_SLOT:
                return other.server_id
        return None

    def take_capital_ship(self) -> str:
        from rebsgo.world.capitals.capital_roster import capital_guid_for, CAPITAL_SLOT
        from rebsgo.pilots.state.holdings.walks.storage_walk import StorageWalk
        player = self.user().pilot_of()
        if player.hangar_of().by_server_id(CAPITAL_SLOT) is not None:
            log.info("Capital ship already deployed for %s", self.user().user_log())
            return "already"
        guid = capital_guid_for(player.faction)
        ship_card = self._catalogue.card_of(guid, CardView.Ship)
        price_card = self._catalogue.card_of(guid, CardView.Price)
        if ship_card is None or price_card is None:
            log.error("capital ship cards missing for guid %s", guid)
            return "error"
        if not StorageWalk.enough_held(price_card.buy_price, player.hold, 1):
            log.info("Capital ship: %s cannot afford %s", self.user().user_log(), price_card.buy_price)
            return "poor"
        self.deploy_capital_ship(ship_card, price_card)
        return "ok" if player.hangar_of().by_server_id(CAPITAL_SLOT) is not None else "error"

    def _send_capital_galaxy_update(self, faction, sector_id: int, duration_seconds: float) -> None:
        try:
            import datetime as _dt
            expire = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(seconds=duration_seconds)
            self.ctx.galaxy.update_capital_ship_location(faction, sector_id, expire)
        except Exception:
            log.exception("Could not send capital ship galaxy update")

    def write_remove_ship(self, ship_id: int):
        bw = self.new_message()
        bw.write_uint16(PilotReply.RemoveShip.value)
        bw.write_uint16(ship_id)
        return bw

    def earn_experience(self, exp: int) -> None:
        if self.user() is None:
            log.warning('experience awarded to a pilot who is not here')
            return
        self.user().pilot_of().skill_book.earn_experience(exp)
        notification_protocol = self.user().protocol_of(ProtocolID.Notification)

        self.user().send(notification_protocol.replies.experience_gained(int(exp)))
        self.push_shared_experience()

    def identify_unknown(self, card_guid: int, iterations: int) -> None:
        sablon = augment_template_for(card_guid)
        if not isinstance(sablon, AugmentLootSpec):
            self.user().protocol_of(ProtocolID.Debug).tell_console('nothing implements this yet')
            return

        jussok = []
        for _ in range(iterations):
            for tetel in sablon.loot_entry_infos:
                if self._jar_e_a_tetel(tetel):
                    jussok.append(self._tetel_masolata(tetel))

        atmeneti = Hold(self.user().pilot_of().user_id_of())
        atmeneti.add_ship_items(jussok)
        self.user().protocol_of(ProtocolID.Notification) \
            .hand_out_augments(atmeneti.all_ship_items)

    def _jar_e_a_tetel(self, tetel) -> bool:
        if not self.ctx.rng.passes(tetel.chance):
            return False
        if not tetel.is_in_level_interval(self.user().pilot_of().skill_book.get()):
            return False
        return tetel.open_to_faction(self.user().pilot_of().faction)

    def _tetel_masolata(self, tetel):
        darab = tetel.ship_item
        if not isinstance(darab, CountableItem):
            return darab.copy()
        uj_mennyiseg = self.ctx.rng.wobble(
            darab.count(), tetel.variation_percentage)
        masolat = darab.copy()
        masolat.update_count(uj_mennyiseg)
        return masolat

    def raise_skill(self, keszseg_id: int) -> None:
        player = self.user().pilot_of()
        skill_book = player.skill_book
        skill_book.raise_skill(keszseg_id)

        self.user().send(self._writer.spent_experience(skill_book.spent_experience()))
        self.user().send(self._writer.skills(player.skill_book))

        active_ship = player.hangar_of().active_ship()
        active_ship.ship_stats().skill_book = skill_book

    def clear_skill(self, keszseg_id: int) -> None:
        player = self.user().pilot_of()
        skill_book = player.skill_book
        skill_book.clear_skill(keszseg_id)

        self.user().send(self._writer.spent_experience(skill_book.spent_experience()))
        self.user().send(self._writer.skills(player.skill_book))

        active_ship = player.hangar_of().active_ship()
        active_ship.ship_stats().skill_book = skill_book

    def items_taken_out(self, honnan_tarolo, torlendo_tetelek):
        bw = self.new_message()
        container_type = honnan_tarolo.container_id.container_type
        if container_type == StorageKind.Hold:
            bw.write_msg_type(PilotReply.RemoveHoldItems.value)
        elif container_type == StorageKind.Locker:
            bw.write_msg_type(PilotReply.RemoveLockerItems.value)
        elif container_type == StorageKind.Mail:
            bw.write_msg_type(PilotReply.RemoveMail.value)
        else:
            raise ValueError(f'clearing items out of this container failed: {container_type}')
        bw.write_uint16_collection(torlendo_tetelek)
        return bw

    def activate_ship(self, ship_id: int) -> None:
        player = self.user().pilot_of()
        hangar = player.hangar_of()
        if not player.location.is_in_room:
            log.info('%s picked a ship from outside a station', self.user().user_log())
            return

        if hangar.active_ship().server_id == ship_id:
            return

        old_active_ship = hangar.active_ship()
        hangar.choose_active_ship(ship_id)
        old_subscribers = old_active_ship.ship_stats().subscribers
        active_ship = hangar.active_ship()
        active_ship.ship_stats().fold_in_stats()
        for sub_key, sub_value in list(old_subscribers.items()):
            active_ship.ship_stats().restore_watcher(sub_value)
            send_result_ok = sub_key.flush_property_buffer(sub_value)

        old_subscribers.clear()

        self.user().send(self._writer.active_player_ship(active_ship.server_id))
        self.user().send(self.hangar_ship_stats(active_ship))

        from rebsgo.world.capitals.capital_roster import CAPITAL_SLOT
        if old_active_ship.server_id == CAPITAL_SLOT and active_ship.server_id != CAPITAL_SLOT:
            self._send_capital_galaxy_update(player.faction, -1, 0)
        elif active_ship.server_id == CAPITAL_SLOT:
            hatralevo = self._capital_desk().remaining_seconds(player.user_id_of())
            if hatralevo > 0:
                self._send_capital_galaxy_update(player.faction, player.sector_id, hatralevo)

        if not self._catalogue.map_card.is_base_sector(player.faction, player.location.sector_id):
            self.push_undock_block(self.REPAIR_DOCK_DELAY_TIME_SECONDS)

    def hull_and_power(self, hp: float, power_now: float):
        bw = self.new_message()
        bw.write_msg_type(PilotReply.Stats.value)
        bw.write_length(2)

        bw.write_byte(6)
        bw.write_single(power_now)

        bw.write_byte(7)
        bw.write_single(hp)

        return bw

    def hangar_ship_stats(self, hangar_ship):
        return self._writer.hangar_ship_stats(hangar_ship)

    def _handle_move_item(self, br) -> None:
        player = self.user().pilot_of()
        transfer_request = self._beolvasott_mozgatas(br, player)
        if transfer_request is None:
            return

        from_container = transfer_request.source_container
        to_container = transfer_request.to
        from rebsgo.pilots.state.holdings.walks.walker_source import walker_for
        from rebsgo.pilots.state.holdings.walks.storage_walk import RaktarGond
        utvonal = walker_for(
            from_container.container_id.container_type, self.user(), transfer_request, self.ctx.rng)

        try:
            utvonal.step_into(to_container)
        except RaktarGond as gond:
            log.error('%s moving item: %s', self.user().user_log(), gond)
            self.user().protocol_of(ProtocolID.Debug).tell_console(
                f'{gond} - {player.user_id_of()}')

    @staticmethod
    def _beolvasott_mozgatas(br, player):
        from rebsgo.pilots.state.holdings.move_request import MoveRequest

        transfer_request = MoveRequest(br, player)
        try:
            transfer_request.read_move_item()
        except RuntimeError as allapot_hiba:
            log.exception('the item move request would not read')
            log.error('state gone wrong: %s', allapot_hiba)
            return None
        except OSError as io_hiba:
            log.error('item move fell over: %s', io_hiba)
            return None
        return transfer_request

    def push_items_added(self, container, targyak):
        bw = self.new_message()
        container_type = container.container_id.container_type
        if container_type == StorageKind.Hold:
            bw.write_msg_type(PilotReply.HoldItems.value)
        elif container_type == StorageKind.Locker:
            bw.write_msg_type(PilotReply.LockerItems.value)
        else:
            raise ValueError('no push message exists for that container kind')
        bw.write_desc_collection(targyak)
        return bw

    def push_item_added(self, container, ship_item):
        return self.push_items_added(container, [ship_item])

    def switch_sides(self, arral: bool, cubits_price: float) -> None:
        self._handlers[_ClientMessage.ChangeFaction].switch_sides(arral, cubits_price)

    def push_item_removed(self, honnan_tarolo, *szerver_ids):
        bw = self.new_message()
        container_type = honnan_tarolo.container_id.container_type
        if container_type == StorageKind.Hold:
            bw.write_msg_type(PilotReply.RemoveHoldItems.value)
        elif container_type == StorageKind.Locker:
            bw.write_msg_type(PilotReply.RemoveLockerItems.value)
        else:
            raise ValueError('no removal message exists for that container kind')
        bw.write_uint16_collection(list(szerver_ids))
        return bw

    def push_shared_experience(self) -> None:
        player = self.user().pilot_of()
        skill_book = player.skill_book
        self.user().send(self._writer.experience(skill_book.experience))
        self.user().send(self._writer.spent_experience(skill_book.spent_experience()))
        self.user().send(self.push_experience_gain(skill_book.experience))
        self.user().send(self.player_level(skill_book.experience))

    def push_experience_gain(self, exp: int):
        bw = self.new_message()
        bw.write_msg_type(PilotReply.NormalExperience.value)
        szint = self._level_curve.level_based_on_exp(exp)

        prev_level_experience = self._level_curve.exp_from_level(szint)
        next_level_experience = self._level_curve.exp_from_level(szint + 1)

        bw.write_uint32(prev_level_experience)
        bw.write_uint32(next_level_experience)

        return bw

    def player_level(self, experience: int):
        bw = self.new_message()
        bw.write_msg_type(PilotReply.Level.value)
        szint = self._level_curve.level_based_on_exp(experience)
        bw.write_byte(szint & 0xFF)
        return bw

    def push_durability(self) -> None:
        player = self.user().pilot_of()
        hangar_ships = player.hangar_of().all_hangar_ships()
        for ship in hangar_ships:
            self.user().send(self._writer.ship_info_durability(ship))

    def push_ship_names(self) -> None:
        player = self.user().pilot_of()
        hangar = player.hangar_of()
        for hangar_ship in hangar.all_hangar_ships():
            if len(hangar_ship.name) != 0:
                self.user().send(self.push_ship_name(hangar_ship))

    def push_ship_name(self, hangar_ship):
        bw = self.new_message()
        bw.write_msg_type(PilotReply.ShipName.value)
        bw.write_uint16(hangar_ship.server_id)
        bw.write_string(hangar_ship.name)
        return bw

    def push_sticker_bindings(self) -> None:
        player = self.user().pilot_of()
        for ship in player.hangar_of().all_hangar_ships():
            self.user().send(self._writer.ship_sticker_binding(ship))

    def sticker_removed(self, hangar_ship):
        bw = self.new_message()
        bw.write_msg_type(PilotReply.RemoveStickers.value)
        bw.write_uint16(hangar_ship.server_id)

        stickers_to_remove = hangar_ship.stickers
        uint16_list_object_point_hashes = [s.object_point_hash for s in stickers_to_remove]
        bw.write_uint16_collection(uint16_list_object_point_hashes)
        return bw

    def push_ship_slots(self) -> None:
        player = self.user().pilot_of()
        for ship in player.hangar_of().all_hangar_ships():
            self.user().send(self._writer.ship_slots(ship))

    def push_slot_stats(self, slot_id: int, object_stats):
        bw = self.new_message()
        bw.write_msg_type(PilotReply.Stats.value)

        bw.write_length(len(object_stats.all_stats))

        for stat_key, stat_value in object_stats.all_stats.items():
            bw.write_byte(12)
            bw.write_byte(slot_id & 0xFF)
            bw.write_uint16(stat_key.value)
            bw.write_single(stat_value)

        return bw

    def flush_property_buffer(self, property_buffer) -> bool:
        if self.user() is None:
            log.error('pending changes have nobody to go to')
            return False
        bw = self._writer.space_property_buffer(property_buffer)
        return self.user().send(bw)

    def user_id(self) -> int:
        return self.user().pilot_of().user_id_of()

    def push_hangar(self) -> None:
        player = self.user().pilot_of()
        hangar_ships = player.hangar_of().all_hangar_ships()
        for hangar_ship in hangar_ships:
            self.user().send(self.push_ship_added(hangar_ship))

    def push_ship_added(self, hangar_ship):
        ship_id, ship_guid = hangar_ship.server_id, hangar_ship.card_guid_of()
        if min(ship_id, ship_guid) < 0:
            raise ValueError(f'hangar ship without a berth or card: {ship_id}/{ship_guid}')
        bw = self.new_message()
        bw.write_uint16(PilotReply.AddShip.value)
        bw.write_uint16(ship_id)
        bw.write_guid(ship_guid)
        return bw

    def push_capability_reset(self, capability):
        bw = self.new_message()
        bw.write_msg_type(PilotReply.Capability.value)

        bw.write_byte(capability.value)
        bw.write_byte(0)
        return bw

    def push_capability_value(self, capability, idopont):
        bw = self.new_message()
        bw.write_msg_type(PilotReply.Capability.value)

        bw.write_byte(capability.value)
        bw.write_byte(2)
        bw.write_date_time(idopont)
        return bw

    def push_name_verdict(self, costs_nothing: bool):
        bw = self.new_message()
        if costs_nothing:
            bw.write_uint16(PilotReply.NameAvailable.value)
        else:
            bw.write_uint16(PilotReply.NameNotAvailable.value)
        return bw

    def announce_character(self) -> None:
        if self.user() is None:
            log.error('the pilot whose character was asked for is not here')
            return
        player = self.user().pilot_of()
        log.info("send_character DIAG user_id=%s name=%r faction=%r active_ship=%s ship_count=%s",
                 player.user_id_of(), player.name, player.faction,
                 player.hangar_of().flying_something(),
                 len(player.hangar_of().all_hangar_ships()))
        self.user().send(self._writer.reset())
        self.user().send(self._writer.write_id(player.user_id_of()))
        self.user().send(self._writer.name(player.name))
        self.user().send(self._writer.avatar_description(player.avatar_description.get()))
        self.user().send(self._writer.faction(player.faction))
        self.push_shared_experience()
        self.user().send(self._writer.skills(player.skill_book))
        self.push_hangar()
        self.push_durability()
        self.push_ship_slots()
        self.push_ship_names()
        self.push_sticker_bindings()
        self.user().send(self._writer.mail_box(player.mail_box))
        if player.hangar_of().flying_something():
            self.user().send(self._writer.active_player_ship(player.hangar_of().active_ship().server_id))
            self.user().send(self.hangar_ship_stats(player.hangar_of().active_ship()))

        end_time = _dt.datetime(2024, 6, 1, 0, 0, 0, tzinfo=_UTC)

        if (not self.user().pilot_of().factors.boosted_by(BoostSource.Holiday)
            and _dt.datetime.now(_UTC) < end_time):
            self.user().pilot_of().factors.take_boost(
                Boost.ending_at(BoostKind.Loot, BoostSource.Holiday, 50, end_time))
            self.user().pilot_of().factors.take_boost(
                Boost.ending_at(BoostKind.Experience, BoostSource.Holiday, 10.0, end_time))
            self.user().pilot_of().factors.take_boost(
                Boost.ending_at(BoostKind.AsteroidYield, BoostSource.Holiday, 30.0, end_time))
        self.user().send(self._writer.factors(player.factors))

        try:
            from rebsgo.services import Services
            from rebsgo.pilots.standings.medal_desk import MedalDesk

            player.player_medals.set(Services.get(MedalDesk).ermek(player.user_id_of()))
        except Exception:
            log.exception("the medals would not be seeded for the arriving pilot")

        player.tally_desk.wake_all()
        self.user().send(self._writer.counters(player.tally_desk.counters()))
        self.user().send(self._writer.all_container_items(player.hold))
        self.user().send(self._writer.all_container_items(player.locker))
        self.user().send(self._writer.missions(player.tally_desk.mission_book))
        setting_protocol = self.user().protocol_of(ProtocolID.Setting)
        setting_protocol.push_settings()
        community_protocol = self.user().protocol_of(ProtocolID.Community)
        fetched_guild = self._guild_registry.guild_of_player_id(player.user_id_of())
        if fetched_guild is not None:
            self.user().pilot_of().join_guild(fetched_guild)
            self._reseat_in_guild(fetched_guild, player)

        if (guild := self.user().pilot_of().guild()) is not None:
            self.user().send(community_protocol.replies.guild_info(ClanInfoReply(guild)))
        if (party := self.user().pilot_of().party()) is not None:
            self.user().send(community_protocol.replies.party(party))
        scene_protocol = self.user().protocol_of(ProtocolID.Scene)

        scene_protocol.push_scene_change()

        self._announce_presence(player)

    def _announce_presence(self, player) -> None:
        from rebsgo.runtime.presence import PresenceCrier
        PresenceCrier(self._pilot_roster).arrived(player)

    @staticmethod
    def _reseat_in_guild(guild, player) -> None:
        korabbi = guild.guild_member_info_of(player.user_id_of())
        if korabbi is None:
            return
        guild.enrol(player, korabbi.player_role)
