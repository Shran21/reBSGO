# github.com/Shran21

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

ORA_MASODPERC = 3600.0


class Oszlop:
    def ertek(self, szamlalok: dict, tapasztalat: float) -> float:
        raise NotImplementedError

    def szamlalo_guidok(self) -> set:
        return set()


class Szamlalo(Oszlop):
    def __init__(self, guid: int):
        self.guid = guid

    def ertek(self, szamlalok, tapasztalat):
        return float(szamlalok.get(self.guid, 0) or 0)

    def szamlalo_guidok(self):
        return {self.guid}


class Osszeg(Oszlop):
    def __init__(self, tagok):
        self.tagok = list(tagok)

    def ertek(self, szamlalok, tapasztalat):
        return sum(t.ertek(szamlalok, tapasztalat) for t in self.tagok)

    def szamlalo_guidok(self):
        return set().union(*(t.szamlalo_guidok() for t in self.tagok)) if self.tagok else set()


class Arany(Oszlop):
    def __init__(self, szamlalo: Oszlop, nevezo: Oszlop):
        self.szamlalo = szamlalo
        self.nevezo = nevezo

    def ertek(self, szamlalok, tapasztalat):
        oszto = self.nevezo.ertek(szamlalok, tapasztalat)
        if oszto <= 0:
            return 0.0
        return self.szamlalo.ertek(szamlalok, tapasztalat) / oszto

    def szamlalo_guidok(self):
        return self.szamlalo.szamlalo_guidok() | self.nevezo.szamlalo_guidok()


class OrankentiRata(Oszlop):
    def __init__(self, mibol: Oszlop, ido_guid: int):
        self.mibol = mibol
        self.ido_guid = ido_guid

    def ertek(self, szamlalok, tapasztalat):
        masodperc = float(szamlalok.get(self.ido_guid, 0) or 0)
        if masodperc <= 0:
            return 0.0
        return self.mibol.ertek(szamlalok, tapasztalat) / (masodperc / ORA_MASODPERC)

    def szamlalo_guidok(self):
        return self.mibol.szamlalo_guidok() | {self.ido_guid}


class Tapasztalat(Oszlop):
    def ertek(self, szamlalok, tapasztalat):
        return float(tapasztalat or 0)


class Nulla(Oszlop):
    def ertek(self, szamlalok, tapasztalat):
        return 0.0


def oszlop_json(obj) -> Oszlop:
    if not isinstance(obj, dict):
        log.warning("ranking column is not an object: %r", obj)
        return Nulla()
    fajta = obj.get("kind")
    if fajta == "counter":
        return Szamlalo(int(obj.get("guid", 0)))
    if fajta == "sum":
        return Osszeg(oszlop_json(t) for t in obj.get("of", []))
    if fajta == "ratio":
        return Arany(oszlop_json(obj.get("of")), oszlop_json(obj.get("per")))
    if fajta == "rate_per_hour":
        return OrankentiRata(oszlop_json(obj.get("of")), int(obj.get("per", 0)))
    if fajta == "experience":
        return Tapasztalat()
    log.warning("ranking column of unknown kind: %r", fajta)
    return Nulla()


class Ranglista:
    def __init__(self, kulcs: str, oszlopok, rendezo: Oszlop | None = None):
        self.kulcs = kulcs
        self.oszlopok = (list(oszlopok) + [Nulla(), Nulla(), Nulla()])[:3]
        self.rendezo = rendezo or self.oszlopok[0]

    def pontszamok(self, szamlalok: dict, tapasztalat: float) -> tuple:
        return tuple(o.ertek(szamlalok, tapasztalat) for o in self.oszlopok)

    def rendezo_ertek(self, szamlalok: dict, tapasztalat: float) -> float:
        return self.rendezo.ertek(szamlalok, tapasztalat)

    @property
    def tapasztalatot_olvas(self) -> bool:
        return any(isinstance(o, Tapasztalat) for o in self.oszlopok) \
            or isinstance(self.rendezo, Tapasztalat)

    def szamlalo_guidok(self) -> set:
        egyben = set().union(*(o.szamlalo_guidok() for o in self.oszlopok))
        return egyben | self.rendezo.szamlalo_guidok()

    @staticmethod
    def from_json(obj: dict) -> "Ranglista":
        rendezo = obj.get("sort")
        return Ranglista(obj.get("key", ""),
                         [oszlop_json(o) for o in obj.get("columns", [])],
                         oszlop_json(rendezo) if rendezo else None)
