# github.com/Shran21
from __future__ import annotations

from contextlib import suppress

import datetime as _dt
import logging

from rebsgo.wire.bytes.stamp import Stamp
from rebsgo.store.records.tally_sheet import TallySheet
from rebsgo.store.records.records import Records
from rebsgo.pilots.state.default_model_paint_updates import normalize_default_model_paints
from rebsgo.pilots.state.berthed_ship import HangarShip
from rebsgo.pilots.state.pilot import Pilot
from rebsgo.pilots.state.tallies import AssignmentLog
from rebsgo.pilots.state.options.input_actions import Action
from rebsgo.pilots.state.options.key_binding import KeyBinding
from rebsgo.pilots.state.options.option import Option
from rebsgo.pilots.state.options.option_kind import OptionKind
from rebsgo.pilots.state.options.kinds.option_kinds import OptionFlag, OptionByte, OptionDecimal, OptionNumber, OptionHelpScreen
from rebsgo.pilots.state.permissions import HelpScreenKind
from rebsgo.pilots.state.boosts.boost import Boost
from rebsgo.store.db_rows import PlaceRow
from rebsgo.store.sqlite_util import read_moment
from rebsgo.vocabulary.pilot import AvatarItem, Faction, BoostSource, BoostKind
from rebsgo.vocabulary.world import PlaceKind
from rebsgo.gamedata.ship_parts.parts import ShipSystem
from rebsgo.helpers.locks import ReadWriteLock, Zarhato
from rebsgo.helpers.rolling_latency_stats import (
    ENABLED as GUARDRAILS_ENABLED,
    DB_BULK_WRITE_WARN_MS,
    DB_PLAYER_FETCH_WARN_MS,
    DB_PLAYER_WRITE_WARN_MS,
    elapsed_ms,
    now_ms,
    warn_if_slow,
)

log = logging.getLogger(__name__)

_TOKEN_GUID = 130920111


def _now_utc():
    return _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)


