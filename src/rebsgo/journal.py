# github.com/Shran21

from __future__ import annotations

import logging
import logging.handlers
import os
import threading
from pathlib import Path

AUDIT = "audit"

_TERULETEK = {
    "rebsgo.admission": "admission",
    "rebsgo.chat.client": "chat",
    "rebsgo.chat.server": "chat",
    "rebsgo.world.galaxy": "world",
    "rebsgo.pilots.state": "pilot",
    "rebsgo.runtime.incoming_loop": "wire",
    "rebsgo.protocol": "wire",
    "rebsgo.pilots.standings": "pilot",
    "rebsgo.world.sectors": "sector",
    "rebsgo.world.objects": "world",
    "rebsgo.runtime.seat": "pilot",
    "rebsgo.runtime.pilot_roster": "pilot",
    "rebsgo.runtime.sweeps": "pilot",
    "rebsgo.wire.bytes": "wire",
    "rebsgo.wire.links": "wire",
    "rebsgo.store": "boot",
    "rebsgo.gamedata": "boot",
    "rebsgo.native": "boot",
    "rebsgo.main": "boot",
    "rebsgo.startup": "boot",
    "rebsgo.schedule": "boot",
    "rebsgo.game_metrics": "boot",
    "rebsgo.audit": AUDIT,
}
_ALAPTERULET = "boot"
_TERULET_SZELESSEG = max(len(nev) for nev in set(_TERULETEK.values()))

_UZENET_SZELESSEG = 64

_JELOLES = {
    logging.DEBUG: "-",
    logging.INFO: " ",
    logging.WARNING: "!",
    logging.ERROR: "X",
    logging.CRITICAL: "X",
}

_SZINTEK = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "warn": logging.WARNING,
    "error": logging.ERROR,
}


_terulet_szuro: "_TeruletSzuro | None" = None


def szintek() -> dict:
    hatarok = {} if _terulet_szuro is None else dict(_terulet_szuro._hatarok)
    return {
        "level": logging.getLevelName(logging.getLogger().level).lower(),
        "areas": {nev: logging.getLevelName(hatar).lower()
                  for nev, hatar in sorted(hatarok.items())},
        "area_names": sorted(set(_TERULETEK.values()) | {_ALAPTERULET}),
    }


def atallit(szint_nev: str, terulet_nev: str | None = None) -> bool:
    szo = str(szint_nev or "").strip().lower()
    if terulet_nev:
        if terulet_nev not in set(_TERULETEK.values()) | {_ALAPTERULET}:
            return False
        if _terulet_szuro is None:
            return False
        if szo in ("", "default"):
            _terulet_szuro._hatarok.pop(terulet_nev, None)
            return True
        if szo not in _SZINTEK:
            return False
        _terulet_szuro._hatarok[terulet_nev] = _SZINTEK[szo]
        return True
    if szo not in _SZINTEK:
        return False
    logging.getLogger().setLevel(_SZINTEK[szo])
    return True


def audit() -> logging.Logger:
    return logging.getLogger("rebsgo.audit")


_egyszer_latott: set[str] = set()
_egyszer_zar = threading.Lock()


def eloszor(naplo: logging.Logger, kulcs: str, uzenet: str, *args) -> None:
    with _egyszer_zar:
        if kulcs in _egyszer_latott:
            return
        _egyszer_latott.add(kulcs)
    naplo.exception(uzenet, *args)


def terulet(modul: str) -> str:
    talalat = ""
    for elotag in _TERULETEK:
        if (modul == elotag or modul.startswith(elotag + ".")) and len(elotag) > len(talalat):
            talalat = elotag
    return _TERULETEK.get(talalat, _ALAPTERULET)


def _naplo_szo() -> str:
    beallitas = (os.environ.get("REBSGO_LANG") or os.environ.get("LC_ALL")
                 or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or "")
    return "napló" if beallitas.lower().startswith("hu") else "journal"


class Naplokep(logging.Formatter):
    def __init__(self, szallal: bool = False, szint: str = ""):
        super().__init__()
        self._szallal = szallal
        self._szint = szint
        self._fejlec_kiirva = False
        self._zar = threading.Lock()

    def format(self, record: logging.LogRecord) -> str:
        sorok = []
        with self._zar:
            if not self._fejlec_kiirva:
                self._fejlec_kiirva = True
                fejlec = f"---- {self.formatTime(record, '%Y-%m-%d')} "
                if self._szint:
                    fejlec += f"---- {_naplo_szo()}: {self._szint} "
                fejlec += "---- github.com/Shran21 "
                sorok.append(fejlec + "-" * max(4, 72 - len(fejlec)))
        pillanat = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        ezred = int(record.msecs)
        hely = terulet(record.name).ljust(_TERULET_SZELESSEG)
        jel = _JELOLES.get(record.levelno, "?")
        uzenet = record.getMessage()

        if self._szallal and record.threadName not in ("MainThread", None):
            uzenet = f"{uzenet}  [{record.threadName}]"

        honnan = f"@{record.filename}:{record.lineno}"
        sorok.append(f"{pillanat}.{ezred:03d} {hely} {jel} {uzenet.ljust(_UZENET_SZELESSEG)} {honnan}")

        if record.exc_info:
            sorok.append(self.formatException(record.exc_info))
        if record.stack_info:
            sorok.append(self.formatStack(record.stack_info))
        return "\n".join(sorok)


