# github.com/Shran21

from __future__ import annotations

import re

ELDOBANDO = (
    "container_types",
    "factions",
    "game_locations",
    "guild_roles",
    "settings_value_types",
)

UJ_NEVEK = {
    "players": "pilots",
    "shipSlots": "slot_state",
    "factor": "boosts",
    "counters": "tallies",
    "caps": "limits",
    "locations": "last_seen",
    "hangars": "hangar_state",
    "mails": "mail",
    "containers": "container_slots",
    "item_countables": "stacks",
    "ship_systems": "installed_systems",
    "avatar_items": "avatar_parts",
    "input_bindings_values": "key_bindings",
    "skillbooks": "skill_books",
    "mission_books": "mission_logs",
    "player_missions": "pilot_missions",
    "player_skills": "pilot_skills",
    "players_hangar_ships": "owned_ships",
    "players_completed_tutorials": "tutorials_done",
    "players_settings_value_bytes": "client_options",
    "guild_member_infos": "guild_members",
    "guild_rank_definitions": "guild_ranks",
}

UJ_OSZLOPOK = {
    "guild_members": {"guild_roles_id": "role", "players_id": "player_id"},
    "container_slots": {"container_types_id": "kind", "players_id": "player_id"},
    "last_seen": {"game_locations_id": "place",
         "previous_game_locations_id": "previous_place",
         "players_id": "player_id"},
    "pilots": {"faction_id": "faction"},
    "avatar_parts": {"players_id": "player_id"},
    "boosts": {"players_id": "player_id"},
    "client_options": {"players_id": "player_id"},
    "hangar_state": {"players_id": "player_id"},
    "installed_systems": {"players_id": "player_id", "containers_id": "container_id"},
    "key_bindings": {"players_id": "player_id"},
    "limits": {"players_id": "player_id"},
    "mail": {"players_id": "player_id"},
    "owned_ships": {"players_id": "player_id"},
    "slot_state": {"players_id": "player_id"},
    "stacks": {"players_id": "player_id", "containers_id": "container_id"},
    "tallies": {"players_id": "player_id"},
    "tutorials_done": {"players_id": "player_id"},
}

UJRAEPITENDO = ("players", "containers", "guild_rank_definitions", "locations")


def uj_nev(regi: str) -> str:
    return UJ_NEVEK.get(regi, regi)


def tablak(conn) -> dict[str, str]:
    return {nev: sql for nev, sql in conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL")}


def oszlopok(conn, tabla: str) -> list[str]:
    return [r[1] for r in conn.execute(f'PRAGMA table_info("{tabla}")')]


def sorszam(conn) -> dict[str, int]:
    return {nev: conn.execute(f'SELECT count(*) FROM "{nev}"').fetchone()[0]
            for nev in tablak(conn)}


def _fk_nelkul(sql: str) -> str:
    for holt in ELDOBANDO:
        while True:
            talalat = re.search(
                rf",\s*FOREIGN\s+KEY\s*\([^)]*\)\s*REFERENCES\s+{holt}\s*\([^)]*\)"
                rf"(?:\s+ON\s+\w+\s+\w+(?:\s+\w+)?)*",
                sql, re.I | re.S)
            if talalat is None:
                break
            sql = sql[:talalat.start()] + sql[talalat.end():]
    return sql


def terv(conn) -> list[str]:
    meglevo = tablak(conn)
    lepesek: list[str] = []

    for nev in UJRAEPITENDO:
        if nev not in meglevo:
            continue
        tiszta = _fk_nelkul(meglevo[nev])
        if tiszta == meglevo[nev]:
            continue
        oszlop_lista = ", ".join(f'"{o}"' for o in oszlopok(conn, nev))
        atmeneti = f"{nev}__uj"
        lepesek += [
            re.sub(rf'CREATE TABLE\s+"?{nev}"?', f'CREATE TABLE "{atmeneti}"',
                   tiszta, count=1, flags=re.I),
            f'INSERT INTO "{atmeneti}" ({oszlop_lista}) SELECT {oszlop_lista} FROM "{nev}"',
            f'DROP TABLE "{nev}"',
            f'ALTER TABLE "{atmeneti}" RENAME TO "{nev}"',
        ]

    for holt in ELDOBANDO:
        if holt in meglevo:
            lepesek.append(f'DROP TABLE "{holt}"')

    for regi in UJ_NEVEK:
        if regi in meglevo and uj_nev(regi) not in meglevo:
            lepesek.append(f'ALTER TABLE "{regi}" RENAME TO "{uj_nev(regi)}"')

    for tabla, cserek in UJ_OSZLOPOK.items():
        regi_tabla = next((r for r, u in UJ_NEVEK.items() if u == tabla), tabla)
        jelen_tabla = tabla if tabla in meglevo else regi_tabla
        if jelen_tabla not in meglevo:
            continue
        jelenlegi = set(oszlopok(conn, jelen_tabla))
        for regi_oszlop, uj_oszlop in cserek.items():
            if regi_oszlop in jelenlegi and uj_oszlop not in jelenlegi:
                lepesek.append(
                    f'ALTER TABLE "{tabla}" RENAME COLUMN "{regi_oszlop}" TO "{uj_oszlop}"')

    return lepesek
