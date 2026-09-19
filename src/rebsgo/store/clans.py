# github.com/Shran21

from __future__ import annotations

from rebsgo.pilots.state.whereabouts import Offline
from rebsgo.pilots.together.clan import ClanRank
from rebsgo.vocabulary.community import ClanRole
from rebsgo.vocabulary.world import SceneChange
import logging


class ClanMemberRow:
    def __init__(self, guild_role, player):
        self._guild_role = guild_role
        self._player = player

    @property
    def guild_role(self):
        return self._guild_role

    def player(self):
        return self._player

    def __eq__(self, other) -> bool:
        if self is other:
            return True
        if type(other) is not type(self):
            return NotImplemented
        return self._guild_role == other._guild_role and self._player == other._player

    def __hash__(self) -> int:
        return hash((self._guild_role, self._player))

    def __repr__(self) -> str:
        return f'<{self._player} as {self._guild_role}>'


class ClanRow:
    def __init__(self, id: int, name: str, klan_rangok, tag_sorok):
        self._id = id
        self._name = name
        self._guild_rank_definition_set = klan_rangok
        self._member_info_records = tag_sorok

    def id(self) -> int:
        return self._id

    def name(self) -> str:
        return self._name

    @property
    def guild_rank_definition_set(self):
        return self._guild_rank_definition_set

    @property
    def member_info_records(self):
        return self._member_info_records

    def __repr__(self) -> str:
        return (f'<clan {self._name} #{self._id}, ranks'
                f' {self._guild_rank_definition_set}, roster {self._member_info_records}>')


log = logging.getLogger(__name__)


def _jeloljuk_kilepettnek(player) -> None:
    try:
        player.location.switch_state(Offline(player.location, SceneChange.None_))
    except Exception:
        log.warning("could not mark a restored guild member as logged out", exc_info=True)


