# github.com/Shran21

from __future__ import annotations

import logging

from rebsgo.pilots.state.pilot_parts import MedalProgress
from rebsgo.vocabulary.combat import AssistMedal, KillerMedal, PvpMedal, TournamentMedal

log = logging.getLogger(__name__)

CSATORNAK = (
    ("pvp_medal", "pvp", PvpMedal),
    ("tournament_medal", "tournament", TournamentMedal),
    ("killer_medal", "killer", KillerMedal),
    ("assist_medal", "assist", AssistMedal),
)


class Sav:
    def __init__(self, helyezes: int, erem):
        self.helyezes = helyezes
        self.erem = erem


class Csatorna:
    def __init__(self, listak, forras: str, savok):
        self.listak = list(listak)
        self.forras = forras
        self.savok = sorted(savok, key=lambda s: s.helyezes)

    def erem(self, helyezes: int | None):
        if not helyezes:
            return None
        for sav in self.savok:
            if helyezes <= sav.helyezes:
                return sav.erem
        return None


def _csatornat_olvas(obj: dict, enum_osztaly) -> Csatorna:
    savok = []
    for leiras in obj.get("bands", []):
        nev = leiras.get("medal")
        erem = getattr(enum_osztaly, nev, None)
        if erem is None:
            log.warning("unknown medal %r for %s", nev, enum_osztaly.__name__)
            continue
        savok.append(Sav(int(leiras.get("up_to_rank", 0)), erem))
    return Csatorna(obj.get("boards", []), obj.get("source", "boards"), savok)


class MedalDesk:
    def __init__(self, pilot_roster, csatornak: dict | None = None):
        self._pilot_roster = pilot_roster
        self._csatornak = csatornak if csatornak is not None else self._betolt()
        self._allas: dict[int, MedalProgress] = {}
        self._torna_helyezes: dict[int, int] = {}

    @staticmethod
    def _betolt() -> dict:
        from rebsgo.gamedata.from_json.template_readers import MedalBandReader

        return MedalBandReader().fetch()

    def torna_allast_frissit(self, helyezesek: dict) -> None:
        self._torna_helyezes = dict(helyezesek or {})

    def ermek(self, player_id: int) -> MedalProgress:
        return self._allas.get(player_id) or MedalProgress()

    def osszes_ujraszamol(self, player_rank: dict) -> None:
        uj: dict[int, MedalProgress] = {}
        erintett = {pid for helyezesek in player_rank.values() for pid in helyezesek}
        erintett |= set(self._torna_helyezes)
        for player_id in erintett:
            uj[player_id] = self._egy_pilota(player_id, player_rank)

        regi, self._allas = self._allas, uj
        for player_id, ermek in uj.items():
            if regi.get(player_id) == ermek:
                continue
            self._kikuld(player_id, ermek)
        for player_id in regi:
            if player_id not in uj:
                self._kikuld(player_id, MedalProgress())

    def _egy_pilota(self, player_id: int, player_rank: dict) -> MedalProgress:
        ermek = {}
        for kulcs, mezo, _enum in CSATORNAK:
            csatorna = self._csatornak.get(kulcs)
            if csatorna is None:
                continue
            if csatorna.forras == "tournament":
                helyezes = self._torna_helyezes.get(player_id)
            else:
                helyek = [player_rank.get(lista, {}).get(player_id, (None,))[0]
                          for lista in csatorna.listak]
                helyek = [h for h in helyek if h]
                helyezes = min(helyek) if helyek else None
            if (erem := csatorna.erem(helyezes)) is not None:
                ermek[mezo] = erem
        return MedalProgress(
            pvp_medal=ermek.get("pvp", PvpMedal.None_),
            tournament_medal=ermek.get("tournament", TournamentMedal.None_),
            killer_medal=ermek.get("killer", KillerMedal.None_),
            assist_medal=ermek.get("assist", AssistMedal.None_))

    def _kikuld(self, player_id: int, ermek: MedalProgress) -> None:
        try:
            user = self._pilot_roster.by_id(player_id)
        except Exception:
            log.exception("medal delivery could not look up player %s", player_id)
            return
        if user is None:
            return
        try:
            user.pilot_of().player_medals.set(ermek)
        except Exception:
            log.exception("medals would not go out to player %s", player_id)
