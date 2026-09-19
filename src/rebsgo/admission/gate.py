# github.com/Shran21

from __future__ import annotations

import logging

from rebsgo.admission import reasons
from rebsgo.admission.passwords import Jelszotar
from rebsgo.admission.reasons import RefusedWithReason
from rebsgo.admission.roster import Engedely, NemEngedheto, Nevsor
from rebsgo.admission.ticket import ErvenytelenJegy, JegyPecset

log = logging.getLogger(__name__)


class BelepesElutasitva(RefusedWithReason):
    def __init__(self, message: str, reason: str = reasons.BAD_CREDENTIALS):
        super().__init__(reason, message)


_KARBANTARTAS_ATJARO_BITEK = 16 | 32


class Kapu:
    def __init__(self, pecset: JegyPecset, nevsor: Nevsor, jelszotar: Jelszotar):
        self.uzemszunet = False
        self.uzemszunet_uzenet = ""
        self._pecset = pecset
        self._nevsor = nevsor
        self._jelszotar = jelszotar

    @property
    def nevsor(self) -> Nevsor:
        return self._nevsor

    def jegyet_ad(self, pilota: str | int, jelszo: str, honnan: str) -> tuple[int, str, int]:
        azonosito = self._jelszotar.azonosito(pilota)
        if azonosito is None or not self._jelszotar.helyes(azonosito, jelszo):
            log.warning('admission refused: pilot=%s origin=%s', pilota, honnan)
            raise BelepesElutasitva("unknown pilot, or the password is wrong",
                                    reasons.BAD_CREDENTIALS)
        pilota = azonosito

        tiltas = self._jelszotar.aktiv_tiltas(pilota)
        if tiltas is not None:
            eddig, indok = tiltas
            log.warning('admission refused, banned: pilot=%s until=%s origin=%s',
                        pilota, eddig, honnan)
            szoveg = f"banned until {eddig[:16].replace('T', ' ')}"
            raise BelepesElutasitva(szoveg + (f" ({indok})" if indok else ""),
                                    reasons.BANNED)

        if self.uzemszunet and not (self._jelszotar.szerep_bitek(pilota)
                                    & _KARBANTARTAS_ATJARO_BITEK):
            log.info('admission held back by maintenance: pilot=%s origin=%s',
                     pilota, honnan)
            raise BelepesElutasitva(self.uzemszunet_uzenet or "the server is under maintenance",
                                    reasons.MAINTENANCE)

        jegy_szoveg = self._pecset.kiallit(pilota, honnan)
        jegy = self._pecset.ellenoriz(jegy_szoveg, honnan)
        try:
            self._nevsor.kiad(jegy)
        except NemEngedheto as hiba:
            raise BelepesElutasitva(str(hiba), reasons.reason_of(hiba)) from hiba
        log.info('ticket issued: pilot=%s origin=%s', pilota, honnan)
        return pilota, jegy_szoveg, jegy.lejar

    def beengedi(self, jegy_szoveg: str, honnan: str) -> Engedely:
        try:
            jegy = self._pecset.ellenoriz(jegy_szoveg, honnan)
        except ErvenytelenJegy as hiba:
            raise BelepesElutasitva(str(hiba), reasons.reason_of(hiba)) from hiba
        try:
            return self._nevsor.bevalt(jegy)
        except NemEngedheto as hiba:
            raise BelepesElutasitva(str(hiba), reasons.reason_of(hiba)) from hiba
