# github.com/Shran21

from __future__ import annotations

import hmac
import logging
import threading
import time
from dataclasses import dataclass, replace

from rebsgo.admission import reasons
from rebsgo.admission.reasons import RefusedWithReason
from rebsgo.admission.ticket import Belepojegy

log = logging.getLogger(__name__)


class NemEngedheto(RefusedWithReason, ValueError):
    def __init__(self, message: str, reason: str = reasons.TICKET_UNKNOWN):
        super().__init__(reason, message)


@dataclass(frozen=True, slots=True)
class Engedely:
    pilota: int
    so: str
    lejar: int
    ujjlenyomat: str
    belepett: float | None = None


@dataclass(frozen=True, slots=True)
class _Kiadott:
    engedely: Engedely
    hatarido: float


class Nevsor:
    def __init__(self):
        self._kiadott: dict[str, _Kiadott] = {}
        self._elo: dict[int, Engedely] = {}
        self._leszakadt: set[int] = set()
        self._felhasznalt: dict[str, float] = {}
        self._zar = threading.RLock()


    def kiad(self, jegy: Belepojegy) -> Engedely:
        most = time.monotonic()
        with self._zar:
            self._takarit(most)
            if jegy.so in self._felhasznalt:
                raise NemEngedheto("this ticket has already been spent",
                                   reasons.TICKET_SPENT)
            if jegy.so in self._kiadott:
                raise NemEngedheto("this ticket is already outstanding",
                                   reasons.TICKET_OUTSTANDING)
            engedely = Engedely(
                pilota=jegy.pilota,
                so=jegy.so,
                lejar=jegy.lejar,
                ujjlenyomat=jegy.ujjlenyomat,
            )
            self._kiadott[jegy.so] = _Kiadott(engedely, most + (jegy.lejar - jegy.kiallitva))
            return engedely

    def bevalt(self, jegy: Belepojegy) -> Engedely:
        most = time.monotonic()
        with self._zar:
            self._takarit(most)

            if jegy.so in self._felhasznalt:
                raise NemEngedheto("this ticket has already been spent",
                                   reasons.TICKET_SPENT)
            kiadott = self._kiadott.get(jegy.so)
            if kiadott is None:
                raise NemEngedheto("unknown ticket", reasons.TICKET_UNKNOWN)
            if kiadott.hatarido <= most:
                self._kiadott.pop(jegy.so, None)
                raise NemEngedheto('this ticket has expired', reasons.TICKET_EXPIRED)
            if kiadott.engedely.pilota != jegy.pilota:
                raise NemEngedheto('this ticket belongs to a different pilot',
                                   reasons.TICKET_OTHER_PILOT)
            if not hmac.compare_digest(kiadott.engedely.ujjlenyomat, jegy.ujjlenyomat):
                raise NemEngedheto('this ticket belongs to a different host',
                                   reasons.TICKET_OTHER_HOST)

            elo = self._elo.get(jegy.pilota)
            if elo is not None and jegy.pilota not in self._leszakadt:
                raise NemEngedheto("this pilot is already in the game",
                                   reasons.ALREADY_ONLINE)

            self._kiadott.pop(jegy.so, None)
            self._felhasznalt[jegy.so] = kiadott.hatarido

            if elo is not None:
                vissza = replace(elo, so=jegy.so, lejar=jegy.lejar,
                                 ujjlenyomat=jegy.ujjlenyomat)
                self._elo[jegy.pilota] = vissza
                self._leszakadt.discard(jegy.pilota)
                log.info('pilot %s reclaimed their dropped session', jegy.pilota)
                return vissza

            uj = replace(kiadott.engedely, belepett=most)
            self._elo[jegy.pilota] = uj
            return uj


    def leszakadt(self, engedely: Engedely) -> bool:
        with self._zar:
            elo = self._egyezo(engedely)
            if elo is None:
                return False
            self._leszakadt.add(elo.pilota)
            return True

    def elenged(self, engedely: Engedely) -> bool:
        with self._zar:
            elo = self._egyezo(engedely)
            if elo is None:
                return False
            self._elo.pop(elo.pilota, None)
            self._leszakadt.discard(elo.pilota)
            return True

    def bent_van(self, pilota: int) -> Engedely | None:
        with self._zar:
            if pilota in self._leszakadt:
                return None
            return self._elo.get(int(pilota))

    def helyet_tartja(self, pilota: int) -> Engedely | None:
        with self._zar:
            if int(pilota) not in self._leszakadt:
                return None
            return self._elo.get(int(pilota))

    def bentiek(self) -> int:
        with self._zar:
            return len(self._elo) - len(self._leszakadt)


    def _egyezo(self, engedely: Engedely) -> Engedely | None:
        elo = self._elo.get(engedely.pilota)
        if elo is None or not hmac.compare_digest(elo.so, engedely.so):
            return None
        return elo

    def hely(self, engedely: Engedely) -> "Hely":
        return Hely(self, engedely)

    def _takarit(self, most: float) -> None:
        lejart = [so for so, kiadott in self._kiadott.items() if kiadott.hatarido <= most]
        for so in lejart:
            del self._kiadott[so]
        elhasznalt = [so for so, hatarido in self._felhasznalt.items() if hatarido <= most]
        for so in elhasznalt:
            del self._felhasznalt[so]


class Hely:
    __slots__ = ("_nevsor", "_engedely", "_nyitva")

    def __init__(self, nevsor: Nevsor, engedely: Engedely):
        self._nevsor = nevsor
        self._engedely = engedely
        self._nyitva = True

    @property
    def pilota(self) -> int:
        return self._engedely.pilota

    @property
    def engedely(self) -> Engedely:
        return self._engedely

    @property
    def nyitva(self) -> bool:
        return self._nyitva

    def kapcsolat_elment(self) -> None:
        if not self._nyitva:
            return
        self._nyitva = False
        self._nevsor.leszakadt(self._engedely)

    def elhagyja(self) -> None:
        self._nyitva = False
        self._nevsor.elenged(self._engedely)

    def __eq__(self, masik: object) -> bool:
        if not isinstance(masik, Hely):
            return NotImplemented
        return (self._engedely.pilota == masik._engedely.pilota
                and hmac.compare_digest(self._engedely.so, masik._engedely.so))

    def __hash__(self) -> int:
        return hash((self._engedely.pilota, self._engedely.so))

    def __str__(self) -> str:
        allapot = "bent" if self._nyitva else "leszakadt"
        return f"hely(pilóta={self._engedely.pilota}, {allapot})"
