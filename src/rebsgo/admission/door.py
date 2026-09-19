# github.com/Shran21

from __future__ import annotations

import json
import logging
import pathlib
import threading
import time
from collections import deque
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from rebsgo.admission import reasons
from rebsgo.admission.enrolment import Anyakonyv, RegisztracioElutasitva
from rebsgo.admission.gate import BelepesElutasitva, Kapu

log = logging.getLogger(__name__)

UTVONAL = "/login"
REGISZTRACIO_UTVONAL = "/register"

MANIFEST_UTVONAL = "/manifest"
KLIENS_UTVONAL = "/client/"

CHECKOUT = "live"


def _mappa(kulcs: str):
    from rebsgo.config.config import Config

    beallitott = (Config.instance().string(kulcs) or "").strip()
    return pathlib.Path(beallitott) if beallitott else None


def _kliens_mappa():
    return _mappa("rebsgo.launcher.client-dir")


def _lista_mappa():
    return _mappa("rebsgo.launcher.manifest-dir")


def _lista_fajl():
    gyoker = _lista_mappa()
    if gyoker is None:
        return None
    fajl = gyoker / "client" / "manifest.json"
    return fajl if fajl.is_file() else None


_KERES_HATAR_BAJT = 4096
_ABLAK_MP = 60.0
_CIMENKENT = 12
_PILOTANKENT = 6
_EGYIDEJU = 4


@dataclass(frozen=True, slots=True)
class Korlatok:
    ablak_mp: float = _ABLAK_MP
    cimenkent: int = _CIMENKENT
    pilotankent: int = _PILOTANKENT
    egyideju: int = _EGYIDEJU


class _Kereskonyvelo:
    def __init__(self, korlatok: Korlatok):
        self._korlatok = korlatok
        self._cimek: dict[str, deque[float]] = {}
        self._pilotak: dict[int, deque[float]] = {}
        self._zar = threading.Lock()

    def belefer(self, cim: str, pilota: int) -> bool:
        most = time.monotonic()
        with self._zar:
            self._nyes(most)
            cim_naplo = self._cimek.setdefault(cim, deque())
            pilota_naplo = self._pilotak.setdefault(pilota, deque())
            if (len(cim_naplo) >= self._korlatok.cimenkent
                or len(pilota_naplo) >= self._korlatok.pilotankent):
                return False
            cim_naplo.append(most)
            pilota_naplo.append(most)
            return True

    def _nyes(self, most: float) -> None:
        hatar = most - self._korlatok.ablak_mp
        for naplo in list(self._cimek.values()) + list(self._pilotak.values()):
            while naplo and naplo[0] < hatar:
                naplo.popleft()
        self._cimek = {k: v for k, v in self._cimek.items() if v}
        self._pilotak = {k: v for k, v in self._pilotak.items() if v}


