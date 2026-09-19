# github.com/Shran21
from __future__ import annotations

import logging
import math

from rebsgo.protocol.debug.debug_replies import DebugReplies
from rebsgo.world.sectors.spoils.spoils import CountableBonusKind, CountableLootEntry, DuelOutcome, PilotBelongings, PilotLoot
from rebsgo.vocabulary.pilot import BoostKind, DropBonusKind
from rebsgo.vocabulary.world import PlaceKind, ObjectKind
from rebsgo.vocabulary.combat import SpecialMove
from rebsgo.gamedata.loot_tables import LootDamageRadiusSpec, LootSpecKind
from rebsgo.gamedata.ship_parts.parts import CountableItem
from rebsgo.gamedata.reading import ObjectStat
from rebsgo.helpers.floats import f32

log = logging.getLogger(__name__)


def settle_pvp(itt_levok, pilot_roster, pvp_zarolas, elpusztult, kisorsoltak,
               experience, tick, server_settings, pvp_kill_history):
    claim_obj = pvp_zarolas.claim_object()
    if claim_obj is None:
        return []
    pvp_results = []

    max_hp = elpusztult.space_subscribe_info().stat(ObjectStat.MaxHullPoints)

    if (player := itt_levok.user(claim_obj)) is not None:
        pvp_results.append(DuelOutcome(player, kisorsoltak, experience, SpecialMove.AssistCountingAsKill))

    kill_shot = pvp_zarolas.kill_shot_object
    if kill_shot is not None:
        if kill_shot.dealer != claim_obj:
            damage_high_enough = f32(max_hp * pvp_zarolas.minimum_percentage_damage) < kill_shot.damage_so_far
            if (kill_shot_user := itt_levok.user(kill_shot.dealer)) is not None:
                if damage_high_enough:
                    pvp_results.append(DuelOutcome(kill_shot_user, kisorsoltak, experience, SpecialMove.Killer))

    sorted_by_dmg = pvp_zarolas.sorted_by_dmg
    for assist_object in sorted_by_dmg:
        assisting_dealer = assist_object.dealer
        if assisting_dealer == claim_obj:
            continue

        if kill_shot is not None:
            kill_shot_dealer = kill_shot.dealer
            if kill_shot_dealer == assisting_dealer:
                continue
        damage_high_enough = f32(max_hp * pvp_zarolas.minimum_percentage_damage) < assist_object.damage_so_far
        if damage_high_enough:
            time_stamp_is_invalid = (assist_object.last_time + pvp_zarolas.claim_time_until_free) < tick.time_stamp()
            if time_stamp_is_invalid:
                continue
            if (assisting_usr := itt_levok.user(assist_object.dealer)) is not None:
                pvp_results.append(DuelOutcome(assisting_usr, kisorsoltak, experience, SpecialMove.Assist))

    dealer_tallies = pvp_zarolas.damage_dealers(lambda accu: accu.dealer.is_player())
    for damage_so_far in dealer_tallies:
        modifier_dealer = damage_so_far.dealer
        opd_modifier_user = itt_levok.user(modifier_dealer)

        dmg_buffs = damage_so_far.dmg_based_on_buffs
        dmg_debuffs = damage_so_far.dmg_based_on_debuffs
        min_dmg_needed = f32(max_hp * f32(pvp_zarolas.minimum_percentage_damage * 2))

        if dmg_buffs > min_dmg_needed and opd_modifier_user is not None:
            mar_nyertes = next((r for r in pvp_results if r.user() == opd_modifier_user), None)
            if mar_nyertes is not None:
                mar_nyertes.special_actions.append(SpecialMove.Buffer)
            else:
                pvp_results.append(DuelOutcome(opd_modifier_user, kisorsoltak, experience, SpecialMove.Buffer))
        if dmg_debuffs > min_dmg_needed and opd_modifier_user is not None:
            mar_nyertes = next((r for r in pvp_results if r.user() == opd_modifier_user), None)
            if mar_nyertes is not None:
                mar_nyertes.special_actions.append(SpecialMove.Debuffer)
            else:
                pvp_results.append(DuelOutcome(opd_modifier_user, kisorsoltak, experience, SpecialMove.Debuffer))

    _bosszut_es_megmentest_oszt(pvp_results, elpusztult, pilot_roster, pvp_kill_history)

    dead_user = pilot_roster.by_id(elpusztult.pilot_id())
    log.info('dead pilot presence=%s', dead_user is not None)
    if dead_user is not None:

        for pvp_result in pvp_results:
            if pvp_result.user().same_address(dead_user):
                log.warning("pvp kill, same ip, death_user_log=%s, kill_user_log=%s",
                            dead_user.user_log(), pvp_result.user().user_log())
                if server_settings.starter_params.testing_mode:
                    pvp_message_bw = DebugReplies().message("párbaj-eredmény azonos címről")
                    pvp_result.user().send(pvp_message_bw)

            if pvp_result.holds_action(SpecialMove.Killer, SpecialMove.AssistCountingAsKill):
                pvp_kill_history.note_pvp_kill(
                    pvp_result.user().pilot_of().user_id_of(), pvp_result.user().pilot_of().name,
                    dead_user.pilot_of().user_id_of(), dead_user.pilot_of().name)

    return pvp_results


