#!/usr/bin/env python3
# github.com/Shran21
"""Pilot accounts: making them, passwords, admin roles, and where a pilot next
appears.

    tools/pilots.py list
    tools/pilots.py admins
    tools/pilots.py create Tuser
    tools/pilots.py create Tuser --grant Developer,Console
    tools/pilots.py password Tuser
    tools/pilots.py password Tuser --password secret
    tools/pilots.py remove Tuser
    tools/pilots.py place teszt3 44
    tools/pilots.py roles Tuser
    tools/pilots.py roles Tuser --grant Developer,Console
    tools/pilots.py roles Tuser --revoke GodMode

Every command works on the server's own database - REBSGO_DB from the .env of
the tree, or else sqlite/bgo_server.db in it - wherever it is started from;
--db points it somewhere else.

A password may be passed on the command line, but by default it is asked for
and never echoed: whatever is typed as an argument lands in the shell history
and shows up in the process list.
"""

from __future__ import annotations

import argparse
import time
import getpass
import os
import sys
from pathlib import Path

_FA = Path(__file__).resolve().parents[1]
_INDULASI_HELY = Path.cwd()
sys.path.insert(0, str(_FA / "src"))

# The server runs from the root of the tree: that is where it finds its .env,
# and where a relative REBSGO_DB starts from. This tool has to see the same
# file, and it has to before the imports below, because the database layer
# reads its settings as it loads. Started anywhere else, it would open - and
# quietly create - a database of its own wherever the shell happened to be.
os.chdir(_FA)

from rebsgo.admission import JelszoHiba, Jelszotar  # noqa: E402
from rebsgo.store.data_source import DataSource  # noqa: E402


def _adatbazis(megadott: str | None) -> str:
    """The file the server itself opens, unless --db names another.

    The server's own rule: REBSGO_DB, or else ./sqlite/bgo_server.db, counted
    from the root of the tree. A --db typed on the command line counts from
    where it was typed, as any path argument does.
    """

    if megadott is not None:
        return str(_INDULASI_HELY / megadott)
    from rebsgo.config.config import Config
    return str(_FA / (Config.instance().string("rebsgo.db") or "./sqlite/bgo_server.db"))


def _tar(args) -> Jelszotar:
    return Jelszotar(DataSource(args.db))


def _szerep_bitek(felsorolas: str) -> int:
    from rebsgo.vocabulary.pilot import ServerRoles

    osszeg = 0
    for nev in (r.strip() for r in felsorolas.split(",") if r.strip()):
        szerep = ServerRoles.__members__.get(nev)
        if szerep is None:
            ismert = ", ".join(x.name for x in ServerRoles if x.name != "None_")
            print(f"no such role: {nev}\nwhat there is: {ismert}", file=sys.stderr)
            raise SystemExit(2)
        osszeg |= szerep.value
    return osszeg


def _szerep_nevek(ertek: int) -> str:
    from rebsgo.vocabulary.pilot import ServerRoles

    nevek = [x.name for x in ServerRoles
             if x.value and x.value != 0 and ertek & x.value]
    return " | ".join(nevek) if nevek else "no roles"


def _titok(megadott: str | None) -> str | None:
    if megadott is not None:
        return megadott
    try:
        titok = getpass.getpass("password: ")
        if titok != getpass.getpass("once more: "):
            print("The two do not match.", file=sys.stderr)
            return None
    except (EOFError, KeyboardInterrupt):
        print(file=sys.stderr)
        return None
    return titok


def lista(args) -> int:
    sorok = _tar(args).pilotak()
    if not sorok:
        print("No pilot has a password yet.")
        return 0
    print(f"{'id':>10}  {'name':<20} set at")
    for pilota, nev, mikor in sorok:
        print(f"{pilota:>10}  {nev:<20} {mikor}")
    return 0


def adminok(args) -> int:
    """Who can run the panel: the Developer role, and a password to sign in.

    The installer asks it whether a first admin is still to be made, so it
    answers in its exit status as well: 0 when there is one, 1 when nobody.
    """

    from rebsgo.vocabulary.pilot import ServerRoles

    forras = DataSource(args.db)
    with forras.connection() as conn:
        sorok = conn.execute(
            "SELECT p.id, p.name, p.roles_bits FROM pilots p "
            "JOIN pilot_passwords j ON j.player_id = p.id "
            "WHERE p.roles_bits & ? ORDER BY p.id",
            (ServerRoles.Developer.value,)).fetchall()
    if not sorok:
        print("Nobody can run the panel yet: no pilot has both a password "
              "and the Developer role.")
        return 1
    print(f"{'id':>10}  {'name':<20} roles")
    for sor in sorok:
        print(f"{sor['id']:>10}  {sor['name']:<20} "
              f"{_szerep_nevek(int(sor['roles_bits'] or 0))}")
    return 0


