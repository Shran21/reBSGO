# github.com/Shran21
from __future__ import annotations

import logging

from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.protocol_book_replies import replies_for
from rebsgo.world.sectors.spoils.spoils import CountableBonusKind
from rebsgo.world.sectors.spoils.drops import SpoilsSource
from rebsgo.world.sectors.spoils.loot_share_maths import associated_loot_users, for_level_and_faction, for_level_and_factions, roll_from_entries, scale_count_by_action, scale_count_by_party, settle_pvp, weigh_items, weigh_one_item
from rebsgo.vocabulary.pilot import ResourceKind
from rebsgo.vocabulary.world import ObjectKind
from rebsgo.gamedata.cards.misc_cards import TallyCardKind
from rebsgo.gamedata.ship_parts.parts import CountableItem

log = logging.getLogger(__name__)


class LootSplit:
    def __init__(self, itt_levok, dice, pilot_wire, tick, tally_giver,
                 szektor_terv, merok, server_settings, pilot_roster, pvp_kill_history):
        self._sector_users = itt_levok
        self._dice = dice
        self._pilot_wire = pilot_wire
        self._tick = tick
        self._tally_giver = tally_giver
        self._sector_blueprint = szektor_terv
        self._merok = merok
        self._server_settings = server_settings
        self._pilot_roster = pilot_roster
        self._pvp_kill_history = pvp_kill_history

    def _loot_to_user(self, pilota_zsakmanya, elesett_objektum) -> None:
        from rebsgo.pilots.state.holdings.walks.storage_walk import deliver_item

        user = pilota_zsakmanya.user()
        exp = pilota_zsakmanya.experience
        items = pilota_zsakmanya.items()

        player = user.pilot_of()
        if exp > 0:
            player_protocol = user.protocol_of(ProtocolID.Pilot)
            player_protocol.earn_experience(exp)

        converted_countables_to_add = []
        for tetel in items:
            if not isinstance(tetel.item_countable, CountableItem):
                continue
            token_cap = player.merits_cap_farmed
            if tetel.item_countable.card_guid_of() == token_cap.guid:
                from rebsgo.vocabulary.pilot import BoostKind
                merit_mult = player.factors.multiplier_for(BoostKind.MeritIncome)
                if merit_mult > 1:
                    tetel.item_countable.update_count(int(tetel.item_countable.count() * merit_mult))
            requires_update = token_cap.grow_if_ore(
                tetel.item_countable.card_guid_of(), int(tetel.item_countable.count()))
            if requires_update:
                delta = tetel.item_countable.count() - token_cap.last_farmed_value
                if delta > 0:
                    converted_countables_to_add.append(CountableItem.from_guid(ResourceKind.Uranium.guid, delta))
                tetel.item_countable.update_count(token_cap.last_farmed_value)
                user.send(self._pilot_wire.merits_cap(token_cap))
        tmp_converted_items = [CountableBonusKind(ic) for ic in converted_countables_to_add]
        items.extend(tmp_converted_items)

        notification_protocol_write_only = replies_for(ProtocolID.Notification)
        bw_notification = notification_protocol_write_only.loot_message(items, pilota_zsakmanya.special_action)
        user.send(bw_notification)
        self._tally_giver.pilot_downed(user, elesett_objektum, pilota_zsakmanya.special_action)

        entity_type = elesett_objektum.space_entity_type
        if entity_type == ObjectKind.Pilot:
            loot_source = SpoilsSource.PVP
        elif entity_type == ObjectKind.Asteroid:
            loot_source = SpoilsSource.ASTEROID
        else:
            loot_source = SpoilsSource.PVE
            if items:
                self._tally_giver.debris_looted(user)

        for tetel in items:
            ship_item = tetel.item_countable
            if not isinstance(ship_item, CountableItem):
                deliver_item(user, ship_item, player.hold)
                continue
            if elesett_objektum.space_entity_type == ObjectKind.Asteroid:
                self._tally_giver.ore_taken(user, ship_item)
            deliver_item(user, ship_item, player.hold)
            self._merok.resource_earned(
                self._sector_blueprint.sector_desc.sector_id,
                ship_item.card_guid_of(),
                user.pilot_of().faction,
                ship_item.count(),
                loot_source)

        log.info('%s took %s from %s (%s), xp=%s',
                 user.user_log_simple,
                 ", ".join(f"{t.item_countable.card_guid_of()}"
                           f"{'x' + str(int(t.item_countable.count())) if isinstance(t.item_countable, CountableItem) else ''}"
                           for t in items) or 'nothing',
                 elesett_objektum.space_entity_type, loot_source, exp)

    def _loot_to_users(self, pilota_zsakmanyai, elesett_objektum) -> None:
        for user_loot in pilota_zsakmanyai:
            self._loot_to_user(user_loot, elesett_objektum)

    def ore_taken_out(self, user, item_countable) -> None:
        from rebsgo.pilots.state.holdings.walks.storage_walk import deliver_item

        player = user.pilot_of()

        notification_protocol = replies_for(ProtocolID.Notification)
        bw_mined_ore = notification_protocol.ore_taken_out(item_countable)
        self._tally_giver.ore_taken_out(user, item_countable)
        player.tally_desk.bump_counter(
            TallyCardKind.mining_ships_income,
            self._sector_blueprint.sector_cards().sector_card.card_guid_of(),
            item_countable.count())
        user.send(bw_mined_ore)

        self._merok.resource_earned(
            self._sector_blueprint.sector_desc.sector_id,
            item_countable.card_guid_of(),
            player.faction,
            item_countable.count(),
            SpoilsSource.PLANETOID_MINING)
        deliver_item(user, item_countable, player.hold)

    def npc_spoils(self, zsakmany_gazdaja, departed_object, sebzes_elozmeny, loot) -> None:
        if departed_object.is_player():
            log.error("Removed pve WorldObject was player!")
            return

        for loot_template in loot.loot_template_lst():
            rolled_items = roll_from_entries(loot_template, self._dice)

            users_of_interest = associated_loot_users(
                loot_template, zsakmany_gazdaja, departed_object, sebzes_elozmeny, self._sector_users)

            user_items = for_level_and_factions(
                users_of_interest, rolled_items, loot_template.experience)

            if departed_object.space_entity_type != ObjectKind.Outpost:
                user_items = scale_count_by_party(user_items, len(users_of_interest))
            else:
                self._tally_giver.outpost_down(users_of_interest)

            user_loots = weigh_items(user_items)
            self._loot_to_users(user_loots, departed_object)

    def pilot_spoils(self, pvp_zarolas, elpusztult, loot) -> None:
        for loot_template in loot.loot_template_lst():
            rolled_result = roll_from_entries(loot_template, self._dice)

            pvp_results = settle_pvp(
                self._sector_users, self._pilot_roster, pvp_zarolas, elpusztult, rolled_result,
                loot_template.experience, self._tick, self._server_settings, self._pvp_kill_history)

            filtered_pvp_results = for_level_and_factions(pvp_results)

            updated_sizes = scale_count_by_action(filtered_pvp_results)

            user_loots = weigh_items(updated_sizes)

            self._loot_to_users(user_loots, elpusztult)

    def outpost_spoils(self, torolt_op, loot, sebzes_elozmeny) -> None:
        self.npc_spoils(None, torolt_op, sebzes_elozmeny, loot)

    def cargo_loot(self, user, cargo_object, loot) -> None:
        from rebsgo.vocabulary.combat import SpecialMove

        for loot_template in loot.loot_template_lst():
            rolled_items = roll_from_entries(loot_template, self._dice)
            user_items = for_level_and_faction(
                user, rolled_items, loot_template.experience, [SpecialMove.None_])
            user_loot = weigh_one_item(user_items)
            self._loot_to_user(user_loot, cargo_object)
