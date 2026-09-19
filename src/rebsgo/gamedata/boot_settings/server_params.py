# github.com/Shran21

from __future__ import annotations

from rebsgo.config.config import Config
from rebsgo.gamedata.boot_settings.starter_rules import StarterRules


def _felolvas(cel, cfg: Config, sorok) -> None:
    for nev, fajta, kulcs, *alap in sorok:
        setattr(cel, nev, getattr(cfg, fajta)(kulcs, *alap))


class FactionChangeRules:
    _SOROK = (
        ("cooldown_faction_switch", "int", "rebsgo.pilot.faction-switch.cooldown"),
        ("cubits_price_faction", "f32", "rebsgo.pilot.faction-switch.cubits"),
    )

    def __init__(self, config: Config | None = None):
        _felolvas(self, config or Config.instance(), FactionChangeRules._SOROK)


class ServerParams:
    _SOROK = (
        ("port", "int", "rebsgo.net.game-port"),
        ("login_server_port", "int", "rebsgo.net.admission-port"),
        ("chat_server_port", "int", "rebsgo.net.chat-port"),
        ("chat_client_port", "int", "rebsgo.net.chat-client-port", 9338),
        ("max_backlog", "int", "rebsgo.net.backlog"),
        ("max_clients", "int", "rebsgo.net.max-pilots"),
        ("chat_server_address", "string", "rebsgo.net.chat-address"),
        ("ignore_client_build", "bool", "rebsgo.admission.ignore-client-build"),
        ("registration_open", "bool", "rebsgo.admission.registration-open", True),
        ("known_client_builds", "set_string", "rebsgo.admission.known-client-builds"),
    )

    def __init__(self, config: Config | None = None):
        cfg = config or Config.instance()
        _felolvas(self, cfg, ServerParams._SOROK)
        self.starter_params = StarterRules(cfg)
        self.faction_change_params = FactionChangeRules(cfg)

    @property
    def chat_backend_wanted(self) -> bool:
        return self.chat_server_port != 0