def _bosszut_es_megmentest_oszt(pvp_results, elpusztult, pilot_roster, pvp_kill_history) -> None:
    if pvp_kill_history is None:
        return
    try:
        aldozat_id = elpusztult.pilot_id()
    except Exception:
        return
    tamadottak = pvp_kill_history.attacked_lately(aldozat_id)

    for pvp_result in pvp_results:
        if not pvp_result.holds_action(SpecialMove.Killer, SpecialMove.AssistCountingAsKill):
            continue
        pilota = pvp_result.user().pilot_of()
        gyilkos_id = pilota.user_id_of()

        if pvp_kill_history.revenge_kill(gyilkos_id, aldozat_id):
            pvp_result.special_actions.append(SpecialMove.Avenger)

        for megmentett_id in tamadottak:
            if megmentett_id == gyilkos_id:
                continue
            tars = pilot_roster.by_id(megmentett_id) if pilot_roster is not None else None
            if tars is not None and tars.pilot_of().faction == pilota.faction:
                pvp_result.special_actions.append(SpecialMove.Saviour)
                break


def users_from_party_same_sector(user):
    party = user.pilot_of().party()
    if party is None:
        if user.pilot_of().location.game_location == PlaceKind.Space:
            return [user]
        else:
            return []

    return [tag for tag in party.members()
            if tag.pilot_of().location.game_location == PlaceKind.Space
            and tag.pilot_of().location.sector_id == user.pilot_of().sector_id]


def weigh_items(pilota_targyai):
    user_loots = []
    for user_item in pilota_targyai:
        user_loots.append(weigh_one_item(user_item))
    return user_loots


def weigh_one_item(pilota_targyai):
    factors = pilota_targyai.user().pilot_of().factors
    loot_mult = factors.multiplier_for(BoostKind.Loot)
    xp_mult = factors.multiplier_for(BoostKind.Experience)

    result_xp = math.floor(pilota_targyai.exp() * xp_mult)

    item_countable_bonus_types = []
    for item_countable in pilota_targyai.item_countables:
        bonus_kind = CountableBonusKind(item_countable, {})
        if loot_mult > 1 and isinstance(item_countable, CountableItem):
            result_count = math.floor(item_countable.count() * loot_mult)
            increased_by = result_count - item_countable.count()
            item_countable.update_count(result_count)

            bonus_kind.loot_bonus_type_long_map[DropBonusKind.Booster] = increased_by

        item_countable_bonus_types.append(bonus_kind)
    return PilotLoot(pilota_targyai.user(), result_xp, item_countable_bonus_types, pilota_targyai.special_actions)


