# github.com/Shran21

from __future__ import annotations

import datetime
import logging

from rebsgo.pilots.state.boosts.boost import Boost
from rebsgo.protocol.pilot.pilot_replies import PilotReplies
from rebsgo.vocabulary.pilot import Faction, BoostSource, BoostKind
from rebsgo.gamedata.from_json.game_data_loader import GameDataLoader
from rebsgo.protocol.protocol_book_replies import replies_for
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo import paths

log = logging.getLogger(__name__)


class _BonusEntry:
    def __init__(self, name: str, factors, ftl_cost_multiplier: float, faction):
        self.name = name
        self.factors = factors
        self.ftl_cost_multiplier = ftl_cost_multiplier
        self.faction = faction


class _DailyBonusTemplateReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Bonus")

    def fetch(self):
        for utvonal in self.file_paths():
            if utvonal.name != "daily_bonuses.json":
                continue
            obj = self.read_json(utvonal)
            if obj is None:
                continue

            def parse_entries(nyers):
                bejegyzesek = []
                for e in nyers:
                    factors = []
                    for f in e.get("factors", []):
                        factor_type = BoostKind[f["type"]]
                        factors.append((factor_type, float(f["value"])))
                    faction = None
                    if e.get("faction"):
                        faction = Faction[e["faction"]]
                    bejegyzesek.append(_BonusEntry(e.get("name", "?"), factors,
                                               float(e.get("ftlCostMultiplier", 1.0)), faction))
                return bejegyzesek

            return parse_entries(obj.get("rotation", [])), parse_entries(obj.get("factionRotation", []))
        log.warning("No daily_bonuses.json found; daily bonuses disabled")
        return [], []


class DailyBonusService:
    def __init__(self, pilot_roster):
        self._pilot_roster = pilot_roster
        self._rotation, self._faction_rotation = _DailyBonusTemplateReader().fetch()
        self._writer = PilotReplies()

    @staticmethod
    def _today() -> datetime.date:
        return datetime.datetime.now(datetime.timezone.utc).date()

    @staticmethod
    def _end_of_day() -> datetime.datetime:
        today = DailyBonusService._today()
        return datetime.datetime(today.year, today.month, today.day) + datetime.timedelta(days=1)

    def _entry_of(self, rotation):
        if not rotation:
            return None
        return rotation[self._today().toordinal() % len(rotation)]

    @property
    def today_general(self):
        return self._entry_of(self._rotation)

    @property
    def today_faction(self):
        return self._entry_of(self._faction_rotation)

    def ftl_cost_multiplier(self) -> float:
        bejegyzes = self.today_general
        return bejegyzes.ftl_cost_multiplier if bejegyzes is not None else 1.0

    def run(self) -> None:
        general = self.today_general
        faction_entry = self.today_faction
        end_of_day = DailyBonusService._end_of_day()
        for user in self._pilot_roster.user_list(lambda u: u.is_connected()):
            try:
                self._apply_to_user(user, general, faction_entry, end_of_day)
            except Exception:
                log.exception("daily bonus apply failed for a user")

    def _apply_to_user(self, user, general, faction_entry, end_of_day) -> None:
        player = user.pilot_of()
        factors = player.factors
        added = False
        if general is not None:
            for factor_type, value in general.factors:
                if not self._has_active(factors, factor_type, BoostSource.Marketing):
                    factors.take_boost(Boost.ending_at(factor_type, BoostSource.Marketing, value, end_of_day))
                    added = True
        if faction_entry is not None and faction_entry.faction == player.faction:
            for factor_type, value in faction_entry.factors:
                if not self._has_active(factors, factor_type, BoostSource.Faction):
                    factors.take_boost(Boost.ending_at(factor_type, BoostSource.Faction, value, end_of_day))
                    added = True
        if added:
            user.send(self._writer.factors(factors))

    @staticmethod
    def _has_active(factors, factor_type, factor_source) -> bool:
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        for szorzo in factors.values():
            vege = szorzo.end_time
            if vege.tzinfo is not None:
                vege = vege.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            if (szorzo.factor_type == factor_type and szorzo.factor_source == factor_source
                and vege > now):
                return True
        return False


class _StreakTable:
    def __init__(self, obj: dict):
        self.grace_days = int(obj.get("graceDays", 1))
        self.hold_at_end = str(obj.get("afterEnd", "hold")) == "hold"
        self.by_day = {}
        for sor in obj.get("days", []):
            if "day" not in sor:
                continue
            if "rewards" in sor:
                self.by_day[int(sor["day"])] = [int(g) for g in sor["rewards"]]
            elif "reward" in sor:
                self.by_day[int(sor["day"])] = [int(sor["reward"])]

    @property
    def last_day(self) -> int:
        return max(self.by_day) if self.by_day else 0

    def rewards_for(self, nap: int):
        return self.by_day.get(nap) or []


class _StreakTableReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Bonus")

    def fetch(self) -> _StreakTable:
        for utvonal in self.file_paths():
            if utvonal.name != "login_streak.json":
                continue
            if (obj := self.read_json(utvonal)) is not None:
                tabla = _StreakTable(obj)
                log.info("Loaded the login streak ladder: %s days", tabla.last_day)
                return tabla
        log.warning("No login_streak.json found; the login reward stays quiet")
        return _StreakTable({})


KLIENS_SZINT_PLAFON = 5


class LoginStreakService:
    def __init__(self, pilot_roster):
        self._pilot_roster = pilot_roster
        self._table = _StreakTableReader().fetch()

    @staticmethod
    def _today() -> datetime.date:
        return datetime.datetime.now(datetime.timezone.utc).date()

    def day_for(self, player) -> int:
        utolso = player.daily_streak_date
        if not utolso:
            return 1
        try:
            elozo = datetime.date.fromisoformat(utolso)
        except ValueError:
            return 1
        koztes = (self._today() - elozo).days
        if koztes <= 0:
            return 0
        if koztes > 1 + self._table.grace_days:
            return 1
        kovetkezo = player.daily_streak_day + 1
        if self._table.hold_at_end:
            kovetkezo = min(kovetkezo, self._table.last_day)
        elif kovetkezo > self._table.last_day:
            kovetkezo = 1
        return kovetkezo

    def run(self) -> None:
        if not self._table.by_day:
            return
        for user in self._pilot_roster.user_stream(lambda u: u.is_connected()):
            self.offer_user(user)

    def offer_user(self, user) -> None:
        if not self._table.by_day:
            return
        try:
            self._offer_to(user, self._today().isoformat())
        except Exception as ex:
            log.warning("login streak offer failed for %s", user.user_log(), exc_info=ex)

    def _offer_to(self, user, ma: str) -> None:
        player = user.pilot_of()
        if player is None or player.daily_streak_date == ma:
            return
        if getattr(player, "_daily_offer_date", None) == ma:
            return
        nap = self.day_for(player)
        if nap <= 0:
            return
        valasztek = self._table.rewards_for(nap)
        if not valasztek:
            return
        player.daily_offer_guid = list(valasztek)
        player._daily_offer_date = ma
        iro = replies_for(ProtocolID.Notification)
        user.send(iro.daily_login_bonus(bonus_level=min(nap, KLIENS_SZINT_PLAFON),
                                        rewar_guids=list(valasztek)))
        log.info("%s offered login day %s choice of %s", user.user_log(), nap, valasztek)
