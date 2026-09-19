# github.com/Shran21

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import sqlite3
import unicodedata
from dataclasses import dataclass

log = logging.getLogger(__name__)

_MUNKA = 1 << 15
_BLOKK = 8
_SZALAK = 1
_MEMORIA_HATAR = 128 * 1024 * 1024

_SO_MERET = 16
_LENYOMAT_MERET = 32
_JELSZO_HATAR = 1024

_URES_SO = b"\x00" * _SO_MERET
_URES_LENYOMAT = b"\x00" * _LENYOMAT_MERET


class JelszoHiba(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Lenyomat:
    algoritmus: str
    so: bytes
    titok: bytes


def _algoritmus_neve() -> str:
    return f"scrypt-{_MUNKA}-{_BLOKK}-{_SZALAK}"


def _jelszo_bajtok(jelszo: str) -> bytes:
    if not isinstance(jelszo, str) or jelszo == "":
        raise JelszoHiba('an empty password will not do')
    nyers = unicodedata.normalize("NFKC", jelszo).encode("utf-8")
    if len(nyers) > _JELSZO_HATAR:
        raise JelszoHiba('that password is too long')
    return nyers


def _szamol(jelszo_bajtok: bytes, so: bytes, algoritmus: str) -> bytes:
    reszek = algoritmus.split("-")
    if len(reszek) != 4 or reszek[0] != "scrypt":
        raise JelszoHiba(f"password algorithm unrecognized: {algoritmus}")
    try:
        munka, blokk, szalak = (int(x) for x in reszek[1:])
    except ValueError as hiba:
        raise JelszoHiba(f"password algorithm string is malformed: {algoritmus}") from hiba
    return hashlib.scrypt(
        jelszo_bajtok, salt=so, n=munka, r=blokk, p=szalak,
        maxmem=_MEMORIA_HATAR, dklen=_LENYOMAT_MERET)


class Jelszotar:
    def __init__(self, data_source):
        self._data_source = data_source


    def helyes(self, pilota: int, jelszo: str) -> bool:
        try:
            nyers = _jelszo_bajtok(jelszo)
        except JelszoHiba:
            return False
        tarolt = self._betolt(pilota)
        vizsgalt = tarolt or Lenyomat(_algoritmus_neve(), _URES_SO, _URES_LENYOMAT)
        try:
            szamolt = _szamol(nyers, vizsgalt.so, vizsgalt.algoritmus)
        except JelszoHiba:
            log.warning('password for pilot %s uses an algorithm we do not know', pilota)
            return False
        egyezik = hmac.compare_digest(szamolt, vizsgalt.titok)
        return tarolt is not None and egyezik


    def beallit(self, pilota: int, jelszo: str) -> None:
        nyers = _jelszo_bajtok(jelszo)
        if not self._letezik(pilota):
            raise JelszoHiba(f"no pilot answers to {pilota}")
        so = secrets.token_bytes(_SO_MERET)
        algoritmus = _algoritmus_neve()
        titok = _szamol(nyers, so, algoritmus)
        with self._data_source.connection() as conn:
            conn.execute(
                "INSERT INTO pilot_passwords(player_id, algorithm, salt, secret, changed_at) "
                "VALUES (?, ?, ?, ?, datetime('now')) "
                "ON CONFLICT(player_id) DO UPDATE SET "
                "algorithm=excluded.algorithm, salt=excluded.salt, "
                "secret=excluded.secret, changed_at=excluded.changed_at",
                (int(pilota), algoritmus, so, titok))

    def torol(self, pilota: int) -> bool:
        with self._data_source.connection() as conn:
            kurzor = conn.execute(
                "DELETE FROM pilot_passwords WHERE player_id=?", (int(pilota),))
            return kurzor.rowcount > 0

    def van_jelszava(self, pilota: int) -> bool:
        return self._betolt(pilota) is not None

    def pilotak(self) -> list[tuple[int, str, str]]:
        conn = self._data_source.connection()
        try:
            return [
                (sor["id"], sor["name"], sor["changed_at"])
                for sor in conn.execute(
                    "SELECT p.id, p.name, j.changed_at FROM pilot_passwords j "
                    "JOIN pilots p ON p.id = j.player_id ORDER BY p.id")
            ]
        finally:
            conn.close()

    def aktiv_tiltas(self, pilota: int):
        import datetime as _dt
        conn = self._data_source.connection()
        try:
            sor = conn.execute(
                "SELECT until_utc, reason FROM panel_bans WHERE player_id=?",
                (int(pilota),)).fetchone()
        except sqlite3.Error:
            return None
        finally:
            conn.close()
        if sor is None:
            return None
        most = _dt.datetime.now(_dt.timezone.utc).isoformat()
        if sor["until_utc"] <= most:
            return None
        return sor["until_utc"], sor["reason"]

    def szerep_bitek(self, pilota: int) -> int:
        conn = self._data_source.connection()
        try:
            sor = conn.execute(
                "SELECT roles_bits FROM pilots WHERE id=?", (int(pilota),)).fetchone()
        except sqlite3.Error:
            return 0
        finally:
            conn.close()
        return int(sor["roles_bits"] or 0) if sor is not None else 0


    def _betolt(self, pilota: int) -> Lenyomat | None:
        conn = self._data_source.connection()
        try:
            sor = conn.execute(
                "SELECT algorithm, salt, secret FROM pilot_passwords WHERE player_id=?",
                (int(pilota),)).fetchone()
        finally:
            conn.close()
        if sor is None:
            return None
        return Lenyomat(sor["algorithm"], bytes(sor["salt"]), bytes(sor["secret"]))

    def azonosito(self, nev_vagy_szam: str) -> int | None:
        szoveg = str(nev_vagy_szam).strip()
        if not szoveg:
            return None
        if szoveg.isdigit():
            return int(szoveg)
        conn = self._data_source.connection()
        try:
            sor = conn.execute(
                "SELECT id FROM pilots WHERE name = ? COLLATE NOCASE LIMIT 1",
                (szoveg,)).fetchone()
        finally:
            conn.close()
        return None if sor is None else int(sor["id"])

    def _letezik(self, pilota: int) -> bool:
        conn = self._data_source.connection()
        try:
            return conn.execute(
                "SELECT 1 FROM pilots WHERE id=? LIMIT 1", (int(pilota),)).fetchone() is not None
        finally:
            conn.close()
