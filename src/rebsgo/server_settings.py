# github.com/Shran21
from __future__ import annotations

from rebsgo.world.galaxy.elo_scales import EloScales
from rebsgo.protocol.pilot.pilot_services import PilotServices
from rebsgo.protocol.pilot.pilot_steps import FactionSwitchLimits
from rebsgo.wire.links.front_door import FrontDoor


class ServerSettings:
    def __init__(self, pilot_roster, server_settings):
        self._pilot_roster = pilot_roster
        self._server_settings = server_settings

    def character_services(self) -> PilotServices:
        return PilotServices(
            0,
            False,
            self._server_settings.faction_change_params.cooldown_faction_switch,
            0,
            0,
            0,
            self._server_settings.faction_change_params.cubits_price_faction,
            10_000_000,
            [FactionSwitchLimits(10, 255)])

    @property
    def faction_scales(self) -> EloScales:
        return EloScales(self._pilot_roster, 10.0)

    @property
    def server_listener(self) -> FrontDoor:
        return FrontDoor(self._server_settings.port,
                         self._server_settings.max_backlog)