class SqliteRecords(Records, Zarhato):
    def __init__(self, data_source, server_settings, kuldetes_frissito, catalogue,
                 sqlite_hangar, containers, sqlite_missions, guild_processor):
        self._data_source = data_source
        self._mission_updater = kuldetes_frissito
        self._server_settings = server_settings
        self._galaxy_map_card = catalogue.map_card
        self._read_write_lock = ReadWriteLock()
        self._containers = containers
        self._hangars = sqlite_hangar
        self._sqlite_missions = sqlite_missions
        self._sqlite_guild_processor = guild_processor

    @property
    def iras_alatt(self):
        return self._irva

    def stored_avatar(self, user_id: int):
        return None

    def stored_pilot(self, user_id: int):
        kezdet = now_ms() if GUARDRAILS_ENABLED else 0.0
        try:
            with self._olvasva:
                return self._pilota_beolvasasa(user_id)
        finally:
            if GUARDRAILS_ENABLED:
                warn_if_slow(
                    log,
                    elapsed_ms(kezdet),
                    DB_PLAYER_FETCH_WARN_MS,
                    "Slow player fetch user_id=%s",
                    user_id,
                )

    def _pilota_beolvasasa(self, user_id: int):
        conn = None
        try:
            conn = self._data_source.connection()
            player = Pilot(user_id, self._server_settings, AssignmentLog(user_id, self._mission_updater))

            sor = conn.execute("SELECT * FROM pilots WHERE id=?", (user_id,)).fetchone()
            if sor is not None:
                name = sor["name"]
                faction = Faction.from_code(sor["faction"])
                role_bits = sor["roles_bits"]
                raw_date = sor["last_logout_date"]
                if raw_date != "":
                    player.note_logout(Stamp(_dt.datetime.fromisoformat(raw_date)))
                raw_wof_date = sor["last_wof_date"]
                last_wof_date = read_moment(raw_wof_date)
                try:
                    player.daily_streak_day = sor["daily_streak_day"] or 0
                    player.daily_streak_date = sor["daily_streak_date"] or ""
                except (KeyError, IndexError):
                    pass

                player.name = name
                player.faction = faction
                player.seed_hangar()
                player.bgo_admin_roles.set_or(role_bits)
                player.last_free_wof_game = last_wof_date

            avatar_items = self._fetch_avatar(user_id, conn=conn)
            description = player.avatar_description.get()
            description.replace_avatar(avatar_items)

            existing_location = self._fetch_location(user_id, player.faction, conn=conn)
            if existing_location is None:
                raise RuntimeError('no saved location exists for this pilot')
            else:
                location_to_set = existing_location.previous_location
                if location_to_set in (PlaceKind.Arena, PlaceKind.BattleSpace,
                                       PlaceKind.Tournament, PlaceKind.Disconnect,
                                       PlaceKind.Starter, PlaceKind.Tutorial, PlaceKind.Teaser):
                    location_to_set = PlaceKind.Room
                    csillag = self._galaxy_map_card.starter_sector_for_faction(player.faction)
                else:
                    csillag = self._galaxy_map_card.stars.get(existing_location.sector_id)
                    if csillag is None:
                        csillag = self._galaxy_map_card.starter_sector_for_faction(player.faction)
                player.location.set_location(location_to_set, csillag.id, csillag.sector_guid)

            hangar_info = self._hangars.stored_hangar(player.user_id_of(), conn=conn)
            hangar = player.hangar_of()
            pending_selected_consumables = []
            for ship_info_fetch_result in hangar_info.ship_info_fetch_results:
                ship = HangarShip(user_id, ship_info_fetch_result.server_id, ship_info_fetch_result.guid,
                                  ship_info_fetch_result.name())
                ship.durability = ship_info_fetch_result.durability
                rekeszek = ship.ship_slots
                for slot_info in ship_info_fetch_result.slot_info_wrappers:
                    if slot_info.guid == 0:
                        continue
                    try:
                        rendszer = ShipSystem.from_guid(slot_info.guid)
                        rendszer.durability = slot_info.durability
                        if (slot := rekeszek.slot(slot_info.server_id)) is not None:
                            slot.add_ship_item(rendszer)
                            pending_selected_consumables.append((slot, slot_info.current_consumable_guid))
                    except ValueError as hibas_ertek:
                        log.warning(f'system row in the database is broken: {hibas_ertek}')
                ship.ship_stats().cap_hull_and_power()
                hangar.berth(ship)
            hangar.choose_active_ship(hangar_info.active_index)
            if hangar.by_server_id(hangar_info.active_index) is None:
                hatralevo = hangar.all_hangar_ships()
                if hatralevo:
                    hangar.choose_active_ship(hatralevo[0].server_id)
                    log.warning("Reset invalid active ship index %s -> %s for user %s",
                                hangar_info.active_index, hatralevo[0].server_id, user_id)

            self._fetch_skill_book(player, conn=conn)
            self._containers.stored_containers(player, conn=conn)
            self._restore_selected_consumables(player, pending_selected_consumables)
            normalize_default_model_paints(player)
            self._containers.stored_mails(player, conn=conn)
            self._fetch_settings(player, conn=conn)
            self._fetch_counters(player, conn=conn)
            self._fetch_token_cap(player, conn=conn)
            self._fetch_factors(player, conn=conn)
            self._fetch_friends(player, conn=conn)
            self._sqlite_missions.stored_missions(player, conn=conn)

            mutatok = hangar.active_ship().ship_stats()
            mutatok.fill_hull()

            return player
        except Exception as e:
            log.error(f'database write blew up {e} pilot:{user_id}')
            raise RuntimeError(e)
        finally:
            if conn is not None:
                conn.close()

    def _fetch_factors(self, player, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            for sor in conn.execute("SELECT * FROM boosts WHERE player_id=?", (player.user_id_of(),)):
                factor_source_id = sor["factor_source_id"]
                factor_type_id = sor["factor_type_id"]
                value = sor["value"]
                raw_end_time = sor["end_time"]

                end_time = _dt.datetime.fromisoformat(raw_end_time)
                if end_time.tzinfo is not None:
                    end_time = end_time.astimezone(_dt.timezone.utc).replace(tzinfo=None)
                factor_is_valid = end_time > _now_utc()
                if factor_is_valid:
                    tmp_factor = Boost(0, BoostKind.from_code(factor_type_id),
                                       BoostSource.from_code(factor_source_id), value, end_time)
                    player.factors.take_boost(tmp_factor)
        except Exception:
            log.exception("the pilot's boosts would not load")
        finally:
            if owns_connection:
                conn.close()

    def _restore_selected_consumables(self, player, pending_selected_consumables) -> None:
        hold = player.hold
        for rekesz, consumable_guid in pending_selected_consumables:
            if consumable_guid is None or consumable_guid == 0:
                continue
            consumable = hold.by_guid(consumable_guid)
            if consumable is None:
                log.warning("Saved selected consumable guid=%s missing from hold for user_id=%s slot_id=%s",
                            consumable_guid, player.user_id_of(), rekesz.ship_system.server_id)
                continue
            rekesz.current_consumable = consumable

    def _write_token_cap(self, player, conn=None) -> None:
        token_cap = player.merits_cap_farmed
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            conn.execute("REPLACE INTO limits(player_id, guid, value, last_cap_date) VALUES (?, ?, ?, ?)",
                         (player.user_id_of(), token_cap.guid, token_cap.farmed,
                          token_cap.last_reset.local_date.isoformat()))
            if owns_connection:
                conn.commit()
        except Exception:
            log.exception("the daily merit cap would not save")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()

    def _fetch_token_cap(self, player, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            for sor in conn.execute("SELECT * FROM limits WHERE player_id=?", (player.user_id_of(),)):
                guid = sor["guid"]
                value = sor["value"]
                raw_last_cap_date = sor["last_cap_date"]
                old_cap_date = _dt.datetime.fromisoformat(raw_last_cap_date)
                is_today = _now_utc().timetuple().tm_yday == old_cap_date.timetuple().tm_yday
                if is_today:
                    cap = player.merits_cap_farmed
                    cap.set_cap(value, old_cap_date)
                player.tally_desk.counters().restore_counters(guid, value)
        except Exception:
            log.exception("the daily merit cap would not load")
        finally:
            if owns_connection:
                conn.close()

    def _fetch_counters(self, player, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            for sor in conn.execute("SELECT * FROM tallies WHERE player_id=?", (player.user_id_of(),)):
                guid = sor["guid"]
                value = sor["value"]
                player.tally_desk.counters().restore_counters(guid, value)
        except Exception:
            log.exception("the tallies would not load")
        finally:
            if owns_connection:
                conn.close()

    def _fetch_avatar(self, player_id: int, conn=None):
        avatar_items = {}
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            for sor in conn.execute("SELECT * FROM avatar_parts WHERE player_id=?", (player_id,)):
                avatar_item_id = sor["item_id"]
                avatar_item = AvatarItem.from_code(avatar_item_id)
                value = sor["value"]
                avatar_items[avatar_item] = value
        except Exception:
            log.exception("the avatar would not load")
        finally:
            if owns_connection:
                conn.close()
        return avatar_items

    def _fetch_location(self, player_id: int, faction, conn=None):
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            sor = conn.execute("SELECT * FROM last_seen WHERE player_id=?", (player_id,)).fetchone()
            if sor is None:
                starter_sector = self._galaxy_map_card.starter_sector_for_faction(faction)
                return PlaceRow(starter_sector.id, PlaceKind.Room, PlaceKind.Starter)
            sector_id = sor["sector_id"]
            game_location = PlaceKind.from_code(sor["place"])
            previous_location = PlaceKind.from_code(sor["previous_place"])
            return PlaceRow(sector_id, game_location, previous_location)
        except Exception:
            log.exception("the last known place would not load")
        finally:
            if owns_connection:
                conn.close()
        return None

    def user_present(self, user_id: int) -> bool:
        log.info('probing the database for player {}'.format(user_id))
        with self._olvasva:
            conn = self._data_source.connection()
            try:
                sor = conn.execute("SELECT 1 FROM pilots WHERE id=? LIMIT 1", (user_id,)).fetchone()
                return sor is not None
            finally:
                conn.close()

    def refresh_avatar(self, user_id: int, avatar_description) -> None:
        self._write_avatar(avatar_description, user_id)


    def _fetch_friends(self, player, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            for sor in conn.execute("SELECT friend_id FROM friends WHERE player_id=?",
                                    (player.user_id_of(),)):
                player.friends.befriend_pilot(int(sor["friend_id"]))
        except Exception:
            log.exception("the friend list would not load")
        finally:
            if owns_connection:
                conn.close()

    def _write_friends(self, player, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            user_id = player.user_id_of()
            conn.execute("DELETE FROM friends WHERE player_id=?", (user_id,))
            rows = [(user_id, friend_id) for friend_id in player.friends.friend_ids()]
            if rows:
                conn.executemany(
                    "REPLACE INTO friends(player_id, friend_id) VALUES (?, ?)", rows)
            if owns_connection:
                conn.commit()
        except Exception:
            log.exception("the friend list would not save")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()

    def record_friendship(self, one_id: int, other_id: int) -> None:
        self._friendship_rows(
            "REPLACE INTO friends(player_id, friend_id) VALUES (?, ?)", one_id, other_id,
            "the new friendship would not save")

    def forget_friendship(self, one_id: int, other_id: int) -> None:
        self._friendship_rows(
            "DELETE FROM friends WHERE player_id=? AND friend_id=?", one_id, other_id,
            "the ended friendship would not save")

    def _friendship_rows(self, statement: str, one_id: int, other_id: int, panasz: str) -> None:
        if one_id == other_id:
            return
        conn = None
        try:
            conn = self._data_source.connection()
            conn.executemany(statement, ((one_id, other_id), (other_id, one_id)))
            conn.commit()
        except Exception:
            log.exception(panasz)
            if conn is not None:
                with suppress(Exception):
                    conn.rollback()
        finally:
            if conn is not None:
                conn.close()

    def friend_names(self, friend_ids) -> dict[int, str]:
        ids = [int(friend_id) for friend_id in friend_ids]
        if not ids:
            return {}
        conn = None
        try:
            conn = self._data_source.connection()
            helyek = ",".join("?" * len(ids))
            return {int(sor["id"]): sor["name"] for sor in conn.execute(
                f"SELECT id, name FROM pilots WHERE id IN ({helyek})", ids)}
        except Exception:
            log.exception("the friends' names would not load")
            return {}
        finally:
            if conn is not None:
                conn.close()

    def name_taken(self, name: str) -> bool:
        conn = self._data_source.connection()
        try:
            sor = conn.execute("SELECT 1 FROM pilots WHERE name=? LIMIT 1", (name,)).fetchone()
            return sor is not None
        except Exception:
            log.exception("the name check would not run")
        finally:
            conn.close()
        return True

    def name_taken_ignoring_case(self, name: str) -> bool:
        conn = self._data_source.connection()
        try:
            sor = conn.execute("SELECT 1 FROM pilots WHERE name COLLATE NOCASE = ? LIMIT 1", (name,)).fetchone()
            return sor is not None
        except Exception:
            log.exception("the case-insensitive name check would not run")
        finally:
            conn.close()
        return True

    def store_pilots(self, players) -> None:
        write_started_ms = now_ms() if GUARDRAILS_ENABLED else 0.0
        player_count = 0
        try:
            with self._irva:
                players = list(players)
                player_count = len(players)
                log.info(f'batched persistence begins, players: {len(players)}')
                for player in players:
                    self._internal_write_player(player)
                log.info('batched persistence done')
        finally:
            if GUARDRAILS_ENABLED:
                warn_if_slow(
                    log,
                    elapsed_ms(write_started_ms),
                    DB_BULK_WRITE_WARN_MS,
                    "Slow bulk player write players=%s",
                    player_count,
                )

    def store_pilot(self, player) -> None:
        write_started_ms = now_ms() if GUARDRAILS_ENABLED else 0.0
        player_id = player.user_id_of() if player is not None else None
        try:
            with self._irva:
                self._internal_write_player(player)
        finally:
            if GUARDRAILS_ENABLED:
                warn_if_slow(
                    log,
                    elapsed_ms(write_started_ms),
                    DB_PLAYER_WRITE_WARN_MS,
                    "Slow player write user_id=%s",
                    player_id,
                )

    def _internal_write_player(self, player) -> None:
        if player is None:
            raise TypeError("a pilot is required to write a row")

        location = player.location.non_disconnect_location()
        if location == PlaceKind.Starter or location == PlaceKind.Avatar:
            log.info('a pilot is still in %s - the write is held back', location)
            return

        conn = None
        try:
            log.info('pilot heading into the database... %s', player.player_log)
            conn = self._data_source.connection()
            conn.execute("BEGIN")
            last_logout_text = ""
            if player.last_logout is not None:
                last_logout_text = player.last_logout.local_date.isoformat()
            wof_draw_date = ""
            if player.last_free_wof_game is not None:
                wof_draw_date = player.last_free_wof_game.local_date.isoformat()
            conn.execute(
                "REPLACE INTO pilots(id, name, faction, roles_bits, last_logout_date, last_wof_date,"
                " daily_streak_day, daily_streak_date)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (player.user_id_of(), player.name, player.faction.value,
                 player.bgo_admin_roles.role_bits, last_logout_text, wof_draw_date,
                 player.daily_streak_day, player.daily_streak_date))

            self._write_avatar(player.avatar_description.get(), player.user_id_of(), conn=conn)
            self._write_settings(player, conn=conn)
            self._write_location(player, conn=conn)
            self._write_skill_book(player, conn=conn)
            self._sqlite_missions.store_missions(player, conn=conn)
            self._hangars.write_hangar(player, conn=conn)
            self._write_counters_db(player, conn=conn)
            self._containers.write_containers(player, conn=conn)
            self._containers.write_mails(player, conn=conn)
            self._write_token_cap(player, conn=conn)
            self._write_factors(player, conn=conn)
            self._write_friends(player, conn=conn)
            conn.commit()
            log.info('storing pilot %s stored', player.name)
        except Exception as e:
            if conn is not None:
                with suppress(Exception):
                    conn.rollback()
            log.error(f'saving a pilot into the database failed: {e}')
        finally:
            if conn is not None:
                conn.close()

    def _write_factors(self, player, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            conn.execute("DELETE FROM boosts WHERE player_id=?", (player.user_id_of(),))
            factors = player.factors
            sorok = []
            for szorzo in factors.values():
                if szorzo.factor_source == BoostSource.Faction:
                    continue
                sorok.append((szorzo.server_id, player.user_id_of(), szorzo.factor_source.int_value,
                             szorzo.factor_type.int_value, szorzo.value,
                             szorzo.end_time.isoformat()))
            conn.executemany("REPLACE INTO boosts(id, player_id, factor_source_id, factor_type_id, value, end_time)"
                             " VALUES (?, ?, ?, ?, ?, ?)", sorok)
            if owns_connection:
                conn.commit()
        except Exception:
            log.exception("the pilot's boosts would not save")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()

    def write_guilds(self, guild_registry) -> None:
        log.info('about to persist the guilds')
        self._sqlite_guild_processor.write_all_guilds(guild_registry)

    def stored_guilds(self, guild_registry) -> None:
        self._sqlite_guild_processor.stored_guilds(guild_registry)

    def stored_counters(self, conn=None):
        counter_desc_map = {}
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            for rs in conn.execute("SELECT * FROM tallies"):
                player_id = rs[0]
                guid = rs[1]
                value = rs[2]
                counter_record = counter_desc_map.get(player_id)
                if counter_record is None:
                    counter_record = TallySheet(player_id)
                counter_record.counters()[guid] = value
                counter_desc_map[player_id] = counter_record
        except Exception as e:
            raise RuntimeError(e)
        finally:
            if owns_connection:
                conn.close()
        return counter_desc_map

    def fetch_all_player_ranking_infos(self, conn=None):
        from rebsgo.vocabulary.pilot import Faction
        eredmeny = {}
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            for sor in conn.execute("SELECT id, name, faction FROM pilots"):
                try:
                    faction = Faction(int(sor["faction"]))
                except Exception:
                    faction = Faction.Neutral
                eredmeny[sor["id"]] = (sor["name"], faction)
        except Exception:
            log.exception("the standings roll would not load")
        finally:
            if owns_connection:
                conn.close()
        return eredmeny

    def fetch_all_player_experience(self, conn=None):
        eredmeny = {}
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            for sor in conn.execute("SELECT player_id, xp FROM skill_books"):
                eredmeny[sor["player_id"]] = int(sor["xp"] or 0)
        except Exception:
            log.exception("the experience totals would not load")
        finally:
            if owns_connection:
                conn.close()
        return eredmeny

    def ranking_period_stored(self, period_key: str) -> bool:
        conn = self._data_source.connection()
        try:
            sor = conn.execute("SELECT 1 FROM ranking_snapshots WHERE period_key = ? LIMIT 1",
                               (period_key,)).fetchone()
            return sor is not None
        except Exception:
            log.exception("the ranking snapshot check would not run")
            return True
        finally:
            conn.close()

    def take_ranking_snapshot(self, period_key: str) -> None:
        conn = self._data_source.connection()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO ranking_snapshots(period_key, player_id, guid, value) "
                "SELECT ?, player_id, guid, value FROM tallies", (period_key,))
            conn.commit()
            log.info("ranking snapshot taken for %s", period_key)
        except Exception:
            log.exception("the ranking snapshot would not be taken for %s", period_key)
        finally:
            conn.close()

    def fetch_ranking_period(self, period_key: str) -> dict:
        eredmeny: dict = {}
        conn = self._data_source.connection()
        try:
            for sor in conn.execute(
                    "SELECT player_id, guid, value FROM ranking_snapshots WHERE period_key = ?",
                    (period_key,)):
                eredmeny.setdefault(sor[0], {})[sor[1]] = sor[2]
        except Exception:
            log.exception("the ranking snapshot would not load for %s", period_key)
        finally:
            conn.close()
        return eredmeny

    def drop_ranking_periods_except(self, megtartando) -> None:
        megtartando = list(megtartando or [])
        if not megtartando:
            return
        conn = self._data_source.connection()
        try:
            helyek = ",".join("?" for _ in megtartando)
            conn.execute(f"DELETE FROM ranking_snapshots WHERE period_key NOT IN ({helyek})",
                         megtartando)
            conn.commit()
        except Exception:
            log.exception("old ranking snapshots would not be cleared")
        finally:
            conn.close()

    def fetch_ranking_snapshot(self, include_experience: bool = False):
        conn = self._data_source.connection()
        try:
            counters = self.stored_counters(conn=conn)
            player_infos = self.fetch_all_player_ranking_infos(conn=conn)
            experience = self.fetch_all_player_experience(conn=conn) if include_experience else {}
            return counters, player_infos, experience
        finally:
            conn.close()

    def _write_avatar(self, avatar_description, user_id: int, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            items = avatar_description.unmodifiable_items
            sorok = [(user_id, kulcs.value, value) for kulcs, value in items.items()]
            conn.executemany("REPLACE INTO avatar_parts(player_id, item_id, value) VALUES (?, ?, ?)", sorok)
            if owns_connection:
                conn.commit()
        except Exception:
            log.exception("the avatar would not save")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()

    def _write_counters_db(self, player, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            conn.execute("DELETE FROM tallies WHERE player_id = ?", (player.user_id_of(),))
            counters = player.tally_desk.counters()
            sorok = []
            for value in counters.internal_read_only.values():
                if value.guid == _TOKEN_GUID:
                    log.error('counter mixup: a token arrived as a counter from {}'.format(player.player_log))
                    continue
                sorok.append((player.user_id_of(), value.guid, value.value))
            conn.executemany("REPLACE INTO tallies(player_id, guid, value) VALUES (?, ?, ?)", sorok)
            if owns_connection:
                conn.commit()
        except Exception:
            log.exception("the tallies would not save")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()

    def _fetch_skill_book(self, player, conn=None) -> None:
        empty_skill_book = player.skill_book
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            sor = conn.execute("SELECT * FROM skill_books WHERE player_id = ?", (player.user_id_of(),)).fetchone()
            if sor is not None:
                xp = sor["xp"]
                spent_xp = sor["spent_xp"]
                empty_skill_book.experience = 0
                empty_skill_book.earn_experience(xp)
                empty_skill_book.note_spent_experience(spent_xp)

            for sor in conn.execute("SELECT * FROM pilot_skills WHERE player_id = ?", (player.user_id_of(),)):
                card_guid = sor["card_guid"]
                server_id = sor["server_id"]
                skill = empty_skill_book.all_skills.get(server_id)
                skill.seed_skill_card(card_guid)
        except Exception:
            log.exception("the skill book would not load")
        finally:
            if owns_connection:
                conn.close()

    def _write_skill_book(self, player, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            conn.execute("REPLACE INTO skill_books(player_id, xp, spent_xp) VALUES (?, ?, ?)",
                         (player.user_id_of(), player.skill_book.experience,
                          player.skill_book.spent_experience()))
            sorok = []
            for server_id, skill in player.skill_book.all_skills.items():
                sorok.append((player.user_id_of(), skill.skill_card.card_guid_of(), skill.server_id))
            conn.executemany("REPLACE INTO pilot_skills(player_id, card_guid, server_id) VALUES (?, ?, ?)", sorok)
            if owns_connection:
                conn.commit()
        except Exception:
            log.exception("the skill book would not save")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()

    def _write_location(self, player, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            conn.execute(
                "REPLACE INTO last_seen(player_id, sector_id, place, previous_place)"
                " VALUES (?, ?, ?, ?)",
                (player.user_id_of(), player.location.sector_id,
                 player.location.game_location.value,
                 player.location.previous_location.value))
            if owns_connection:
                conn.commit()
        except Exception:
            log.exception("the last known place would not save")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()

    def _fetch_settings(self, player, conn=None) -> None:
        from rebsgo.protocol.setting.preferences_wire import SettingProtocol
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            settings = player.settings
            server_saved_settings = settings.server_saved_user_settings
            for sor in conn.execute("SELECT * FROM client_options WHERE player_id=?",
                                    (player.user_id_of(),)):
                setting = Option.from_code(sor["user_setting_id"])
                value_type = SettingProtocol.value_type(setting)
                if value_type == OptionKind.Byte:
                    server_saved_settings.set_option(setting, OptionByte(int(sor["value"])))
                elif value_type == OptionKind.Integer:
                    server_saved_settings.set_option(setting, OptionNumber(int(sor["value"])))
                elif value_type == OptionKind.Float:
                    server_saved_settings.set_option(setting, OptionDecimal(sor["value"]))
                elif value_type == OptionKind.Boolean:
                    float_value = sor["value"]
                    server_saved_settings.set_option(setting, OptionFlag(float_value == 1.0))
                else:
                    raise RuntimeError(f'database read, kind {value_type} has no implementation')
            server_saved_settings.apply_render_defaults()
        except Exception:
            log.exception("the saved options would not load")

        try:
            settings = player.settings
            input_bindings = settings.input_bindings
            for sor in conn.execute("SELECT * FROM key_bindings WHERE player_id=?",
                                    (player.user_id_of(),)):
                action = Action.from_code(sor["action_id"])
                trigger_code = sor["device_trigger_code"]
                mod_code = sor["device_mod_code"]
                device = sor["device"]
                flags = sor["flags"]
                profile_no = sor["profile_number"]
                binding = KeyBinding(action, trigger_code, mod_code, device, flags, profile_no)
                input_bindings.remember(binding)
        except Exception:
            log.exception("the key bindings would not load")

        try:
            help_screens = []
            for sor in conn.execute("SELECT help_screen_id FROM tutorials_done WHERE player_id=?",
                                    (player.user_id_of(),)):
                help_screen = HelpScreenKind.from_code(int(sor["help_screen_id"]))
                if help_screen is not None:
                    help_screens.append(help_screen)
            if help_screens:
                player.settings.server_saved_user_settings.set_option(
                    Option.CompletedTutorials, OptionHelpScreen(help_screens))
        except Exception:
            log.exception("the seen help screens would not load")
        finally:
            if owns_connection:
                conn.close()

    def _write_settings(self, player, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            settings = player.settings
            settings_map = settings.server_saved_user_settings.settings_unmodifiable_map()
            setting_rows = []
            for setting_key, setting_value in settings_map.items():
                vt = setting_value.type
                if vt == OptionKind.Float2 or vt == OptionKind.HelpScreenKind:
                    continue
                if vt == OptionKind.Byte:
                    value = int(setting_value.value)
                elif vt == OptionKind.Boolean:
                    value = 1 if setting_value.value else 0
                elif vt == OptionKind.Integer:
                    value = int(setting_value.value)
                elif vt == OptionKind.Float:
                    value = float(setting_value.value)
                else:
                    raise ValueError(f'a setting of type {vt} has no place in the database')
                setting_rows.append((player.user_id_of(), setting_key.value, value))
            conn.executemany("REPLACE INTO client_options(player_id, user_setting_id, value)"
                             " VALUES (?, ?, ?)", setting_rows)

            bindings = settings.input_bindings.unmodifiable_input_bindings
            binding_rows = []
            for binding in bindings:
                binding_rows.append((player.user_id_of(), binding.action.int_value,
                                     binding.device_trigger_code, binding.device_modifier_code,
                                     binding.device, binding.flags, binding.profile_no))
            conn.executemany("REPLACE INTO key_bindings(player_id, action_id, device_trigger_code, "
                             "device_mod_code, device, flags, profile_number) VALUES (?, ?, ?, ?, ?, ?, ?)",
                             binding_rows)

            conn.execute("DELETE FROM tutorials_done WHERE player_id=?", (player.user_id_of(),))
            tutorial_rows = []
            for setting_key, setting_value in settings_map.items():
                if setting_value.type == OptionKind.HelpScreenKind:
                    for help_screen in setting_value.value:
                        if help_screen is not None:
                            tutorial_rows.append((player.user_id_of(), help_screen.int_value))
            if tutorial_rows:
                conn.executemany("REPLACE INTO tutorials_done(player_id, help_screen_id)"
                                 " VALUES (?, ?)", tutorial_rows)
            if owns_connection:
                conn.commit()
        except Exception:
            log.exception("the settings would not save")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()

    @staticmethod
    def read_moment(nyers_szoveg: str):
        return read_moment(nyers_szoveg)