def letrehoz(args) -> int:
    """Make an account, the way the launcher's registration makes one.

    A fresh server needs it for its first admin: the panel lets in only a
    Developer or a Console, and only a Developer can make an account there.
    The checks are the registration's own - the name rules, a name already
    taken, the length of the password - and so is the account: a bare one,
    whose first login goes through the faction choice and the avatar.
    """

    from rebsgo.admission.enrolment import Anyakonyv, RegisztracioElutasitva
    from rebsgo.protocol.pilot.pilot_steps import NameRules

    nev = args.pilot.strip()
    # Whatever can be refused without the password is refused before it is
    # asked for, and a mistyped role before the account exists. The
    # registration checks the name again, under its own lock.
    bitek = _szerep_bitek(args.grant) if args.grant else 0
    if not NameRules._name_safe_check(nev):
        print("a name is 3-20 letters, digits or underscores", file=sys.stderr)
        return 1
    forras = DataSource(args.db)
    with forras.connection() as conn:
        foglalt = conn.execute("SELECT 1 FROM pilots WHERE name=? COLLATE NOCASE",
                               (nev,)).fetchone()
    if foglalt is not None:
        print(f"this name is already taken: {nev}", file=sys.stderr)
        return 1

    titok = _titok(args.password)
    if titok is None:
        return 1
    try:
        azonosito = Anyakonyv(forras, Jelszotar(forras)).felvesz(
            nev, titok, "tools/pilots.py")
    except (RegisztracioElutasitva, JelszoHiba) as hiba:
        print(hiba, file=sys.stderr)
        return 1

    if bitek:
        with forras.connection() as conn:
            conn.execute("UPDATE pilots SET roles_bits=? WHERE id=?", (bitek, azonosito))
            conn.commit()
    print(f"{nev} ({azonosito}) created: {_szerep_nevek(bitek)}")
    print("the first login takes them through the faction choice and the avatar")
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
    titok = _titok(args.password)
    if titok is None:
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
    """Show a pilot's admin roles, or change them.

    The roles live in the `pilots.roles_bits` column, which is where the
    server reads them and the only place they are written down. Handled by
    name, because the bit pattern says nothing about what it permits.
    """

    tar = _tar(args)
    azonosito = _feloldas(tar, args.pilot)
    if azonosito is None:
        return 1

    forras = DataSource(args.db)
    with forras.connection() as conn:
        sor = conn.execute("SELECT name, roles_bits FROM pilots WHERE id=?",
                           (azonosito,)).fetchone()
        if sor is None:
            print(f"no such pilot: {args.pilot}", file=sys.stderr)
            return 1
        nev, mostani = sor["name"], sor["roles_bits"]

        uj_ertek = mostani
        if args.grant:
            uj_ertek |= _szerep_bitek(args.grant)
        if args.revoke:
            uj_ertek &= ~_szerep_bitek(args.revoke)

        if uj_ertek != mostani:
            conn.execute("UPDATE pilots SET roles_bits=? WHERE id=?", (uj_ertek, azonosito))
            conn.commit()

    if uj_ertek == mostani:
        print(f"{nev} ({azonosito}): {_szerep_nevek(mostani)}")
    else:
        print(f"{nev} ({azonosito}): {_szerep_nevek(mostani)}  ->  {_szerep_nevek(uj_ertek)}")
        print("the server picks this up at their next login")
    return 0


def hely(args) -> int:
    """Put a pilot into a known state for the next recording.

    The bench needs it. The probe plays for real - it docks, jumps, moves and
    collects boosts along the way - so at the end of a run it stands somewhere
    else than it started. Two runs only compare if both begin from the same
    place in the same state.

    The boosts go because they expire: restored from a saved state they are
    already old, the server hands out fresh ones, and the client then receives
    a different list although nothing in the code changed.
    """

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

    # The server writes the pilot out on *logout*, which lands after the
    # recording process has already exited - sometimes seconds after. Waiting
    # is not enough: write first and the server overwrites it. So the row is
    # read back, and while it is not what we wrote, we write it again.
    # `previous_place` counts too, and it is the one that drifts: logout
    # records the *docked* state while loading reads the previous place. Leave
    # `Room` there and the pilot wakes at a station in the faction's home
    # sector - and the recording measures something else entirely.
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
    ertelmezo.add_argument("--db", default=None,
                           help="path to the database; left out, the server's own")
    alparancsok = ertelmezo.add_subparsers(dest="parancs", required=True)

    alparancsok.add_parser("list", help="who has a password").set_defaults(fut=lista)

    alparancsok.add_parser("admins", help="who can run the panel (exit status 1: nobody)"
                           ).set_defaults(fut=adminok)

    uj = alparancsok.add_parser("create", help="make an account, as the launcher's "
                                               "registration does")
    uj.add_argument("pilot", help="the new pilot's name")
    uj.add_argument("--password", default=None,
                    help="left out, it is asked for instead - which is safer")
    uj.add_argument("--grant", default=None,
                    help="comma separated role names, e.g. Developer,Console")
    uj.set_defaults(fut=letrehoz)

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
    args.db = _adatbazis(args.db)
    # Only `create` may bring a database into being - on a fresh install that
    # is how the first admin gets in before the server ever started. Anything
    # else finding no file was pointed at the wrong place.
    if args.fut is not letrehoz and not Path(args.db).is_file():
        print(f"there is no database at {args.db}\n"
              f"(the server writes it on its first start, and so does `create`)",
              file=sys.stderr)
        return 1
    return args.fut(args)


if __name__ == "__main__":
    raise SystemExit(main())
