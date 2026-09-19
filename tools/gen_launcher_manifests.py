#!/usr/bin/env python3
# github.com/Shran21
"""Write the file list the launcher's file check runs against.

The launcher fetches this list from the door, sums every named file in the
player's client folder, and fetches whatever is missing or wrong. The list
is plain JSON - a name, an MD5 and a size per file - and each download url
is `<base url><name>`.

The comparison cuts both ways, and that is the thing to hold on to:

  * a file the list names but the player lacks - or holds in a different
    version - is downloaded from this server;
  * a file the player has and the list does NOT name is treated as
    obsolete and DELETED from their folder.

So the list should be made from a clean install. Our launcher never
deletes - an unlisted file on a player's machine is simply left alone - but
a listed leftover would make every player download it. The tool refuses to
run quietly past files that look like leftovers; `--skip-suspect` leaves them
out of the list (what a distribution wants), `--gyanusakkal` puts them in.

    python3 tools/gen_launcher_manifests.py --client /path/to/client/live \\
                                            --out /path/to/serve --skip-suspect

The messages follow the machine's language: Hungarian on a Hungarian locale,
English everywhere else. The older Hungarian flag spellings still work.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import sys

GYANUS = ("*.bak", "*.bak-*", "*.bak.*", "*.log", "*.tmp", "*.old", "*.orig",
          "*.cmd", "*.bat", "*.zip", "*.7z", "*.rar", "output_log.txt")


def md5_je(ut: pathlib.Path) -> str:
    kivonat = hashlib.md5()
    with ut.open("rb") as f:
        for darab in iter(lambda: f.read(1 << 20), b""):
            kivonat.update(darab)
    return kivonat.hexdigest()


def gyanus_e(ut: pathlib.Path) -> bool:
    return any(ut.match(minta) for minta in GYANUS)


def leltar(gyoker: pathlib.Path) -> tuple[list, list]:
    tetelek, gyanusak = [], []
    for ut in sorted(gyoker.rglob("*")):
        if not ut.is_file():
            continue
        if gyanus_e(ut):
            gyanusak.append(ut)
        tetelek.append({
            "Name": ut.relative_to(gyoker).as_posix(),
            "Hash": md5_je(ut),
            "Size": ut.stat().st_size,
        })
    return tetelek, gyanusak


def kiir(tetelek: list, cel: pathlib.Path) -> None:
    cel.parent.mkdir(parents=True, exist_ok=True)
    cel.write_text(json.dumps({"Resources": tetelek}, indent=1), encoding="utf-8")


def _magyarul() -> bool:
    beallitas = (os.environ.get("REBSGO_LANG") or os.environ.get("LC_ALL")
                 or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or "")
    return beallitas.lower().startswith("hu")


def t(hu: str, en: str) -> str:
    return hu if _magyarul() else en


def main() -> int:
    ertelmezo = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ertelmezo.add_argument("--client", "--kliens", dest="client", required=True,
                           help="the client folder the game runs from (…/client/live)")
    ertelmezo.add_argument("--out", "--hova", dest="out", required=True,
                           help="where to write client/manifest.json")
    ertelmezo.add_argument("--with-suspect", "--gyanusakkal", dest="with_suspect",
                           action="store_true",
                           help="list the leftover-looking files too, instead of stopping")
    ertelmezo.add_argument("--skip-suspect", "--kihagyva", dest="skip_suspect",
                           action="store_true",
                           help="leave the leftover-looking files out of the list "
                                "(they will be deleted from players' folders)")
    beallitas = ertelmezo.parse_args()

    hova = pathlib.Path(beallitas.out)
    baj = False
    for nev, honnan in (("client", beallitas.client),):
        gyoker = pathlib.Path(honnan)
        if not gyoker.is_dir():
            print(t(f"nincs ilyen mappa: {gyoker}", f"no such folder: {gyoker}"))
            return 2
        tetelek, gyanusak = leltar(gyoker)
        if gyanusak and beallitas.skip_suspect:
            hagyd = {ut.relative_to(gyoker).as_posix() for ut in gyanusak}
            tetelek = [t for t in tetelek if t["Name"] not in hagyd]
            minta = f"({', '.join(sorted(hagyd)[:3])}{'…' if len(hagyd) > 3 else ''})"
            print(t(f"{nev}: {len(hagyd)} fájl kihagyva a listából {minta}",
                    f"{nev}: {len(hagyd)} files left out of the list {minta}"))
            gyanusak = []
        if gyanusak and not beallitas.with_suspect:
            print(t(f"\n{nev}: {len(gyanusak)} fájl nem néz ki a játék részének:",
                    f"\n{nev}: {len(gyanusak)} files do not look like part of the game:"))
            for ut in gyanusak[:12]:
                print("   ", ut)
            if len(gyanusak) > 12:
                print(t(f"    … és még {len(gyanusak) - 12}",
                        f"    … and {len(gyanusak) - 12} more"))
            print(t("  Vidd ki őket a mappából, vagy add hozzá a --with-suspect kapcsolót,\n"
                    "  ha tényleg részei a kiosztásnak. Ha bent maradnak és NEM kerülnek a\n"
                    "  listába, a launcher a játékosok gépéről törli az ilyen fájlokat.",
                    "  Move them out of the folder, or add --with-suspect if they really\n"
                    "  belong to the distribution. Left in place and NOT listed, the\n"
                    "  launcher deletes such files from the players' machines."))
            baj = True
            continue
        meret = sum(t["Size"] for t in tetelek)
        kiir(tetelek, hova / nev / "manifest.json")
        cel = hova / nev / "manifest.json"
        print(t(f"{nev}: {len(tetelek)} fájl, {meret / (1 << 20):.0f} MB -> {cel}",
                f"{nev}: {len(tetelek)} files, {meret / (1 << 20):.0f} MB -> {cel}"))
    return 1 if baj else 0


if __name__ == "__main__":
    sys.exit(main())
