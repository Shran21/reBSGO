# github.com/Shran21

from __future__ import annotations

from rebsgo.config.config import Config


class StarterRules:
    _SOROK = (
        ("start_tylium", "int", "rebsgo.pilot.starting.tylium"),
        ("start_cubits", "int", "rebsgo.pilot.starting.cubits"),
        ("start_titanium", "int", "rebsgo.pilot.starting.titanium"),
        ("start_token", "int", "rebsgo.pilot.starting.merits"),
        ("daily_token_cap", "int", "rebsgo.pilot.starting.daily-merit-cap"),
        ("testing_mode", "bool", "rebsgo.pilot.starting.testing-mode"),
    )

    def __init__(self, config: Config | None = None):
        cfg = config or Config.instance()
        for nev, fajta, kulcs in StarterRules._SOROK:
            setattr(self, nev, getattr(cfg, fajta)(kulcs))

    @property
    def is_live(self) -> bool:
        return not self.testing_mode
