# github.com/Shran21
from __future__ import annotations

import datetime as _dt
import logging

from rebsgo.pilots.state.holdings.storages import StorageKind, Mail
from rebsgo.vocabulary.pilot import ResourceKind
from rebsgo.gamedata.ship_parts.parts import CountableItem, ShipSystem

log = logging.getLogger(__name__)


class SqliteStorages:
    def __init__(self, data_source, server_settings):
        self._data_source = data_source
        self._server_settings = server_settings

    def wipe_mail_holds(self, player, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            if owns_connection:
                conn.execute("BEGIN")
            self._delete_items_from_container(player, StorageKind.Mail, conn=conn)
            self._delete_mails(player, conn=conn)
            if owns_connection:
                conn.commit()
        except Exception:
            if owns_connection:
                conn.rollback()
            log.exception("the mail attachments would not clear")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()

    def _delete_mails(self, player, conn=None) -> None:
        mail_box = player.mail_box
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            sorok = [(player.user_id_of(), mail.server_id) for mail in mail_box.items().values()]
            conn.executemany("DELETE FROM mail WHERE player_id = ? AND mail_id = ?", sorok)
            if owns_connection:
                conn.commit()
        except Exception:
            if owns_connection:
                conn.rollback()
            log.exception("the mails would not delete")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()

    def _delete_items_from_container(self, player, type, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            if owns_connection:
                conn.execute("BEGIN")
            for sql in ("DELETE FROM installed_systems WHERE player_id = ? AND container_id = ?",
                        "DELETE FROM stacks WHERE player_id = ? AND container_id = ?",
                        "DELETE FROM container_slots WHERE player_id = ? AND kind = ?"):
                conn.execute(sql, (player.user_id_of(), type.value))
            if owns_connection:
                conn.commit()
        except Exception:
            if owns_connection:
                conn.rollback()
            log.exception("the container items would not delete")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()

    def _write_items_to_container(self, player, container, conn=None) -> None:
        type = container.container_id.container_type
        self._write_systems_and_countables(player.user_id_of(), type, container,
                                           lambda item: item.server_id, conn=conn)

    @staticmethod
    def _collect_system_and_countable_rows(player_id, type, container, server_id_of):
        system_rows = []
        countable_rows = []
        for item_id in container.all_items_ids():
            tetel = container.by_id(item_id)
            if isinstance(tetel, ShipSystem):
                system_rows.append((player_id, type.value, server_id_of(tetel),
                                    tetel.card_guid_of(), tetel.durability))
            elif isinstance(tetel, CountableItem):
                countable_rows.append((player_id, type.value, server_id_of(tetel),
                                       tetel.card_guid_of(), tetel.count()))
        return system_rows, countable_rows

    def _write_systems_and_countables(self, player_id, type, container, server_id_of, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            if owns_connection:
                conn.execute("BEGIN")
            system_rows, countable_rows = self._collect_system_and_countable_rows(
                player_id, type, container, server_id_of)
            conn.executemany("INSERT INTO installed_systems(player_id, container_id, server_id, guid, durability)"
                             "VALUES (?, ?, ?, ?, ?)", system_rows)
            conn.executemany("INSERT INTO stacks(player_id, container_id, server_id, guid, count)"
                             "VALUES (?, ?, ?, ?, ?)", countable_rows)
            if owns_connection:
                conn.commit()
        except Exception:
            if owns_connection:
                conn.rollback()
            log.exception("the container contents would not save")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()

    def write_containers(self, player, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            player_id = player.user_id_of()
            hold = player.hold
            locker = player.locker
            hold_type = hold.container_id.container_type
            locker_type = locker.container_id.container_type
            container_rows = [
                (hold_type.value, player_id),
                (locker_type.value, player_id),
            ]
            hold_system_rows, hold_countable_rows = self._collect_system_and_countable_rows(
                player_id, hold_type, hold, lambda item: item.server_id)
            locker_system_rows, locker_countable_rows = self._collect_system_and_countable_rows(
                player_id, locker_type, locker, lambda item: item.server_id)

            if owns_connection:
                conn.execute("BEGIN")
            for type in (hold_type, locker_type):
                conn.execute("DELETE FROM installed_systems WHERE player_id = ? AND container_id = ?",
                             (player_id, type.value))
                conn.execute("DELETE FROM stacks WHERE player_id = ? AND container_id = ?",
                             (player_id, type.value))
                conn.execute("DELETE FROM container_slots WHERE player_id = ? AND kind = ?",
                             (player_id, type.value))
            conn.executemany("INSERT INTO container_slots(kind, player_id)VALUES (?, ?)", [
                *container_rows,
            ])
            conn.executemany("INSERT INTO installed_systems(player_id, container_id, server_id, guid, durability)"
                             "VALUES (?, ?, ?, ?, ?)", hold_system_rows + locker_system_rows)
            conn.executemany("INSERT INTO stacks(player_id, container_id, server_id, guid, count)"
                             "VALUES (?, ?, ?, ?, ?)", hold_countable_rows + locker_countable_rows)
            if owns_connection:
                conn.commit()
        except Exception:
            if owns_connection:
                conn.rollback()
            log.exception("the containers would not save")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()

    def stored_mails(self, player, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            sorok = conn.execute("SELECT * FROM mail WHERE player_id=?", (player.user_id_of(),)).fetchall()
            items_by_mail = self._fetch_mail_items_for_mail_ids(
                player.user_id_of(), [sor["mail_id"] for sor in sorok], conn=conn)
            for sor in sorok:
                mail_id = sor["mail_id"]
                mail_template_guid = sor["mail_template_guid"]
                raw_time_stamp = sor["received_timestamp"]
                received_time_stamp = _dt.datetime.fromisoformat(raw_time_stamp)
                raw_parameters = sor["parameters"]
                parameters = raw_parameters.split(",")

                items_fetched = items_by_mail.get(mail_id, [])
                mail = Mail(mail_id, mail_template_guid, Mail.MailState.Unread,
                            received_time_stamp, items_fetched, parameters, player.user_id_of())
                player.mail_box.add_item(mail)
        except Exception:
            log.exception("the mails would not load")
        finally:
            if owns_connection:
                conn.close()

    def _fetch_mail_items(self, player_id: int, mail_id: int, conn=None):
        items_by_mail = self._fetch_mail_items_for_mail_ids(player_id, [mail_id], conn=conn)
        return items_by_mail.get(mail_id, [])

    def _fetch_mail_items_for_mail_ids(self, player_id: int, mail_ids, conn=None):
        items_by_mail = {mail_id: [] for mail_id in mail_ids}
        if not mail_ids:
            return items_by_mail
        type = StorageKind.Mail
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            placeholders = ",".join("?" for _ in mail_ids)
            cursor = conn.execute(
                "SELECT * FROM installed_systems WHERE player_id=? AND container_id=? "
                f"AND server_id IN ({placeholders})",
                (player_id, type.value, *mail_ids))
            for sor in cursor:
                mail_id = sor["server_id"]
                guid = sor["guid"]
                durability = sor["durability"]
                try:
                    rendszer = ShipSystem.from_guid(guid)
                    rendszer.durability = durability
                    items_by_mail.setdefault(mail_id, []).append(rendszer)
                except ValueError:
                    log.warning(f'guid absent {guid}')

            cursor = conn.execute(
                "SELECT * FROM stacks WHERE player_id=? AND container_id=? "
                f"AND server_id IN ({placeholders})",
                (player_id, type.value, *mail_ids))
            for sor in cursor:
                mail_id = sor["server_id"]
                guid = sor["guid"]
                count = sor["count"]
                try:
                    countable = CountableItem.from_guid(guid, count)
                    items_by_mail.setdefault(mail_id, []).append(countable)
                except ValueError as hibas_ertek:
                    log.warning(f'mail attachment in the database is broken: {hibas_ertek}')
        except Exception:
            log.exception("the mail attachments would not load")
        finally:
            if owns_connection:
                conn.close()
        return items_by_mail

    def write_mails(self, player, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            if owns_connection:
                conn.execute("BEGIN")
            self._write_mails_with_conn(conn, player.user_id_of(), player.mail_box.items().values())
            if owns_connection:
                conn.commit()
        except Exception:
            if owns_connection:
                conn.rollback()
            log.exception("the mails would not save")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()

    def _write_mails(self, player_id: int, mails, conn=None) -> None:
        mails = list(mails)
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            if owns_connection:
                conn.execute("BEGIN")
            sorok = []
            for mail in mails:
                parameter_string = ",".join(mail.parameters)
                sorok.append((mail.server_id, player_id, mail.mail_template_card_guid,
                             mail.received.isoformat(), parameter_string))
            conn.executemany("REPLACE INTO mail(mail_id, player_id, mail_template_guid, received_timestamp, "
                             "parameters) VALUES (?, ?, ?, ?, ?)", sorok)
            self._write_mail_entries(player_id, mails, conn=conn)
            if owns_connection:
                conn.commit()
        except Exception:
            if owns_connection:
                conn.rollback()
            log.exception("the mail rows would not save")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()

    def _write_mail_entries(self, player_id: int, mails, conn=None) -> None:
        for mail in mails:
            tarolo = mail.mail_container
            type = tarolo.container_id.container_type
            self._write_systems_and_countables(
                player_id, type, tarolo, lambda item, m=mail: m.server_id, conn=conn)

    def _write_mails_with_conn(self, conn, player_id: int, mails) -> None:
        mails = list(mails)
        mail_type = StorageKind.Mail
        conn.execute("DELETE FROM installed_systems WHERE player_id = ? AND container_id = ?",
                     (player_id, mail_type.value))
        conn.execute("DELETE FROM stacks WHERE player_id = ? AND container_id = ?",
                     (player_id, mail_type.value))
        conn.execute("DELETE FROM container_slots WHERE player_id = ? AND kind = ?",
                     (player_id, mail_type.value))
        delete_mail_rows = [(player_id, mail.server_id) for mail in mails]
        conn.executemany("DELETE FROM mail WHERE player_id = ? AND mail_id = ?", delete_mail_rows)
        conn.execute("INSERT INTO container_slots(kind, player_id)VALUES (?, ?)",
                     (mail_type.value, player_id))

        mail_rows = []
        system_rows = []
        countable_rows = []
        for mail in mails:
            parameter_string = ",".join(mail.parameters)
            mail_rows.append((mail.server_id, player_id, mail.mail_template_card_guid,
                              mail.received.isoformat(), parameter_string))
            tarolo = mail.mail_container
            type = tarolo.container_id.container_type
            mail_system_rows, mail_countable_rows = self._collect_system_and_countable_rows(
                player_id, type, tarolo, lambda item, m=mail: m.server_id)
            system_rows.extend(mail_system_rows)
            countable_rows.extend(mail_countable_rows)
        conn.executemany("REPLACE INTO mail(mail_id, player_id, mail_template_guid, received_timestamp, "
                         "parameters) VALUES (?, ?, ?, ?, ?)", mail_rows)
        conn.executemany("INSERT INTO installed_systems(player_id, container_id, server_id, guid, durability)"
                         "VALUES (?, ?, ?, ?, ?)", system_rows)
        conn.executemany("INSERT INTO stacks(player_id, container_id, server_id, guid, count)"
                         "VALUES (?, ?, ?, ?, ?)", countable_rows)

    def _fetch_container_systems(self, conn, player_id: int, containers_by_type) -> None:
        if not containers_by_type:
            return
        container_type_ids = tuple(containers_by_type.keys())
        placeholders = ",".join("?" for _ in container_type_ids)
        cursor = conn.execute(
            "SELECT * FROM installed_systems WHERE player_id=? "
            f"AND container_id IN ({placeholders})",
            (player_id, *container_type_ids))
        for sor in cursor:
            tarolo = containers_by_type.get(sor["container_id"])
            if tarolo is None:
                continue
            guid = sor["guid"]
            durability = sor["durability"]
            try:
                rendszer = ShipSystem.from_guid(guid)
                rendszer.durability = durability
                tarolo.add_ship_item(rendszer)
            except ValueError:
                log.info(f'item record arrived guidless {guid}')

    def _fetch_container_countables(self, conn, player, containers_by_type) -> None:
        if not containers_by_type:
            return
        container_type_ids = tuple(containers_by_type.keys())
        placeholders = ",".join("?" for _ in container_type_ids)
        cursor = conn.execute(
            "SELECT * FROM stacks WHERE player_id=? "
            f"AND container_id IN ({placeholders})",
            (player.user_id_of(), *container_type_ids))
        for sor in cursor:
            tarolo = containers_by_type.get(sor["container_id"])
            if tarolo is None:
                continue
            guid = sor["guid"]
            count = sor["count"]
            if not self._server_settings.starter_params.testing_mode and player.user_id_of() > 4:
                if guid == ResourceKind.Cubits.guid and count >= 2_000_000:
                    log.warning('suspicious wealth: player {} holds {} cubits'.format(
                        player.user_id_of(), count))
                elif guid == ResourceKind.TuningKit.guid and count >= 2000:
                    log.warning("Cheat warning; userID: {} has unusual amount of tuning_kits {}".format(
                        player.user_id_of(), count))
            try:
                countable = CountableItem.from_guid(guid, count)
                tarolo.add_ship_item(countable)
            except ValueError:
                log.error(f'item record arrived guidless {guid}')

    def _fetch_container(self, player, container, conn=None) -> None:
        type = container.container_id.container_type
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            containers_by_type = {type.value: container}
            self._fetch_container_systems(conn, player.user_id_of(), containers_by_type)
            self._fetch_container_countables(conn, player, containers_by_type)
        except Exception:
            log.exception("a container would not load")
        finally:
            if owns_connection:
                conn.close()

    def stored_containers(self, player, conn=None) -> None:
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            containers_by_type = {
                player.hold.container_id.container_type.value: player.hold,
                player.locker.container_id.container_type.value: player.locker,
            }
            self._fetch_container_systems(conn, player.user_id_of(), containers_by_type)
            self._fetch_container_countables(conn, player, containers_by_type)
        except Exception:
            log.exception("the containers would not load")
        finally:
            if owns_connection:
                conn.close()
