# github.com/Shran21
from __future__ import annotations

import logging

from rebsgo import journal
from rebsgo.services import Services
from rebsgo.world.sectors.harm.damage_line import DamageLine
from rebsgo.vocabulary.pilot import ServerRoles, Faction
from rebsgo.vocabulary.world import DepartureCause, ObjectKind
from rebsgo.geometry.maths.maths import Maths
from rebsgo.gamedata.cards.card_view import CardView
from rebsgo.gamedata.library import Catalogue
from rebsgo.gamedata.cards.misc_cards import TallyCardKind
from rebsgo.gamedata.reading import MissileKind, ObjectStat
from rebsgo.helpers.floats import f32

log = logging.getLogger(__name__)


class DamageBook:
    def __init__(self, ctx, damage_roll, share_book, takarito, damage_log,
                 tartossag_modosito, space_replies):
        self._ctx = ctx
        self._damage_roll = damage_roll
        self._share_book = share_book
        self._remover = takarito
        self._damage_log = damage_log
        self._damage_durability_modifier = tartossag_modosito
        self._space_replies = space_replies
        self._sector_cards = ctx.blueprint().sector_cards()
        self._damage_watchers = []

    def watch_with(self, watcher) -> None:
        self._damage_watchers.append(watcher)

    def hurt(self, sebzes_sor) -> None:
        damage = sebzes_sor.damage

        celpont = sebzes_sor.to
        if celpont.is_player():
            target_user = self._ctx.users().user(celpont.pilot_id())
            if (target_user is not None
                and target_user.pilot_of().bgo_admin_roles.wears_role(ServerRoles.GodMode)):
                return

        if (removing_cause := sebzes_sor.to.removal_cause_of()) is not None:
            log.error("in deal damage, object to kill is already removed, obj_type=%s, old_removing_cause=%s",
                      sebzes_sor.to.space_entity_type, removing_cause)

        to_stats = sebzes_sor.to.space_subscribe_info()
        damage_dealt_cleaned = damage
        was_kill_shot = False

        target_hp = to_stats.hp
        new_hp_dirty = f32(target_hp - damage)
        if new_hp_dirty < 0:
            damage_dealt_cleaned = Maths.max(target_hp, 0.0)
            if target_hp < 0:
                journal.eloszor(
                    log, "negative-hull",
                    "target was already below zero hull: type=%s object=%s hp=%s damage=%s",
                    sebzes_sor.to.space_entity_type, sebzes_sor.to.id_in_space(),
                    target_hp, damage)

        to_stats.set_hull(Maths.max(new_hp_dirty, 0.0))
        if sebzes_sor.energy_drain > 0.0:
            to_stats.set_power(Maths.max(to_stats.pp - sebzes_sor.energy_drain, 0))
        if to_stats.hp == 0.0:
            self._remover.note_removal_cause(sebzes_sor.to, DepartureCause.Death, sebzes_sor.from_)
            to_stats.set_power(0)
            was_kill_shot = True

        new_dmg_record = DamageLine.of_cleaned(sebzes_sor, damage_dealt_cleaned, was_kill_shot)
        self._damage_log.refresh_damage(new_dmg_record)
        self._damage_durability_modifier.took_a_hit(new_dmg_record)
        for watcher in self._damage_watchers:
            watcher.damage_landed(new_dmg_record)
        self._report_damage_to(new_dmg_record)

    def _report_damage_to(self, sebzes_sor) -> None:
        tamado, celpont = sebzes_sor.from_, sebzes_sor.to

        if tamado.is_player():
            user = self._ctx.users().user(tamado.pilot_id())
            if user is not None:
                self._combat_report(user, sebzes_sor, True, celpont,
                                    TallyCardKind.damage_dealt,
                                    TallyCardKind.outposts_damage_dealt)
                try:
                    self._share_book.update_claim(sebzes_sor, user)
                except Exception as baj:
                    log.error('loot claim refresh fell over', exc_info=baj)

        if celpont.is_player():
            user = self._ctx.users().user(celpont)
            if user is not None:
                self._combat_report(user, sebzes_sor, False, tamado,
                                    TallyCardKind.took_a_hit,
                                    TallyCardKind.outposts_damage_received)

        if celpont.faction != Faction.Neutral:
            most = self._ctx.tick().time_stamp()
            tamado.space_subscribe_info().note_combat_moment(most)
            celpont.space_subscribe_info().note_combat_moment(most)

    def _combat_report(self, user, sebzes_sor, sajat_lovese: bool, masik,
                       sajat_szamlalo, poszt_szamlalo) -> None:
        szektor = self._sector_cards.sector_card.card_guid_of()
        user.send(self._space_replies.combat_info(
            sajat_lovese, masik.id_in_space(), sebzes_sor.damage,
            sebzes_sor.to.is_removed(), sebzes_sor.is_critical))
        szamlalok = user.pilot_of().tally_desk
        szamlalok.bump_counter(sajat_szamlalo, szektor, sebzes_sor.damage)
        if masik.space_entity_type == ObjectKind.Outpost:
            szamlalok.bump_counter(poszt_szamlalo, szektor, sebzes_sor.damage)

    def hurt_by_asteroid(self, asteroid, to) -> None:
        valasz = self._damage_roll.damage_of_collision(asteroid, to)
        self.hurt(valasz)

    def hurt_by_missile(self, missile, to) -> None:
        missile_stats = missile.space_subscribe_info()
        if not self._is_aoe_missile(missile, missile_stats):
            valasz = self._damage_roll.damage_of_missile(missile, to)
            self.hurt(valasz)
            return

        owner = missile.owner_object
        excluded = set()
        dropoff = missile_stats.stat_or_default(ObjectStat.AoeDropoffIndex, 1)

        def _deal_direct(ship) -> None:
            if ship is None or ship.is_removed():
                return
            if not ship.faction.hostile_to(owner.faction):
                return
            self.hurt(self._damage_roll.damage_of_missile(missile, ship))
            excluded.add(ship)

        _deal_direct(to)

        if self._is_nuclear_missile(missile):
            launched_on = missile.missile_launched_on_object
            if launched_on is not None and launched_on != to:
                _deal_direct(launched_on)

        splash_records = self._damage_roll.damage_of_torpedo(
            missile, self._ctx.space_objects(), dropoff,
            exclude_targets=excluded)
        for damage_record in splash_records:
            self.hurt(damage_record)

    def _is_nuclear_missile(self, missile) -> bool:
        guid = missile.owner_card.card_guid_of()
        kartya = Services.get(Catalogue).card_of(guid, CardView.Missile)
        return kartya is not None and kartya.missile_type == MissileKind.Nuke

    def _is_aoe_missile(self, missile, missile_stats) -> bool:
        if missile_stats.holds_stat(ObjectStat.DrainLow):
            return True
        guid = missile.owner_card.card_guid_of()
        kartya = Services.get(Catalogue).card_of(guid, CardView.Missile)
        return kartya is not None and kartya.missile_type == MissileKind.Nuke

    def deal_damage_from_mine(self, mine) -> None:
        damage_records = self._damage_roll.calculate_damage_from_mine(mine, self._ctx.space_objects())
        for damage_record in damage_records:
            self.hurt(damage_record)

    def hurt_by_ability(self, from_, to, ability) -> None:
        valasz = self._damage_roll.damage_for(from_, to, ability)
        self.hurt(valasz)

    def hurt_by_mining(self, caster, target, ability) -> None:
        valasz = self._damage_roll.damage_of_mining(caster, target, ability)
        self.hurt(valasz)
