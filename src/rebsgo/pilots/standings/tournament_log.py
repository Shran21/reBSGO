# github.com/Shran21

from __future__ import annotations

import datetime
import logging

from rebsgo.helpers.locks import ReadWriteLock, Zarhato
from rebsgo.protocol.ranking import RankInfo

log = logging.getLogger(__name__)

MOSTANI, ELOZO, AZELOTTI = 0, -1, -2
SZEZONOK = (MOSTANI, ELOZO, AZELOTTI)


class TournamentLog(Zarhato):
    OLDAL_SOROK = 17

    def __init__(self, data_store, listak=None, szezon_honapok: int | None = None):
        if listak is None:
            from rebsgo.gamedata.from_json.template_readers import TournamentBoardReader

            listak, olvasott_honapok = TournamentBoardReader().fetch()
            szezon_honapok = szezon_honapok or olvasott_honapok
        self._data_store = data_store
        self._listak = listak
        self._szezon_honapok = max(1, int(szezon_honapok or 1))
        self._records: dict = {}
        self._player_rank: dict = {}
        self._last_update = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        self._read_write_lock = ReadWriteLock()


    def szezon_kulcsa(self, eltolas: int = 0, mikor=None) -> str:
        mikor = mikor or datetime.datetime.now(datetime.timezone.utc)
        sorszam = (mikor.year * 12 + (mikor.month - 1)) // self._szezon_honapok + eltolas
        ev, honap = divmod(sorszam * self._szezon_honapok, 12)
        return f"season:{ev:04d}-{honap + 1:02d}"


    def run(self) -> None:
        with self._irva:
            self._epit()

    def _epit(self) -> None:
        from rebsgo.vocabulary.pilot import Faction

        if not self._listak:
            return
        kulcsok = [self.szezon_kulcsa(-i) for i in range(3)]
        nyito = self._nyito_vonalak(kulcsok)
        mostani_szamlalok, player_infos = self._mostani_allas()

        feljegyzesek, player_rank = {}, {}
        for szezon in SZEZONOK:
            vege = mostani_szamlalok if szezon == MOSTANI else nyito.get(kulcsok[-szezon - 1], {})
            eleje = nyito.get(kulcsok[-szezon], {})
            for osztaly, ranglista in self._listak.items():
                scored = []
                for player_id, vege_sajat in vege.items():
                    sajat = self._kulonbseg(vege_sajat, eleje.get(player_id, {}))
                    rendezo = ranglista.rendezo_ertek(sajat, 0)
                    pontok = ranglista.pontszamok(sajat, 0)
                    if rendezo <= 0 and not any(p > 0 for p in pontok):
                        continue
                    scored.append((player_id, rendezo, pontok))
                scored.sort(key=lambda t: (-t[1], t[0]))

                sorok, ranks = [], {}
                for sorszam, (player_id, _r, pontok) in enumerate(scored):
                    rank = sorszam + 1
                    nev, frakcio = player_infos.get(player_id, ("", Faction.Neutral))
                    sorok.append(RankInfo(rank, player_id, nev, frakcio or Faction.Neutral, *pontok))
                    ranks[player_id] = (rank, pontok)
                feljegyzesek[(osztaly, szezon)] = sorok
                player_rank[(osztaly, szezon)] = ranks

        self._last_update = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        self._records = feljegyzesek
        self._player_rank = player_rank
        self._ermet_jelent(player_rank)

    def _nyito_vonalak(self, kulcsok) -> dict:
        ki = {}
        try:
            if not self._data_store.ranking_period_stored(kulcsok[0]):
                self._data_store.take_ranking_snapshot(kulcsok[0])
            for kulcs in kulcsok:
                ki[kulcs] = self._data_store.fetch_ranking_period(kulcs)
        except AttributeError:
            return {}
        except Exception:
            log.exception("the tournament's opening lines would not load")
        return ki

    def _mostani_allas(self):
        try:
            counters, player_infos, _xp = self._data_store.fetch_ranking_snapshot(
                include_experience=False)
        except Exception:
            log.exception("the tournament standings would not load")
            return {}, {}
        return ({pid: rec.counters() for pid, rec in counters.items()}, player_infos)

    @staticmethod
    def _kulonbseg(vege: dict, eleje: dict) -> dict:
        return {guid: max(0.0, float(ertek) - float(eleje.get(guid, 0)))
                for guid, ertek in vege.items()}

    def _ermet_jelent(self, player_rank: dict) -> None:
        legjobb: dict = {}
        for (_osztaly, szezon), helyezesek in player_rank.items():
            if szezon != MOSTANI:
                continue
            for player_id, (rank, _pontok) in helyezesek.items():
                if rank < legjobb.get(player_id, 10 ** 9):
                    legjobb[player_id] = rank
        try:
            from rebsgo.services import Services
            from rebsgo.pilots.standings.medal_desk import MedalDesk

            Services.get(MedalDesk).torna_allast_frissit(legjobb)
        except Exception:
            log.debug("the tournament medal was not handed over", exc_info=True)


    def board(self, osztaly: int, szezon: int, page: int):
        with self._olvasva:
            sorok = self._records.get((osztaly, szezon), [])
            kezdet = max(0, int(page)) * TournamentLog.OLDAL_SOROK
            return (sorok[kezdet:kezdet + TournamentLog.OLDAL_SOROK],
                    len(sorok), self._last_update)

    def player_entry(self, osztaly: int, szezon: int, player_id: int):
        with self._olvasva:
            bejegyzes = self._player_rank.get((osztaly, szezon), {}).get(player_id)
            if bejegyzes is None:
                return 0, 0, 0.0, 0.0, 0.0
            rank, pontok = bejegyzes
            return (rank, rank) + tuple(float(p) for p in pontok)
