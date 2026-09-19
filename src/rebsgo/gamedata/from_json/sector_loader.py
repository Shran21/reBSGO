# github.com/Shran21
from __future__ import annotations

import logging
from pathlib import Path

from rebsgo.gamedata import lenient_json
from rebsgo.gamedata.sector_layout import SectorInfo
from rebsgo.gamedata.object_templates import AsteroidSpec, PlanetoidSpec
from rebsgo.gamedata.from_json.game_data_loader import GameDataLoader
from rebsgo import paths

log = logging.getLogger(__name__)


class SectorLoader(GameDataLoader):
    def __init__(self):
        super().__init__(paths.JATEKADAT / "templates" / "Sector")

    UJRASZULETES = (
        (AsteroidSpec, "asteroid_desc", "asteroidDesc"),
        (PlanetoidSpec, "planetoid_desc", "planetoidDesc"),
    )

    def sector_templates(self) -> list:
        utak = self.file_paths()
        if not utak:
            log.warning("no sector templates under '%s' (expected .json files).",
                        self.template_path)
        sablonok = [s for s in (self._egy_sablon(ut) for ut in utak) if s is not None]
        if not sablonok:
            log.warning("not one sector template readable under '%s' - no sectors can be built.", self.template_path)
        return sablonok

    def _egy_sablon(self, ut: Path):
        nyers = self.raw_text(ut)
        if nyers is None:
            return None
        sablon = SectorInfo.from_json(lenient_json.loads(nyers))
        if sablon is None:
            log.warning("sector template '%s' would not parse; skipping it.", ut)
            return None
        self._ujraszuletest_beallit(sablon, ut)
        return sablon

    def _ujraszuletest_beallit(self, sablon, ut: Path) -> None:
        objektumok = [o for o in (sablon.space_object_templates or []) if o is not None]
        if not objektumok:
            log.info("sector template '%s' lists no objects, so no respawn timing to set.", ut)
            return

        for fajta, mezo, jelzo in self.UJRASZULETES:
            erintett = [o for o in objektumok if isinstance(o, fajta)]
            if not erintett:
                continue
            leiras = getattr(sablon, mezo)
            if leiras is None:
                log.warning("template '%s' lacks %s - respawn timing stays at its default.", ut, jelzo)
                continue
            ido = leiras.respawn_time
            for objektum in erintett:
                objektum.respawn_after(ido)