class SqliteClans:
    def __init__(self, data_source, sqlite_store=None):
        self._data_source = data_source
        self._sqlite_store = sqlite_store

    def disband_guild(self, guild_id: int, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            if owns_connection:
                conn.execute("BEGIN")
            for sql in ("DELETE FROM guild_members WHERE guild_id=?",
                        "DELETE FROM guild_ranks WHERE guild_id=?",
                        "DELETE FROM guilds WHERE id=?"):
                conn.execute(sql, (guild_id,))
            if owns_connection:
                conn.commit()
        except Exception:
            if owns_connection:
                conn.rollback()
            log.exception("the clan would not disband in the database")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()

    @staticmethod
    def _collect_rank_definition_rows(guild_id: int, klan_rang_lista):
        return [(guild_id, d.guild_role.value, d.name, d.permissions)
                for d in klan_rang_lista]

    def _write_rank_definitions(self, guild_id: int, klan_rang_lista, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            sorok = self._collect_rank_definition_rows(guild_id, klan_rang_lista)
            conn.executemany("REPLACE INTO guild_ranks(guild_id, role_id, rank_name, permissions) "
                             "VALUES (?, ?, ?, ?)", sorok)
            if owns_connection:
                conn.commit()
        except Exception:
            log.exception("the clan ranks would not save")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()

    @staticmethod
    def _collect_guild_member_rows(guild_id: int, wing_roster):
        return [(guild_id, m.pilot_id(), m.player_role.value) for m in wing_roster]

    def _write_wing_roster(self, guild_id: int, wing_roster, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            sorok = self._collect_guild_member_rows(guild_id, wing_roster)
            conn.executemany("REPLACE INTO guild_members(guild_id, player_id, role) "
                             "VALUES (?, ?, ?)", sorok)
            if owns_connection:
                conn.commit()
        except Exception:
            log.exception("the clan roster would not save")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()

    def write_all_guilds(self, guild_registry) -> None:
        with self._sqlite_store.iras_alatt:
            log.info('guild persistence holds the lock now')
            try:
                all_guilds = []
                for klan in guild_registry.all_guilds():
                    if not klan.wing_roster:
                        log.info("skip persisting memberless guild %s (id=%s) to keep its saved members",
                                 klan.name, klan.id)
                        continue
                    all_guilds.append(klan)
                conn = self._data_source.connection()
                try:
                    conn.execute("BEGIN")
                    guild_rows = []
                    rank_rows = []
                    member_rows = []
                    for klan in all_guilds:
                        self.disband_guild(klan.id, conn=conn)
                        log.info("write_guild {} into db".format(klan))
                        guild_rows.append((klan.id, klan.name))
                        rank_rows.extend(self._collect_rank_definition_rows(
                            klan.id, klan.guild_rank_definitions))
                        member_rows.extend(self._collect_guild_member_rows(
                            klan.id, klan.wing_roster))
                    conn.executemany("REPLACE INTO guilds(id, name) VALUES (?, ?)", guild_rows)
                    conn.executemany("REPLACE INTO guild_ranks(guild_id, role_id, rank_name, permissions) "
                                     "VALUES (?, ?, ?, ?)", rank_rows)
                    conn.executemany("REPLACE INTO guild_members(guild_id, player_id, role) "
                                     "VALUES (?, ?, ?)", member_rows)
                    conn.commit()
                except Exception:
                    conn.rollback()
                    log.error("error in writing guilds transaction", exc_info=True)
                finally:
                    conn.close()
            except Exception as e:
                log.error('guild persistence fell over', exc_info=e)

    def stored_guilds(self, guild_registry) -> None:
        guild_fetch_results = []
        conn = self._data_source.connection()
        try:
            guild_rows = []
            for sor in conn.execute("SELECT * FROM guilds"):
                id = sor["id"]
                name = sor["name"]
                guild_rows.append((id, name))
            guild_ids = [guild_id for guild_id, _ in guild_rows]
            rank_definitions_by_guild = self._get_rank_definitions_for_guilds(guild_ids, conn=conn)
            member_rows_by_guild = self._fetch_guild_member_rows_for_guilds(guild_ids, conn=conn)
        except Exception:
            log.exception("the clans would not load")
            guild_rows = []
            rank_definitions_by_guild = {}
            member_rows_by_guild = {}
        finally:
            conn.close()

        for id, name in guild_rows:
            wing_roster = self._member_info_records_from_rows(id, member_rows_by_guild.get(id, []))
            guild_fetch_results.append(ClanRow(
                id, name, rank_definitions_by_guild.get(id, set()), wing_roster))
        self._create_guilds_from_wrappers(guild_registry, guild_fetch_results)

    def _create_guilds_from_wrappers(self, guild_registry, klan_sorok) -> None:
        for guild_fetch_result in klan_sorok:
            klan = guild_registry.restore_guild(guild_fetch_result.name(), guild_fetch_result.id())
            klan.seed_ranks(guild_fetch_result.guild_rank_definition_set)
            for member_info_record in guild_fetch_result.member_info_records:
                klan.enrol(member_info_record.player(), member_info_record.guild_role)

    def stored_guild(self, id: int, name: str) -> ClanRow:
        rank_definitions = self._get_rank_definitions(id)
        wing_roster = self._fetch_wing_roster(id)
        return ClanRow(id, name, rank_definitions, wing_roster)

    def _get_rank_definitions(self, guild_id: int, conn=None):
        return self._get_rank_definitions_for_guilds([guild_id], conn=conn).get(guild_id, set())

    def _get_rank_definitions_for_guilds(self, guild_ids, conn=None):
        eredmeny = {guild_id: set() for guild_id in guild_ids}
        if not guild_ids:
            return eredmeny
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            placeholders = ",".join("?" for _ in guild_ids)
            cursor = conn.execute(
                "SELECT * FROM guild_ranks WHERE guild_id IN (" + placeholders + ")",
                tuple(guild_ids))
            for sor in cursor:
                guild_id = sor["guild_id"]
                role_id = sor["role_id"]
                rank_name = sor["rank_name"]
                permissions = sor["permissions"]
                eredmeny.setdefault(guild_id, set()).add(
                    ClanRank(ClanRole.from_code(role_id), rank_name, permissions))
        except Exception:
            log.exception("the clan ranks would not load")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()
        return eredmeny

    def _fetch_wing_roster(self, guild_id: int):
        sorok = self._fetch_guild_member_rows_for_guilds([guild_id]).get(guild_id, [])
        return self._member_info_records_from_rows(guild_id, sorok)

    def _fetch_guild_member_rows_for_guilds(self, guild_ids, conn=None):
        eredmeny = {guild_id: [] for guild_id in guild_ids}
        if not guild_ids:
            return eredmeny
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            placeholders = ",".join("?" for _ in guild_ids)
            cursor = conn.execute(
                "SELECT * FROM guild_members WHERE guild_id IN (" + placeholders + ") "
                "ORDER BY guild_id, player_id",
                tuple(guild_ids))
            for sor in cursor:
                eredmeny.setdefault(sor["guild_id"], []).append((sor["player_id"], sor["role"]))
        except Exception:
            log.exception("the clan members would not load")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()
        return eredmeny

    def _member_info_records_from_rows(self, guild_id: int, rows):
        member_info_records = []
        for player_id, roles_id in rows:
            try:
                player = self._sqlite_store.stored_pilot(player_id)
                _jeloljuk_kilepettnek(player)
                member_info_records.append(ClanMemberRow(ClanRole.from_code(roles_id), player))
            except Exception:
                log.warning("failed to load guild member player_id=%s for guild_id=%s",
                            player_id, guild_id, exc_info=True)
        return member_info_records
