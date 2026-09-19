# github.com/Shran21

from __future__ import annotations

from rebsgo.admission import reasons
from rebsgo.admission.reasons import RefusedWithReason

import base64
import binascii
import hashlib
import hmac
import ipaddress
import secrets
import struct
import time
from dataclasses import dataclass

ELETTARTAM_MP = 180

_ORAELTERES_MP = 5

_JELZES = b"rBGO"
_FORMATUM = 1
_SO_MERET = 18
_UJJLENYOMAT_MERET = hashlib.sha256().digest_size

_TARTALOM = struct.Struct(">4sBQQQ18s32s")

_ALAIRAS_CIMKE = b"rebsgo/belepojegy/1\x00"


@dataclass(frozen=True, slots=True)
class Belepojegy:
    pilota: int
    so: str
    kiallitva: int
    lejar: int
    ujjlenyomat: str


class ErvenytelenJegy(RefusedWithReason, ValueError):
    def __init__(self, message: str, reason: str = reasons.TICKET_MALFORMED):
        super().__init__(reason, message)


class JegyPecset:
    def __init__(self, titok: bytes | None = None, elettartam_mp: int = ELETTARTAM_MP):
        if elettartam_mp <= 0:
            raise ValueError('ticket lifetime must be positive')
        alap = titok if titok is not None else secrets.token_bytes(32)
        if len(alap) < 16:
            raise ValueError('ticket secret must span at least 16 bytes')
        gyoker = hmac.new(bytes(alap), b"rebsgo/belepojegy/kulcsok", hashlib.sha256).digest()
        self._alairo_kulcs = hmac.new(gyoker, b"alairas", hashlib.sha256).digest()
        self._ujjlenyomat_kulcs = hmac.new(gyoker, b"ujjlenyomat", hashlib.sha256).digest()
        self._elettartam_mp = int(elettartam_mp)

    @property
    def elettartam_mp(self) -> int:
        return self._elettartam_mp

    def kiallit(self, pilota: int, honnan: str, most: int | None = None) -> str:
        if isinstance(pilota, bool) or not isinstance(pilota, int) or pilota < 0:
            raise ValueError('pilot id must be a non-negative integer')
        kiallitva = _most(most)
        tartalom = _TARTALOM.pack(
            _JELZES,
            _FORMATUM,
            pilota,
            kiallitva,
            kiallitva + self._elettartam_mp,
            secrets.token_bytes(_SO_MERET),
            bytes.fromhex(self._ujjlenyomat(honnan)),
        )
        alairas = hmac.new(self._alairo_kulcs, _ALAIRAS_CIMKE + tartalom, hashlib.sha256).digest()
        return _b64(tartalom) + "." + _b64(alairas)


    def ellenoriz(self, jegy: str, honnan: str, most: int | None = None) -> Belepojegy:
        if not isinstance(jegy, str) or len(jegy) > 512:
            raise ErvenytelenJegy('ticket shape is wrong')
        tartalom_resz, elvalaszto, alairas_resz = jegy.partition(".")
        if not elvalaszto or not tartalom_resz or not alairas_resz or "." in alairas_resz:
            raise ErvenytelenJegy('ticket shape is wrong')

        try:
            tartalom = _unb64(tartalom_resz, meret=_TARTALOM.size)
            kapott_alairas = _unb64(alairas_resz, meret=hashlib.sha256().digest_size)
        except ValueError as hiba:
            raise ErvenytelenJegy(str(hiba)) from hiba

        vart_alairas = hmac.new(
            self._alairo_kulcs, _ALAIRAS_CIMKE + tartalom, hashlib.sha256).digest()
        if not hmac.compare_digest(vart_alairas, kapott_alairas):
            raise ErvenytelenJegy('ticket signature does not check out')

        jelzes, formatum, pilota, kiallitva, lejar, so, kotott_ujjlenyomat = \
            _TARTALOM.unpack(tartalom)
        if jelzes != _JELZES or formatum != _FORMATUM:
            raise ErvenytelenJegy('ticket format unrecognized')
        if lejar - kiallitva != self._elettartam_mp:
            raise ErvenytelenJegy('ticket lifetime out of bounds')

        mostani = _most(most)
        if kiallitva > mostani + _ORAELTERES_MP:
            raise ErvenytelenJegy('ticket timestamped in the future')
        if mostani >= lejar:
            raise ErvenytelenJegy('ticket expired', reasons.TICKET_EXPIRED)
        if not hmac.compare_digest(
                kotott_ujjlenyomat, bytes.fromhex(self._ujjlenyomat(honnan))):
            raise ErvenytelenJegy('ticket was minted for another host',
                                  reasons.TICKET_OTHER_HOST)

        return Belepojegy(
            pilota=pilota,
            so=_b64(so),
            kiallitva=kiallitva,
            lejar=lejar,
            ujjlenyomat=kotott_ujjlenyomat.hex(),
        )

    def _ujjlenyomat(self, honnan: str) -> str:
        return hmac.new(
            self._ujjlenyomat_kulcs, _cim(honnan).encode("ascii"), hashlib.sha256).hexdigest()


def _cim(honnan: object) -> str:
    if not isinstance(honnan, str) or not honnan.strip():
        raise ValueError('requesting host address is absent')
    try:
        cim = ipaddress.ip_address(honnan.strip())
    except ValueError as hiba:
        raise ValueError('requesting host address is not an IP') from hiba
    if isinstance(cim, ipaddress.IPv6Address) and cim.ipv4_mapped is not None:
        cim = cim.ipv4_mapped
    return cim.compressed


def _most(megadott: int | None) -> int:
    return int(time.time()) if megadott is None else int(megadott)


def _b64(nyers: bytes) -> str:
    return base64.urlsafe_b64encode(nyers).decode("ascii").rstrip("=")


def _unb64(szoveg: str, *, meret: int) -> bytes:
    try:
        nyers = szoveg.encode("ascii")
        kiegeszitve = nyers + b"=" * (-len(nyers) % 4)
        vissza = base64.b64decode(kiegeszitve, altchars=b"-_", validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError) as hiba:
        raise ValueError('ticket encoding is broken') from hiba
    if len(vissza) != meret or _b64(vissza) != szoveg:
        raise ValueError('ticket encoding is broken')
    return vissza