def associated_loot_users(zsakmany_sablon, user, elesett, sebzes_elozmeny, itt_levok):
    associated_users = set()

    loot_type = zsakmany_sablon.type
    if loot_type == LootSpecKind.Damage:
        members_filtered = users_from_party_same_sector(user)
        filtered_for_global = [tag for tag in members_filtered
                               if zsakmany_sablon.within_global_band(tag.pilot_of().skill_book.get())]
        associated_users.update(filtered_for_global)
    elif loot_type == LootSpecKind.RadiusDamage:
        if not isinstance(zsakmany_sablon, LootDamageRadiusSpec):
            raise RuntimeError('radial damage on a kind that takes none')
        loot_damage_radius_template = zsakmany_sablon
        all_damage_dealers = sebzes_elozmeny.by_damage_dealt
        highest_dmg_dealer = sebzes_elozmeny.highest_damage_dealer()
        if highest_dmg_dealer is None:
            return associated_users
        faction_highest_dealer = highest_dmg_dealer.dealer.faction
        for all_damage_dealer in all_damage_dealers:
            if all_damage_dealer.dealer.space_entity_type == ObjectKind.Outpost:
                associated_users.clear()
                break

            if all_damage_dealer.dealer.is_player():
                dealer_user = itt_levok.user(all_damage_dealer.dealer)
                if (dealer_user is not None
                    and loot_damage_radius_template.radius_of() >= elesett.mover_of().position_of().distance_(all_damage_dealer.dealer.mover_of().position_of())
                    and loot_damage_radius_template.min_damage <= all_damage_dealer.damage_so_far
                    and all_damage_dealer.dealer.faction == faction_highest_dealer):
                    associated_users.add(dealer_user)

    return associated_users


def scale_count_by_party(user_items_list, group_size: int):
    return_lst = []
    for user_items in user_items_list:
        for item_countable in user_items.item_countables:
            if not isinstance(item_countable, CountableItem):
                continue
            new_count = _ceil_loot_count(item_countable.count() / group_size)
            item_countable.update_count(new_count)
        xp_div = _ceil_loot_count(user_items.exp() / group_size)
        return_lst.append(PilotBelongings(user_items.user(), user_items.item_countables, xp_div))
    return return_lst


def scale_count_by_action(user_items_list):
    return [_megszorozva(user_items, user_items.highest_special_action().loot_multiplier)
            for user_items in user_items_list]


def _megszorozva(pilota_targyai, szorzo: float):
    tetelek = []
    for eredeti in pilota_targyai.item_countables:
        darab = eredeti.copy()
        if isinstance(darab, CountableItem):
            darab.update_count(_ceil_loot_count(eredeti.count() * szorzo))
        tetelek.append(darab)
    return PilotBelongings(pilota_targyai.user(), tetelek,
                           _ceil_loot_count(pilota_targyai.exp() * szorzo),
                           pilota_targyai.special_actions)


def _ceil_loot_count(uj_darab: float) -> int:
    return int(math.ceil(max(uj_darab, 1)))


def for_level_and_factions(arg, kisorsoltak=None, exp=None):
    if kisorsoltak is None:
        pvp_results = arg
        result_items_list = []
        for pvp_result in pvp_results:
            filtered = for_level_and_faction(
                pvp_result.user(), pvp_result.rolled_items, pvp_result.experience, pvp_result.special_actions)
            result_items_list.append(filtered)
        return result_items_list
    users_of_interest = arg
    user_items_list = []
    for user in users_of_interest:
        user_items_list.append(for_level_and_faction(
            user, kisorsoltak, exp, [SpecialMove.None_]))
    return user_items_list


def for_level_and_faction(user, kisorsoltak, exp, kulon_gombok):
    tmp_items = []
    for rolled_item in kisorsoltak:
        level_okay = rolled_item.entry_details.is_in_level_interval(user.pilot_of().skill_book.get())
        faction_okay = rolled_item.entry_details.open_to_faction(user.pilot_of().faction)

        if level_okay and faction_okay:
            tmp_items.append(rolled_item.item_countable.copy())
    return PilotBelongings(user, tmp_items, exp, kulon_gombok)


def roll_from_entries(zsakmany_sablon, dice):
    item_countables = []

    is_in_overall_chance = dice.passes(zsakmany_sablon.chance)
    if not is_in_overall_chance:
        return []
    for entry_details in zsakmany_sablon.loot_entry_infos:
        roll_successfully = dice.passes(entry_details.chance)
        if roll_successfully:
            if isinstance(entry_details.ship_item, CountableItem):
                countable = entry_details.ship_item
                rolled_count = dice.wobble(countable.count(), entry_details.variation_percentage)
                new_countable = countable.copy()
                new_countable.update_count(rolled_count)
                item_countables.append(CountableLootEntry(new_countable, entry_details))
            elif entry_details.ship_item is not None:
                item_countables.append(CountableLootEntry(entry_details.ship_item.copy(), entry_details))

    return item_countables
