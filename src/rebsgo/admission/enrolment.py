# github.com/Shran21

from __future__ import annotations

import logging
import threading

from rebsgo.admission import reasons
from rebsgo.admission.passwords import Jelszotar
from rebsgo.admission.reasons import RefusedWithReason
from rebsgo.protocol.pilot.pilot_steps import NameRules

log = logging.getLogger(__name__)

_JELSZO_LEGALABB = 5
_JELSZO_LEGFELJEBB = 64


class RegisztracioElutasitva(RefusedWithReason):
    def __init__(self, message: str, reason: str = reasons.NAME_RULES):
        super().__init__(reason, message)


class Anyakonyv:
    def __init__(self, data_source, jelszotar: Jelszotar):
        self._data_source = data_source
        self._jelszotar = jelszotar
        self._zar = threading.Lock()

    def felvesz(self, nev: str, jelszo: str, honnan: str) -> int:
        nev = str(nev or "").strip()
        if not NameRules._name_safe_check(nev):
            raise RegisztracioElutasitva(
                "a name is 3-20 letters, digits or underscores",
                reasons.NAME_RULES)
        if not (_JELSZO_LEGALABB <= len(jelszo or "") <= _JELSZO_LEGFELJEBB):
            raise RegisztracioElutasitva(
                f"a password is at least {_JELSZO_LEGALABB} characters",
                reasons.PASSWORD_RULES)

        with self._zar:
            conn = self._data_source.connection()
            try:
                foglalt = conn.execute(
                    "SELECT 1 FROM pilots WHERE name=? COLLATE NOCASE",
                    (nev,)).fetchone()
                if foglalt is not None:
                    raise RegisztracioElutasitva("this name is already taken",
                                                 reasons.NAME_TAKEN)
                uj_azonosito = int(conn.execute(
                    "SELECT COALESCE(MAX(id), 0) + 1 FROM pilots").fetchone()[0])
                conn.execute(
                    "INSERT INTO pilots(id, name, faction, roles_bits,"
                    " last_logout_date, last_wof_date) VALUES (?,?,0,0,'','')",
                    (uj_azonosito, nev))
                conn.commit()
            finally:
                conn.close()
            self._jelszotar.beallit(uj_azonosito, jelszo)

        log.info('enrolled: pilot=%s name=%s origin=%s', uj_azonosito, nev, honnan)
        return uj_azonosito