class _Ajto(BaseHTTPRequestHandler):
    server_version = "reBSGO"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:  # noqa: N802 - http.server dispatches on this exact name
        utvonal = urlsplit(self.path).path
        if utvonal == REGISZTRACIO_UTVONAL:
            self._regisztracio()
            return
        if utvonal != UTVONAL:
            self._valasz(HTTPStatus.NOT_FOUND, "no such address", reasons.UNKNOWN_PATH)
            return

        mezok = self._mezok()
        if mezok is None:
            return
        pilota = (mezok.get("name") or [""])[0].strip()
        jelszo = (mezok.get("password") or [""])[0]
        if not pilota:
            self._valasz(HTTPStatus.BAD_REQUEST, "the pilot name is missing",
                        reasons.MISSING_NAME)
            return
        if not jelszo:
            self._valasz(HTTPStatus.BAD_REQUEST, "the password is missing",
                        reasons.MISSING_PASSWORD)
            return

        honnan = self.client_address[0]
        if not self.server.konyvelo.belefer(honnan, pilota):
            log.warning('admission rate limit tripped: pilot=%s origin=%s', pilota, honnan)
            self._valasz(HTTPStatus.TOO_MANY_REQUESTS,
                        "too many attempts, wait a minute", reasons.RATE_LIMITED)
            return

        if not self.server.egyideju.acquire(blocking=False):
            log.warning('admission turned away, every check already busy: origin=%s', honnan)
            self._valasz(HTTPStatus.SERVICE_UNAVAILABLE,
                        "every check is busy, try again", reasons.BUSY)
            return
        try:
            azonosito, jegy, _lejar = self.server.kapu.jegyet_ad(pilota, jelszo, honnan)
        except BelepesElutasitva as hiba:
            self._valasz(HTTPStatus.FORBIDDEN, str(hiba), reasons.reason_of(hiba))
            return
        except Exception:
            log.exception('admission request handling fell over')
            self._valasz(HTTPStatus.INTERNAL_SERVER_ERROR, "the server failed",
                        reasons.SERVER_ERROR)
            return
        finally:
            self.server.egyideju.release()

        self._valasz(HTTPStatus.OK, f"{azonosito} {jegy}")

    def _regisztracio(self) -> None:
        anyakonyv = self.server.anyakonyv
        if anyakonyv is None:
            self._valasz(HTTPStatus.FORBIDDEN, "sign-ups are closed",
                        reasons.REGISTRATION_CLOSED)
            return

        mezok = self._mezok()
        if mezok is None:
            return
        nev = (mezok.get("name") or [""])[0].strip()
        jelszo = (mezok.get("password") or [""])[0]
        if not nev:
            self._valasz(HTTPStatus.BAD_REQUEST, "the name is missing", reasons.MISSING_NAME)
            return
        if not jelszo:
            self._valasz(HTTPStatus.BAD_REQUEST, "the password is missing",
                        reasons.MISSING_PASSWORD)
            return

        honnan = self.client_address[0]
        if not self.server.konyvelo.belefer(honnan, nev):
            log.warning('enrolment rate limit tripped: name=%s origin=%s', nev, honnan)
            self._valasz(HTTPStatus.TOO_MANY_REQUESTS,
                        "too many attempts, wait a minute", reasons.RATE_LIMITED)
            return

        if not self.server.egyideju.acquire(blocking=False):
            self._valasz(HTTPStatus.SERVICE_UNAVAILABLE,
                        "every check is busy, try again", reasons.BUSY)
            return
        try:
            azonosito = anyakonyv.felvesz(nev, jelszo, honnan)
        except RegisztracioElutasitva as hiba:
            self._valasz(HTTPStatus.FORBIDDEN, str(hiba), reasons.reason_of(hiba))
            return
        except Exception:
            log.exception('enrolment request handling fell over')
            self._valasz(HTTPStatus.INTERNAL_SERVER_ERROR, "the server failed",
                        reasons.SERVER_ERROR)
            return
        finally:
            self.server.egyideju.release()

        self._valasz(HTTPStatus.OK, f"ok {azonosito}")

    def do_GET(self) -> None:  # noqa: N802 - http.server dispatches on this exact name
        utvonal = urlsplit(self.path).path
        if utvonal == MANIFEST_UTVONAL:
            self._manifest()
            return
        if utvonal.startswith(KLIENS_UTVONAL):
            self._jatekfajl(utvonal[len(KLIENS_UTVONAL):])
            return
        self._valasz(HTTPStatus.METHOD_NOT_ALLOWED, "POST only",
                     reasons.METHOD_NOT_ALLOWED)

    def _manifest(self) -> None:
        cim = ""
        if _lista_fajl() is not None:
            gazda = (self.headers.get("Host") or "").strip()
            if gazda:
                cim = f"http://{gazda}{KLIENS_UTVONAL}"
        test = json.dumps({
            "Client": {"Urlx86": cim, "Urlx64": cim, "Checkout": CHECKOUT},
        }).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(test)))
        self.end_headers()
        self.wfile.write(test)

    def _jatekfajl(self, nev: str) -> None:
        mappa = _kliens_mappa()
        tiszta = nev.replace("\\", "/").replace("%5C", "/").lstrip("/")
        if tiszta == "manifest.json":
            lista = _lista_fajl()
            if lista is None:
                log.info("launcher asked for the client file list, which is "
                         "not configured here")
                self._valasz(HTTPStatus.NOT_FOUND, "no file list is served here",
                             reasons.UNKNOWN_PATH)
                return
            log.info("launcher %s took the client file list",
                     self.client_address[0])
            self._kikuld(lista, "application/json; charset=utf-8")
            return
        if mappa is None:
            self._valasz(HTTPStatus.NOT_FOUND, "no files are served here",
                         reasons.UNKNOWN_PATH)
            return
        try:
            fajl = (mappa / tiszta).resolve()
            fajl.relative_to(mappa.resolve())
        except (ValueError, OSError):
            self._valasz(HTTPStatus.NOT_FOUND, "no such file", reasons.UNKNOWN_PATH)
            return
        if not fajl.is_file():
            self._valasz(HTTPStatus.NOT_FOUND, "no such file", reasons.UNKNOWN_PATH)
            return
        self._kikuld(fajl, "application/octet-stream")

    def _kikuld(self, fajl, fajta: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", fajta)
        self.send_header("Content-Length", str(fajl.stat().st_size))
        self.end_headers()
        with fajl.open("rb") as be:
            while True:
                darab = be.read(1 << 16)
                if not darab:
                    break
                self.wfile.write(darab)

    def _mezok(self):
        hossz = self.headers.get("Content-Length")
        try:
            meret = int(hossz or 0)
        except ValueError:
            self._valasz(HTTPStatus.BAD_REQUEST, "malformed request", reasons.BAD_REQUEST)
            return None
        if meret <= 0 or meret > _KERES_HATAR_BAJT:
            self._valasz(HTTPStatus.BAD_REQUEST, "malformed request", reasons.BAD_REQUEST)
            return None

        test = self.rfile.read(meret).decode("utf-8", "replace").rstrip("\r\n")
        return parse_qs(test)

    def _valasz(self, allapot: HTTPStatus, szoveg: str, ok: str | None = None) -> None:
        test = (szoveg + "\n").encode("utf-8")
        self.send_response(allapot)
        if ok:
            self.send_header("X-Reason", ok)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(test)))
        self.end_headers()
        self.wfile.write(test)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        log.debug('admission door %s - %s', self.client_address[0], format % args)


