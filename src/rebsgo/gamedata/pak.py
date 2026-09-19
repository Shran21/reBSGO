# github.com/Shran21

from __future__ import annotations

import hashlib
import hmac
import struct
import zlib

FEJLEC = b"@shran21 - reBSGO GameData, sealed. github.com/Shran21 - Not a text file; the server reads it.\n"

_SO_HOSSZ = 16
_HMAC_HOSSZ = 32
_BLOKK = 64


_DARABOK = ("bsgo", "@shran21", "reBSGO", "colonial-cylon",
            "battlestar", "kobol->earth")


def _kulcs(so: bytes) -> bytes:
    mag = hashlib.sha256()
    for darab in _DARABOK:
        mag.update(darab.encode("utf-8"))
        mag.update(b"\x1f")
    mag.update(FEJLEC)
    mag.update(so)
    return mag.digest()


def _kulcsfolyam(kulcs: bytes, so: bytes, hossz: int) -> bytes:
    ki = bytearray()
    szamlalo = 0
    while len(ki) < hossz:
        blokk = hashlib.sha256(kulcs + so + struct.pack("<Q", szamlalo)).digest()
        ki.extend(blokk)
        szamlalo += 1
    return bytes(ki[:hossz])


def _rejtjelez(kulcs: bytes, so: bytes, adat: bytes) -> bytes:
    folyam = _kulcsfolyam(kulcs, so, len(adat))
    return bytes(a ^ b for a, b in zip(adat, folyam))


def _torzs_ossze(fajlok: dict[str, bytes]) -> bytes:
    darabok = []
    for nev in sorted(fajlok):
        nev_b = nev.encode("utf-8")
        adat = fajlok[nev]
        darabok.append(struct.pack("<I", len(nev_b)))
        darabok.append(nev_b)
        darabok.append(struct.pack("<I", len(adat)))
        darabok.append(adat)
    return b"".join(darabok)


def _torzs_szet(nyers: bytes) -> dict[str, bytes]:
    fajlok = {}
    i = 0
    n = len(nyers)
    while i < n:
        (nev_hossz,) = struct.unpack_from("<I", nyers, i); i += 4
        nev = nyers[i:i + nev_hossz].decode("utf-8"); i += nev_hossz
        (adat_hossz,) = struct.unpack_from("<I", nyers, i); i += 4
        fajlok[nev] = nyers[i:i + adat_hossz]; i += adat_hossz
    return fajlok


def pack(fajlok: dict[str, bytes], so: bytes) -> bytes:
    if len(so) != _SO_HOSSZ:
        raise ValueError(f"a sónak {_SO_HOSSZ} bájtnak kell lennie")
    kulcs = _kulcs(so)
    tomoritett = zlib.compress(_torzs_ossze(fajlok), 9)
    rejtett = _rejtjelez(kulcs, so, tomoritett)
    elozetes = FEJLEC + so + rejtett
    pecset = hmac.new(kulcs, elozetes, hashlib.sha256).digest()
    return elozetes + pecset


class PakHiba(Exception):
    pass


def unpack(nyers: bytes) -> dict[str, bytes]:
    if not nyers.startswith(FEJLEC):
        raise PakHiba("nem a mi pak-fejlécünk")
    test = nyers[len(FEJLEC):]
    if len(test) < _SO_HOSSZ + _HMAC_HOSSZ:
        raise PakHiba("csonka pak")
    so = test[:_SO_HOSSZ]
    pecset = test[-_HMAC_HOSSZ:]
    rejtett = test[_SO_HOSSZ:-_HMAC_HOSSZ]

    kulcs = _kulcs(so)
    elozetes = nyers[:len(nyers) - _HMAC_HOSSZ]
    var = hmac.new(kulcs, elozetes, hashlib.sha256).digest()
    if not hmac.compare_digest(var, pecset):
        raise PakHiba("a pecsét nem stimmel - a fájlt megváltoztatták")

    try:
        tomoritett = _rejtjelez(kulcs, so, rejtett)
        nyers_torzs = zlib.decompress(tomoritett)
    except zlib.error as ex:
        raise PakHiba("a törzs nem bontható ki") from ex
    return _torzs_szet(nyers_torzs)
