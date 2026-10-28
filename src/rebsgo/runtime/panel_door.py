# github.com/Shran21

from __future__ import annotations

import json
import logging
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger(__name__)

UTVONAL_ALLAPOT = "/status"
UTVONAL_MENTES = "/save"
UTVONAL_KONZOL = "/console"
UTVONAL_KONZOL_NEVEK = "/console/commands"
UTVONAL_NAPLO = "/log"
UTVONAL_SZEKTOROK = "/sectors"
UTVONAL_SZEKTOR_ESEMENY = "/sector-event"
UTVONAL_SZEKTOR_OP = "/sector-op"
UTVONAL_SZEKTOR_UJRA = "/sector-restart"
UTVONAL_SZABALYZAT = "/policy-reload"
UTVONAL_KARBANTARTAS = "/maintenance"
UTVONAL_RANGLISTA = "/rankings-recalc"
UTVONAL_ELENGED = "/release"
UTVONAL_SZALAK = "/threads"
KULCS_FEJLEC = "X-Panel-Key"

_KERES_HATAR_BAJT = 16384


def _uptime_text(masodperc: float) -> str:
    egesz = int(masodperc)
    ora, maradek = divmod(egesz, 3600)
    perc, mp = divmod(maradek, 60)
    return f"{ora}:{perc:02d}:{mp:02d}"