class _AjtoSzerver(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, cim, kapu: Kapu, korlatok: Korlatok,
                 anyakonyv: "Anyakonyv | None" = None):
        super().__init__(cim, _Ajto)
        self.kapu = kapu
        self.anyakonyv = anyakonyv
        self.konyvelo = _Kereskonyvelo(korlatok)
        self.egyideju = threading.BoundedSemaphore(korlatok.egyideju)


class BelepesiAjto:
    def __init__(self, kapu: Kapu, port: int, korlatok: Korlatok | None = None,
                 anyakonyv: "Anyakonyv | None" = None):
        self._kapu = kapu
        self._port = port
        self._korlatok = korlatok or Korlatok()
        self._anyakonyv = anyakonyv
        self._szerver: _AjtoSzerver | None = None
        self._szal: threading.Thread | None = None

    def start(self) -> None:
        self._szerver = _AjtoSzerver(("", self._port), self._kapu, self._korlatok,
                                     self._anyakonyv)
        self._szal = threading.Thread(
            target=self._szerver.serve_forever, name="BelepesiAjto", daemon=True)
        self._szal.start()
        log.info('admission door listening on %s:%s', self._port, UTVONAL)

    def stop(self) -> None:
        if self._szerver is not None:
            self._szerver.shutdown()
            self._szerver.server_close()
            self._szerver = None
        if self._szal is not None:
            self._szal.join(timeout=5.0)
            self._szal = None
