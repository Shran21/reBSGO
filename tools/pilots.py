#!/usr/bin/env python3
# github.com/Shran21
"""Pilot accounts: passwords, admin roles, and where a pilot next appears.

    tools/pilots.py list
    tools/pilots.py password Tuser
    tools/pilots.py password Tuser --password secret
    tools/pilots.py remove Tuser
    tools/pilots.py place teszt3 44
    tools/pilots.py roles Tuser
    tools/pilots.py roles Tuser --grant Developer,Console
    tools/pilots.py roles Tuser --revoke GodMode

A password may be passed on the command line, but by default it is asked for
and never echoed: whatever is typed as an argument lands in the shell history
and shows up in the process list.
"""

from __future__ import annotations

import argparse
import time
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rebsgo.admission import JelszoHiba, Jelszotar  # noqa: E402
from rebsgo.store.data_source import DataSource  # noqa: E402


def _tar(args) -> Jelszotar:
    return Jelszotar(DataSource(args.db))


def lista(args) -> int:
    sorok = _tar(args).pilotak()
    if not sorok:
        print("No pilot has a password yet.")
        return 0
    print(f"{'id':>10}  {'name':<20} set at")
    for pilota, nev, mikor in sorok:
        print(f"{pilota:>10}  {nev:<20} {mikor}")
    return 0


def _feloldas(tar, megadott):
    azonosito = tar.azonosito(megadott)
    if azonosito is None:
        print(f"no such pilot: {megadott}", file=sys.stderr)
    return azonosito


def jelszo(args) -> int:
    tar = _tar(args)
    azonosito = _feloldas(tar, args.pilot)
    if azonosito is None:
        return 1
    titok = args.password
    if titok is None:
        titok = getpass.getpass("password: ")
        if titok != getpass.getpass("once more: "):
            print("The two do not match.", file=sys.stderr)
            return 1
    try:
        tar.beallit(azonosito, titok)
    except JelszoHiba as hiba:
        print(hiba, file=sys.stderr)
        return 1
    print(f"password set for {args.pilot}.")
    return 0


def torol(args) -> int:
    tar = _tar(args)
    azonosito = _feloldas(tar, args.pilot)
    if azonosito is None:
        return 1
    if tar.torol(azonosito):
        print(f"password taken from {args.pilot}; they cannot log in with it now.")
    else:
        print(f"{args.pilot} had no password.")
    return 0


def jogok(args) -> int:
    from rebsgo.vocabulary.pilot import ServerRoles

    tar = _tar(args)
    azonosito = _feloldas(tar, args.pilot)
    if azonosito is None:
        return 1

    def bitek(felsorolas: str) -> int:
        osszeg = 0
        for nev in (r.strip() for r in felsorolas.split(",") if r.strip()):
            szerep = getattr(ServerRoles, nev, None)
            if szerep is None:
                ismert = ", ".join(x.name for x in ServerRoles if x.name != "None_")
                print(f"no such role: {nev}\nwhat there is: {ismert}")
                raise SystemExit(2)
            osszeg |= szerep.value
        return osszeg

    forras = DataSource(args.db)
    with forras.connection() as conn:
        sor = conn.execute("SELECT name, roles_bits FROM pilots WHERE id=?",
                           (azonosito,)).fetchone()
        if sor is None:
            print(f"{args.pilot} has no row in the pilots table yet "
                  f"(one login writes it)")
            return 1
        nev, mostani = sor["name"], sor["roles_bits"]

        uj_ertek = mostani
        if args.grant:
            uj_ertek |= bitek(args.grant)
        if args.revoke:
            uj_ertek &= ~bitek(args.revoke)

        if uj_ertek != mostani:
            conn.execute("UPDATE pilots SET roles_bits=? WHERE id=?", (uj_ertek, azonosito))
            conn.commit()

    def kifejt(ertek: int) -> str:
        nevek = [x.name for x in ServerRoles
                 if x.value and x.value != 0 and ertek & x.value]
        return " | ".join(nevek) if nevek else "no roles"

    if uj_ertek == mostani:
        print(f"{nev} ({azonosito}): {kifejt(mostani)}")
    else:
        print(f"{nev} ({azonosito}): {kifejt(mostani)}  ->  {kifejt(uj_ertek)}")
        print("the server picks this up at their next login")
    return 0


def hely(args) -> int:
    tar = _tar(args)
    azonosito = _feloldas(tar, args.pilot)
    if azonosito is None:
        return 1
    forras = DataSource(args.db)

    def hol_all():
        with forras.connection() as conn:
            sor = conn.execute(
                "SELECT sector_id, place, previous_place FROM last_seen WHERE player_id=?",
                (azonosito,)).fetchone()
        return (sor["sector_id"], sor["place"], sor["previous_place"]) if sor else None

    def beallit():
        with forras.connection() as conn:
            conn.execute(
                "UPDATE last_seen SET sector_id=?, place=4, "
                "previous_place=1 WHERE player_id=?",
                (args.sector, azonosito))
            conn.execute("DELETE FROM boosts WHERE player_id=?", (azonosito,))

    kivant = (args.sector, 4, 1)
    for _ in range(20):
        beallit()
        time.sleep(0.5)
        if hol_all() == kivant:
            break
    else:
        print("warning: the place did not hold;", hol_all(), "instead of", kivant)

    print(f"{args.pilot} starts in sector {args.sector}, in space, with no boosts.")
    return 0


def main() -> int:
    ertelmezo = argparse.ArgumentParser(description=__doc__,
                                        formatter_class=argparse.RawDescriptionHelpFormatter)
    ertelmezo.add_argument("--db", default="./sqlite/bgo_server.db",
                           help="path to the database")
    alparancsok = ertelmezo.add_subparsers(dest="parancs", required=True)

    alparancsok.add_parser("list", help="who has a password").set_defaults(fut=lista)

    beallit = alparancsok.add_parser("password", help="set or change a password")
    beallit.add_argument("pilot", help="pilot name or id")
    beallit.add_argument("--password", default=None,
                         help="left out, it is asked for instead - which is safer")
    beallit.set_defaults(fut=jelszo)

    hova = alparancsok.add_parser("place", help="where they appear at their next login")
    hova.add_argument("pilot", help="pilot name or id")
    hova.add_argument("sector", type=int)
    hova.set_defaults(fut=hely)

    szerepek = alparancsok.add_parser("roles", help="show or change admin roles")
    szerepek.add_argument("pilot", help="pilot name or id")
    szerepek.add_argument("--grant", default=None,
                          help="comma separated role names, e.g. Developer,Console")
    szerepek.add_argument("--revoke", default=None,
                          help="comma separated role names")
    szerepek.set_defaults(fut=jogok)

    torles = alparancsok.add_parser("remove", help="take a password away")
    torles.add_argument("pilot", help="pilot name or id")
    torles.set_defaults(fut=torol)

    args = ertelmezo.parse_args()
    return args.fut(args)


if __name__ == "__main__":
    raise SystemExit(main())
