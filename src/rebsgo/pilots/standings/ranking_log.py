# github.com/Shran21
from __future__ import annotations

import datetime
import logging

from rebsgo.gamedata.from_json.template_readers import RankingCounterMapReader

from rebsgo.wire.bytes.stamp import Stamp
from rebsgo.protocol.ranking import RankInfo, StandingRow
from rebsgo.helpers.locks import ReadWriteLock, Zarhato

log = logging.getLogger(__name__)

def _load_group_counter_map() -> dict:
    return RankingCounterMapReader().fetch()


class RankingLog(Zarhato):
    OLDAL_SOROK = 17

    def __init__(self, pilot_roster, data_store, reroll_seconds: float):
        self._pilot_roster = pilot_roster
        self._data_store = data_store
        self._reroll_seconds = reroll_seconds
        self._group_counter_map = _load_group_counter_map()
        self._records: dict[int, list] = {}
        self._player_rank: dict[int, dict] = {}
        self._last_update = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        self._last_counter_fetch = None
        self._last_player_infos = None
        self._last_experience_map = None
        self._last_time_fetched = None
        self._read_write_lock = ReadWriteLock()

    def run(self) -> None:
        with self._irva:
            self._fetch_counters()
            self._setup_rankings()

    @staticmethod
    def honap_kulcsa(mikor=None) -> str:
        mikor = mikor or datetime.datetime.now(datetime.timezone.utc)
        return f"month:{mikor.year:04d}-{mikor.month:02d}"

    def _honap_eleje(self) -> dict:
        kulcs = self.honap_kulcsa()
        try:
            if not self._data_store.ranking_period_stored(kulcs):
                self._data_store.take_ranking_snapshot(kulcs)
                self._data_store.drop_ranking_periods_except([kulcs])
            return self._data_store.fetch_ranking_period(kulcs)
        except AttributeError:
            return {}
        except Exception:
            log.exception("the month's opening line would not load")
            return {}

    def _fetch_counters(self) -> None:
        include_experience = self._tapasztalat_kell()
        fetch_snapshot = getattr(self._data_store, "fetch_ranking_snapshot", None)
        if callable(fetch_snapshot):
            counters, player_infos, experience_map = fetch_snapshot(include_experience=include_experience)
            self._last_counter_fetch = counters
            self._last_player_infos = player_infos
            self._last_experience_map = experience_map
        else:
            self._last_counter_fetch = self._data_store.stored_counters()
            self._last_player_infos = None
            self._last_experience_map = None
        self._last_time_fetched = Stamp.now()

    def _setup_rankings(self) -> None:
        from rebsgo.vocabulary.pilot import Faction

        counters = self._last_counter_fetch or {}
        player_infos = self._last_player_infos
        if player_infos is None:
            player_infos = {}
            try:
                player_infos = self._data_store.fetch_all_player_ranking_infos()
            except Exception:
                log.exception("fetch_all_player_ranking_infos failed")

        experience_map = self._last_experience_map
        if self._tapasztalat_kell():
            if experience_map is None:
                experience_map = {}
                try:
                    experience_map = self._data_store.fetch_all_player_experience()
                except Exception:
                    log.exception("fetch_all_player_experience failed")
        elif experience_map is None:
            experience_map = {}

        pilotak = set(counters) | set(experience_map)

        honap_eleje = self._honap_eleje()

        feljegyzesek: dict = {}
        player_rank: dict = {}
        for fajta_ertek, kezdo_allas in ((0, None), (1, honap_eleje)):
            for group_value, ranglista in self._group_counter_map.items():
                scored = []
                for player_id in pilotak:
                    counter_record = counters.get(player_id)
                    sajat = counter_record.counters() if counter_record is not None else {}
                    if kezdo_allas is not None:
                        sajat = self._havi_kulonbseg(sajat, kezdo_allas.get(player_id, {}))
                    xp = experience_map.get(player_id, 0)
                    rendezo = ranglista.rendezo_ertek(sajat, xp)
                    pontok = ranglista.pontszamok(sajat, xp)
                    if rendezo <= 0 and not any(p > 0 for p in pontok):
                        continue
                    scored.append((player_id, rendezo, pontok))
                scored.sort(key=lambda t: (-t[1], t[0]))

                group_records = []
                ranks = {}
                for sorszam, (player_id, _rendezo, pontok) in enumerate(scored):
                    rank = sorszam + 1
                    nev, frakcio = player_infos.get(player_id, ("", Faction.Neutral))
                    if frakcio is None:
                        frakcio = Faction.Neutral
                    group_records.append(RankInfo(rank, player_id, nev, frakcio, *pontok))
                    ranks[player_id] = (rank, pontok)
                feljegyzesek[(group_value, fajta_ertek)] = group_records
                player_rank[(group_value, fajta_ertek)] = ranks

        self._last_update = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        self._records = feljegyzesek
        self._player_rank = player_rank
        self._ermeket_oszt({g: h for (g, fajta), h in player_rank.items() if fajta == 0})

    @staticmethod
    def _havi_kulonbseg(mostani: dict, honap_eleji: dict) -> dict:
        return {guid: max(0.0, float(ertek) - float(honap_eleji.get(guid, 0)))
                for guid, ertek in mostani.items()}

    def _tapasztalat_kell(self) -> bool:
        return any(r.tapasztalatot_olvas for r in self._group_counter_map.values())

    def _ermeket_oszt(self, player_rank: dict) -> None:
        try:
            from rebsgo.services import Services
            from rebsgo.pilots.standings.medal_desk import MedalDesk

            Services.get(MedalDesk).osszes_ujraszamol(player_rank)
        except Exception:
            log.debug("medals not handed out this round", exc_info=True)

    def ranking_group_record(self, ranking_group, ranking_type, page: int) -> StandingRow:
        with self._olvasva:
            all_records = self._records.get(
                (ranking_group.value, getattr(ranking_type, "value", 0)), [])
            kezdet = max(0, int(page)) * RankingLog.OLDAL_SOROK
            page_records = all_records[kezdet:kezdet + RankingLog.OLDAL_SOROK]
            return StandingRow(ranking_group, ranking_type, page_records,
                               len(all_records), self._last_update)

    def player_entry(self, ranking_group, player_id: int, ranking_type=None):
        with self._olvasva:
            bejegyzes = self._player_rank.get(
                (ranking_group.value, getattr(ranking_type, "value", 0)), {}).get(player_id)
            if bejegyzes is None:
                return 0, 0, 0.0, 0.0, 0.0
            rank, pontok = bejegyzes
            return (rank, rank) + tuple(float(p) for p in pontok)

    @property
    def last_time_fetched(self):
        return self._last_time_fetched

    @property
    def reroll_seconds(self) -> float:
        return self._reroll_seconds