class PanelDoor:
    def __init__(self, kulcs: str, pilot_roster, data_store, host: str = "127.0.0.1",
                 port: int = 27053, console_gateway=None, sector_book=None,
                 kapu=None, elengedo=None):
        self._kulcs = kulcs
        self._elengedo = elengedo
        self._pilot_roster = pilot_roster
        self._data_store = data_store
        self._console_gateway = console_gateway
        self._sector_book = sector_book
        self._kapu = kapu
        self._host = host
        self._port = port
        self._indult = time.time()
        self._szerver = None
        self._szal = None


    def start(self) -> None:
        ajto = self

        class _Kezelo(BaseHTTPRequestHandler):
            def log_message(self, *_args) -> None:
                pass

            def _keyed(self) -> bool:
                kapott = self.headers.get(KULCS_FEJLEC, "")
                if kapott and ajto._kulcs and kapott == ajto._kulcs:
                    return True
                self._json(HTTPStatus.UNAUTHORIZED, {"error": "missing or wrong key"})
                return False

            def _json(self, allapot, adat) -> None:
                torzs = json.dumps(adat).encode("utf-8")
                self.send_response(allapot.value if hasattr(allapot, "value") else allapot)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(torzs)))
                self.end_headers()
                self.wfile.write(torzs)

            def do_GET(self) -> None:
                if not self._keyed():
                    return
                if self.path == UTVONAL_ALLAPOT:
                    self._json(HTTPStatus.OK, ajto.allapot())
                elif self.path == UTVONAL_KONZOL_NEVEK:
                    self._json(*ajto.konzol_nevek())
                elif self.path == UTVONAL_NAPLO:
                    self._json(HTTPStatus.OK, ajto.naplo_allapot())
                elif self.path == UTVONAL_SZEKTOROK:
                    self._json(*ajto.szektorok())
                elif self.path == UTVONAL_KARBANTARTAS:
                    self._json(*ajto.karbantartas_allapot())
                elif self.path == UTVONAL_SZALAK:
                    self._json(HTTPStatus.OK, ajto.szalak())
                else:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "no such path"})

            def do_POST(self) -> None:
                if not self._keyed():
                    return
                hossz = int(self.headers.get("Content-Length", 0) or 0)
                if hossz > _KERES_HATAR_BAJT:
                    self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "too big"})
                    return
                torzs = self.rfile.read(hossz)
                if self.path == UTVONAL_MENTES:
                    self._json(HTTPStatus.OK, ajto.mentes())
                elif self.path == UTVONAL_KONZOL:
                    self._json(*ajto.konzol(torzs))
                elif self.path == UTVONAL_NAPLO:
                    self._json(*ajto.naplo_beallit(torzs))
                elif self.path == UTVONAL_SZEKTOR_ESEMENY:
                    self._json(*ajto.szektor_esemeny(torzs))
                elif self.path == UTVONAL_SZEKTOR_OP:
                    self._json(*ajto.szektor_op(torzs))
                elif self.path == UTVONAL_SZEKTOR_UJRA:
                    self._json(*ajto.szektor_ujraindit(torzs))
                elif self.path == UTVONAL_SZABALYZAT:
                    self._json(*ajto.szabalyzat_ujratolt())
                elif self.path == UTVONAL_KARBANTARTAS:
                    self._json(*ajto.karbantartas_beallit(torzs))
                elif self.path == UTVONAL_RANGLISTA:
                    self._json(*ajto.ranglista_ujraszamol())
                elif self.path == UTVONAL_ELENGED:
                    self._json(*ajto.elenged(torzs))
                else:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "no such path"})

        self._szerver = ThreadingHTTPServer((self._host, self._port), _Kezelo)
        self._port = self._szerver.server_address[1]
        self._szal = threading.Thread(target=self._szerver.serve_forever,
                                      name="panel-door", daemon=True)
        self._szal.start()
        log.info("panel door listening on %s:%s", self._host, self._port)

    def stop(self) -> None:
        if self._szerver is not None:
            self._szerver.shutdown()
            self._szerver = None

    @property
    def port(self) -> int:
        return self._port


    def _online_users(self) -> list:
        bent = []
        for user in self._pilot_roster.mind():
            try:
                if not user.is_connected():
                    continue
                pilota = user.pilot_of()
                if pilota is None:
                    continue
                bent.append(user)
            except Exception:
                continue
        return bent

    def allapot(self) -> dict:
        online = []
        szektoronkent: dict = {}
        for user in self._online_users():
            pilota = user.pilot_of()
            try:
                szektor = int(pilota.sector_id)
            except Exception:
                szektor = 0
            online.append({
                "id": pilota.user_id_of(),
                "name": pilota.name,
                "faction": getattr(pilota.faction, "value", 0),
                "sector": szektor,
            })
            szektoronkent[str(szektor)] = szektoronkent.get(str(szektor), 0) + 1
        return {
            "started": int(self._indult),
            "uptime": _uptime_text(time.time() - self._indult),
            "online": online,
            "sectors": szektoronkent,
        }

    def szalak(self) -> dict:
        # The operating system cuts a thread's name to 15 bytes ("crew-26 sector ["),
        # so the panel takes the full names - and with them the sector a thread
        # runs - from here; it measures the load itself.
        import os
        return {"pid": os.getpid(),
                "threads": [{"tid": szal.native_id, "name": szal.name, "daemon": szal.daemon}
                            for szal in threading.enumerate() if szal.native_id is not None]}

    def mentes(self) -> dict:
        pilotak = [user.pilot_of() for user in self._online_users()]
        if pilotak:
            self._data_store.store_pilots(pilotak)
        log.info("panel door forced a save of %s online pilots", len(pilotak))
        return {"saved": len(pilotak)}

    def konzol(self, torzs: bytes) -> tuple:
        if self._console_gateway is None:
            return HTTPStatus.NOT_IMPLEMENTED, {"error": "no console gateway"}
        try:
            keres = json.loads(torzs.decode("utf-8") or "{}")
            pilot_id = int(keres["pilot"])
            line = str(keres.get("line", ""))
        except (ValueError, KeyError, UnicodeDecodeError):
            return HTTPStatus.BAD_REQUEST, {"error": "want json with pilot and line"}
        try:
            return HTTPStatus.OK, self._console_gateway.run(pilot_id, line)
        except Exception as baj:
            log.exception("panel console request fell over")
            return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(baj)}

    def elenged(self, torzs: bytes) -> tuple:
        if self._elengedo is None:
            return HTTPStatus.NOT_IMPLEMENTED, {"error": "no idle sweep"}
        try:
            keres = json.loads(torzs.decode("utf-8") or "{}")
            pilot_id = int(keres["pilot"])
        except (ValueError, KeyError, TypeError, UnicodeDecodeError):
            return HTTPStatus.BAD_REQUEST, {"error": "want json with pilot"}
        try:
            mi_lett = self._elengedo.release(pilot_id)
        except Exception as baj:
            log.exception("letting go of a pilot fell over")
            return HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(baj)}
        if mi_lett == "released":
            log.info("panel door let go of pilot %s, held in memory since they left", pilot_id)
        return HTTPStatus.OK, {"online": mi_lett == "online", "released": mi_lett == "released"}

    def konzol_nevek(self) -> tuple:
        if self._console_gateway is None:
            return HTTPStatus.NOT_IMPLEMENTED, {"error": "no console gateway"}
        return HTTPStatus.OK, self._console_gateway.command_names()

    def karbantartas_allapot(self) -> tuple:
        if self._kapu is None:
            return HTTPStatus.NOT_IMPLEMENTED, {"error": "no gate"}
        return HTTPStatus.OK, {"on": bool(self._kapu.uzemszunet),
                               "message": self._kapu.uzemszunet_uzenet}

    def karbantartas_beallit(self, torzs: bytes) -> tuple:
        if self._kapu is None:
            return HTTPStatus.NOT_IMPLEMENTED, {"error": "no gate"}
        try:
            keres = json.loads(torzs.decode("utf-8") or "{}")
            kapcsolva = bool(keres["on"])
            uzenet = str(keres.get("message", ""))[:200]
        except (ValueError, KeyError, UnicodeDecodeError):
            return HTTPStatus.BAD_REQUEST, {"error": "want json with on and maybe message"}
        self._kapu.uzemszunet = kapcsolva
        self._kapu.uzemszunet_uzenet = uzenet
        log.info("panel door %s maintenance mode%s",
                 "raised" if kapcsolva else "lifted",
                 f": {uzenet}" if uzenet else "")
        return HTTPStatus.OK, {"ok": True, "on": kapcsolva, "message": uzenet}

    def ranglista_ujraszamol(self) -> tuple:
        from rebsgo.services import Services
        rebuilt = []
        try:
            from rebsgo.pilots.standings.ranking_log import RankingLog
            Services.get(RankingLog).run()
            rebuilt.append("rankings")
        except Exception as baj:
            log.warning("panel ranking rebuild refused: %s", baj)
        try:
            from rebsgo.pilots.standings.tournament_log import TournamentLog
            Services.get(TournamentLog).run()
            rebuilt.append("tournament")
        except Exception as baj:
            log.warning("panel tournament rebuild refused: %s", baj)
        return HTTPStatus.OK, {"ok": bool(rebuilt), "rebuilt": rebuilt}

    def naplo_allapot(self) -> dict:
        from rebsgo import journal
        return journal.szintek()


    def _sector_of(self, torzs: bytes):
        if self._sector_book is None:
            return None, (HTTPStatus.NOT_IMPLEMENTED, {"error": "no sector book"})
        try:
            keres = json.loads(torzs.decode("utf-8") or "{}")
            sector_id = int(keres["sector"])
        except (ValueError, KeyError, UnicodeDecodeError):
            return None, (HTTPStatus.BAD_REQUEST, {"error": "want json with sector"})
        sector = self._sector_book.sector_by_id(sector_id)
        if sector is None:
            return None, (HTTPStatus.NOT_FOUND, {"error": f"no sector {sector_id}"})
        return (sector, keres), None

    def szektorok(self) -> tuple:
        if self._sector_book is None:
            return HTTPStatus.NOT_IMPLEMENTED, {"error": "no sector book"}
        from rebsgo.vocabulary.world import ObjectKind
        npc_kinds = (ObjectKind.Cruiser, ObjectKind.BotFighter,
                     ObjectKind.MiningShip, ObjectKind.AsteroidBot)
        rows = []
        for sector in self._sector_book.sectors():
            row = {"id": sector.id}
            try:
                users = [user for user in sector.ctx.users().users()
                         if user.is_connected()]
                row["players"] = len(users)
                row["names"] = [user.pilot_of().name for user in users]
                objects = sector.ctx.space_objects()
                row["total"] = objects.size()
                row["npcs"] = sum(len(objects.objects_of_kind(kind))
                                  for kind in npc_kinds)
                row["asteroids"] = (len(objects.objects_of_kind(ObjectKind.Asteroid))
                                    + len(objects.objects_of_kind(ObjectKind.Planetoid)))
                row["platforms"] = len(objects.objects_of_kind(ObjectKind.WeaponPlatform))
                row["outposts"] = len(objects.objects_of_kind(ObjectKind.Outpost))
                row["debris"] = len(objects.objects_of_kind(ObjectKind.Debris))
                row["cargo"] = len(objects.objects_of_kind(ObjectKind.CargoObject))
                row["beacons"] = len(objects.objects_of_kind(ObjectKind.JumpBeacon))
                row["op_colonial"] = int(sector.colonial_op_state.op_points)
                row["op_cylon"] = int(sector.cylon_op_state.op_points)
                from rebsgo.gamedata.reading import ObjectStat
                row["outpost_hp"] = []
                for outpost in objects.objects_of_kind(ObjectKind.Outpost):
                    stats = outpost.space_subscribe_info()
                    row["outpost_hp"].append({
                        "faction": getattr(outpost.faction, "name", str(outpost.faction)),
                        "hp": round(float(stats.hp), 1),
                        "max": round(float(stats.stat_or_default(ObjectStat.MaxHullPoints)), 1),
                    })
            except Exception as baj:
                row["trouble"] = str(baj)
            rows.append(row)
        return HTTPStatus.OK, {"sectors": rows}

    def szektor_esemeny(self, torzs: bytes) -> tuple:
        found, trouble = self._sector_of(torzs)
        if trouble is not None:
            return trouble
        sector, _keres = found
        from rebsgo.world.sectors.clockwork import SectorEventTimer
        timer = sector.timer_updater.timer_of_type(SectorEventTimer)
        if timer is None:
            return HTTPStatus.OK, {"ok": False, "reason": "no event timer here"}
        try:
            anybody = any(user.is_connected() for user in sector.ctx.users().users())
        except Exception:
            anybody = False
        if not anybody:
            return HTTPStatus.OK, {"ok": False, "reason": "empty"}
        started = bool(timer.force_start())
        log.info("panel door %s a sector event in %s",
                 "armed" if started else "could not arm", sector.id)
        return HTTPStatus.OK, {"ok": started, "armed": started,
                               "reason": "" if started else "already running"}

    def szektor_op(self, torzs: bytes) -> tuple:
        found, trouble = self._sector_of(torzs)
        if trouble is not None:
            return trouble
        sector, keres = found
        from rebsgo.protocol.protocol_book_replies import game_replies
        try:
            pontok = int(keres.get("points", 0))
        except (TypeError, ValueError):
            return HTTPStatus.BAD_REQUEST, {"error": "points must be a number"}
        oldal = str(keres.get("faction", "")).lower()
        absolute = bool(keres.get("set"))
        if oldal not in ("colonial", "cylon") or (pontok == 0 and not absolute):
            return HTTPStatus.BAD_REQUEST, {"error": "want faction and nonzero points"}
        pontok = max(-3000, min(3000, pontok))
        state = sector.colonial_op_state if oldal == "colonial" else sector.cylon_op_state
        if not state.can_outpost:
            return HTTPStatus.OK, {"ok": False, "reason": "outpost not allowed here",
                                   "op_colonial": int(sector.colonial_op_state.op_points),
                                   "op_cylon": int(sector.cylon_op_state.op_points)}
        if absolute:
            state.op_down(0)
            if pontok > 0:
                state.gain_points(pontok)
        elif pontok > 0:
            if state.is_blocked():
                state.op_down(0)
            state.gain_points(pontok)
        else:
            state.lose_points(abs(pontok))
        sector.ctx.sender().push_to_everyone(
            game_replies().outpost_state_broadcast(
                sector.colonial_op_state.op_points, sector.colonial_op_state.delta(),
                sector.cylon_op_state.op_points, sector.cylon_op_state.delta()))
        log.info("panel door moved outpost points: sector=%s %s %+d",
                 sector.id, oldal, pontok)
        return HTTPStatus.OK, {"ok": True,
                               "op_colonial": int(sector.colonial_op_state.op_points),
                               "op_cylon": int(sector.cylon_op_state.op_points)}

    def szektor_ujraindit(self, torzs: bytes) -> tuple:
        found, trouble = self._sector_of(torzs)
        if trouble is not None:
            return trouble
        sector, _keres = found
        try:
            inside = [user.pilot_of().name for user in sector.ctx.users().users()
                      if user.is_connected()]
        except Exception:
            inside = []
        if inside:
            return HTTPStatus.OK, {"ok": False, "reason": "occupied", "pilots": inside}
        fresh = self._sector_book.restart_sector(sector.id)
        if fresh is None:
            return HTTPStatus.OK, {"ok": False, "reason": "gone"}
        log.info("panel door restarted sector %s", sector.id)
        return HTTPStatus.OK, {"ok": True}

    def szabalyzat_ujratolt(self) -> tuple:
        from rebsgo.gamedata.from_json.template_readers import reload_sector_policy
        policy = reload_sector_policy()
        try:
            from rebsgo.gamedata.cards.card_view import CardView
            from rebsgo.gamedata.library import Catalogue
            from rebsgo.services import Services
            from rebsgo.vocabulary.world import WellKnownCard
            Services.get(Catalogue).forget_writer(WellKnownCard.GalaxyMap.value,
                                                  CardView.GalaxyMap)
        except Exception as baj:
            log.warning("galaxy map cache not dropped: %s", baj)
        log.info("panel door reloaded sector policy: %s closed, %s limited",
                 len(policy.disabled), len(policy.player_limits))
        return HTTPStatus.OK, {"ok": True,
                               "disabled": sorted(policy.disabled),
                               "limits": {str(k): v
                                          for k, v in policy.player_limits.items()}}

    def naplo_beallit(self, torzs: bytes) -> tuple:
        from rebsgo import journal
        try:
            keres = json.loads(torzs.decode("utf-8") or "{}")
            szint = str(keres.get("level", ""))
            terulet = keres.get("area") or None
        except (ValueError, UnicodeDecodeError):
            return HTTPStatus.BAD_REQUEST, {"error": "want json with level and maybe area"}
        rendben = journal.atallit(szint, terulet)
        if rendben:
            journal.audit().info("panel set journal volume: %s%s",
                                 szint, f" area={terulet}" if terulet else "")
        return HTTPStatus.OK, {"ok": rendben, **journal.szintek()}
