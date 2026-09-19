# github.com/Shran21

from __future__ import annotations

import logging

from rebsgo.gamedata.from_json.game_data_loader import GameDataLoader
from rebsgo import paths

log = logging.getLogger(__name__)

ALAP_LEPCSO = ((2, 0), (4, 1), (6, 2), (8, 3), (9, 4))
ALAP_FOLOTTE = 5
ALAP_KOCKA_KESZLETENKENT = 1000.0


class UpgradeRules:
    def __init__(self, lepcso, folotte: int, kocka_keszletenkent: float):
        self._lepcso = tuple(lepcso)
        self._folotte = folotte
        self._kocka_keszletenkent = kocka_keszletenkent

    def required_skill_level(self, system_level: int) -> int:
        for eddig, kell in self._lepcso:
            if system_level <= eddig:
                return kell
        return self._folotte

    def cubits_per_tuning_kit(self) -> float:
        return self._kocka_keszletenkent

    @staticmethod
    def alapertelmezett() -> "UpgradeRules":
        return UpgradeRules(ALAP_LEPCSO, ALAP_FOLOTTE, ALAP_KOCKA_KESZLETENKENT)


class UpgradeRulesReader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Progression")

    def fetch_upgrade_rules(self) -> UpgradeRules:
        for utvonal in self.file_paths():
            if utvonal.name != "system_upgrade.json":
                continue
            obj = self.read_json(utvonal)
            if obj is None:
                continue
            lepcso = [(int(e["upToSystemLevel"]), int(e["skillLevel"]))
                      for e in obj.get("requiredSkillLevel", [])]
            return UpgradeRules(
                sorted(lepcso) or ALAP_LEPCSO,
                int(obj.get("skillLevelAbove", ALAP_FOLOTTE)),
                float(obj.get("cubitsPerTuningKit", ALAP_KOCKA_KESZLETENKENT)))
        log.warning('system_upgrade.json absent - upgrades run on built-in rules')
        return UpgradeRules.alapertelmezett()


_szabalyok: UpgradeRules | None = None


def upgrade_rules() -> UpgradeRules:
    global _szabalyok
    if _szabalyok is None:
        _szabalyok = UpgradeRulesReader().fetch_upgrade_rules()
    return _szabalyok