class _TeruletSzuro(logging.Filter):
    def __init__(self, hatarok: dict[str, int]):
        super().__init__()
        self._hatarok = hatarok

    def filter(self, record: logging.LogRecord) -> bool:
        hatar = self._hatarok.get(terulet(record.name))
        return hatar is None or record.levelno >= hatar


class _CsakTeruletek(logging.Filter):
    def __init__(self, teruletek: set[str], kivéve: bool = False):
        super().__init__()
        self._teruletek = teruletek
        self._kiveve = kivéve

    def filter(self, record: logging.LogRecord) -> bool:
        benne = terulet(record.name) in self._teruletek
        return not benne if self._kiveve else benne


def _szint(nev: str | None, alap: int) -> int:
    if not nev:
        return alap
    return _SZINTEK.get(nev.strip().lower(), alap)


def _beallitas(nev: str) -> str | None:
    ertek = os.environ.get(nev)
    if ertek:
        return ertek
    try:
        from rebsgo.config.config import Config
        return Config.instance().string(nev)
    except Exception:
        return None


def _terulet_hatarok() -> dict[str, int]:
    hatarok: dict[str, int] = {}
    for nev in sorted(set(_TERULETEK.values()) | {_ALAPTERULET}):
        ertek = _beallitas(f"REBSGO_LOG_{nev.upper()}")
        if ertek:
            hatarok[nev] = _szint(ertek, logging.INFO)
    return hatarok


def bekapcsol(mappa: str | None = None) -> str:
    szint = _szint(_beallitas("REBSGO_LOG"), logging.INFO)
    reszletes = szint <= logging.DEBUG

    hova = Path(mappa or _beallitas("REBSGO_LOG_DIR")
                or Path(__file__).resolve().parents[2] / "logs")
    hova.mkdir(parents=True, exist_ok=True)
    fajl = hova / "server.log"

    szint_neve = logging.getLevelName(szint).lower()

    def _kep():
        return Naplokep(szallal=reszletes, szint=szint_neve)

    def _fajl(nev: str, mb: int, fordulok: int = 5):
        kezelo = logging.handlers.RotatingFileHandler(
            hova / nev, maxBytes=mb * 1024 * 1024, backupCount=fordulok, encoding="utf-8")
        kezelo.setFormatter(_kep())
        return kezelo

    hatarok = _terulet_hatarok()
    szuro = _TeruletSzuro(hatarok)
    global _terulet_szuro
    _terulet_szuro = szuro

    kepernyo = logging.StreamHandler()
    kepernyo.setFormatter(_kep())

    szerver = _fajl("server.log", 20)
    szektor = _fajl("sector.log", 60, fordulok=6)
    belepes = _fajl("login.log", 5)
    hibak = _fajl("error.log", 5)
    audit_fajl = _fajl("audit.log", 5)

    kepernyo.addFilter(_CsakTeruletek({"sector"}, kivéve=True))
    szerver.addFilter(_CsakTeruletek({"sector"}, kivéve=True))
    szektor.addFilter(_CsakTeruletek({"sector"}))
    belepes.addFilter(_CsakTeruletek({"admission", "pilot"}))
    audit_fajl.addFilter(_CsakTeruletek({AUDIT}))
    hibak.setLevel(logging.WARNING)
    hibak.addFilter(_CsakTeruletek({AUDIT}, kivéve=True))

    kezelok = [kepernyo, szerver, szektor, belepes, hibak, audit_fajl]
    if szuro is not None:
        for kezelo in kezelok:
            kezelo.addFilter(szuro)

    gyoker = logging.getLogger()
    gyoker.setLevel(szint)
    for regi in list(gyoker.handlers):
        gyoker.removeHandler(regi)
    for kezelo in kezelok:
        gyoker.addHandler(kezelo)

    log = logging.getLogger(__name__)
    log.info('logging configured: level=%s file=%s%s', szint_neve, fajl,
             f" quieted={hatarok}" if hatarok else "")
    return str(fajl)


def hivasi_lanc(kivetel: BaseException) -> str:
    import traceback

    lanc = "".join(traceback.format_exception(
        type(kivetel), kivetel, kivetel.__traceback__))
    return f"{kivetel} hívási lánc {lanc}"
