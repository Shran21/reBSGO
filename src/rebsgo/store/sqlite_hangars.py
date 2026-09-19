# github.com/Shran21
from __future__ import annotations

import logging

from rebsgo.store.db_rows import HangarRow, ShipRow, SlotRow

log = logging.getLogger(__name__)


class SqliteHangars:
    def __init__(self, data_source):
        self._data_source = data_source

    def stored_hangar(self, player_id: int, conn=None):
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            sor = conn.execute("SELECT * FROM hangar_state WHERE player_id=?", (player_id,)).fetchone()
            if sor is None:
                raise RuntimeError('pilot loaded without an active-ship index')
            active_index = sor["active_index"]
            player_hangar_ships_infos = self._fetch_player_hangar_ship_infos(conn, player_id)
            return HangarRow(active_index, player_hangar_ships_infos)
        except Exception:
            log.exception("the hangar would not load")
        finally:
            if owns_connection:
                conn.close()
        return None

    @staticmethod
    def _fetch_slots_by_ship(conn, player_id: int) -> dict[int, list]:
        slots_by_ship: dict[int, list] = {}
        cursor = conn.execute("SELECT * FROM slot_state WHERE player_id=?", (player_id,))
        for sor in cursor:
            ship_id = sor["ship_id"]
            server_id = sor["server_id"]
            guid = sor["guid"]
            durability = sor["durability"]
            current_consumable_guid = sor["current_consumable_guid"]
            slots_by_ship.setdefault(ship_id, []).append(
                SlotRow(server_id, guid, durability, current_consumable_guid))
        return slots_by_ship

    def _fetch_player_hangar_ship_infos(self, conn, player_id: int):
        try:
            slots_by_ship = self._fetch_slots_by_ship(conn, player_id)
            cursor = conn.execute("SELECT * FROM owned_ships WHERE player_id=?", (player_id,))
            ship_info_fetch_results = []
            for sor in cursor.fetchall():
                server_id = sor["server_id"]
                guid = sor["guid"]
                durability = sor["durability"]
                name = sor["name"]

                slots_fetched = slots_by_ship.get(server_id, [])
                log.debug(f'player {player_id} reading a hangar ship back {guid} {server_id}')

                ship_info_fetch_results.append(ShipRow(guid, server_id, durability, name, slots_fetched))
            return ship_info_fetch_results
        except Exception:
            log.exception("the berthed ships would not load")
        return None

    def write_hangar(self, player, conn=None) -> None:
        hangar = player.hangar_of()
        owns_connection = conn is None
        if owns_connection:
            conn = self._data_source.connection()
        try:
            active = hangar.active_ship()
            active_index = active.server_id if active is not None else 0
            if active_index == 12:
                active_index = 0
                for s in hangar.all_hangar_ships():
                    if s.server_id != 12:
                        active_index = s.server_id
                        break
            ship_rows = []
            slot_rows = []
            for ship in hangar.all_hangar_ships():
                if ship.server_id == 12:
                    continue
                log.debug(f'persisting a hangar ship {player.user_id_of()} to db {ship.card_guid_of()} {ship.server_id}')
                ship_rows.append((player.user_id_of(), ship.server_id, ship.card_guid_of(),
                                  ship.durability, ship.name))
                for rekesz in ship.ship_slots.values():
                    rendszer = rekesz.ship_system
                    if rendszer is None:
                        continue
                    current_consumable = rekesz.current_consumable
                    current_consumable_guid = 0
                    if current_consumable is not None and current_consumable.item_countable is not None:
                        current_consumable_guid = current_consumable.item_countable.card_guid_of()
                    slot_rows.append((player.user_id_of(), ship.server_id, rendszer.server_id,
                                      rendszer.card_guid_of(), rendszer.durability, current_consumable_guid))

            if owns_connection:
                conn.execute("BEGIN")
            conn.execute("REPLACE INTO hangar_state(player_id, active_index) VALUES (?, ?)",
                         (player.user_id_of(), active_index))
            conn.execute("DELETE FROM owned_ships WHERE player_id=?", (player.user_id_of(),))
            conn.execute("DELETE FROM slot_state WHERE player_id=?", (player.user_id_of(),))
            conn.executemany("REPLACE INTO owned_ships(player_id, server_id, guid, durability, name)"
                             " VALUES (?, ?, ?, ?, ?)", ship_rows)
            conn.executemany("REPLACE INTO slot_state(player_id, ship_id, server_id, guid, durability, "
                             "current_consumable_guid) VALUES (?, ?, ?, ?, ?, ?)", slot_rows)
            if owns_connection:
                conn.commit()
        except Exception:
            if owns_connection:
                conn.rollback()
            log.exception("the hangar would not save")
            if not owns_connection:
                raise
        finally:
            if owns_connection:
                conn.close()
