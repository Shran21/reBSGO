# github.com/Shran21
from __future__ import annotations

import logging
from enum import Enum

from rebsgo.pilots.state.permissions import HelpScreenKind
from rebsgo.pilots.state.options.key_binding import KeyBinding
from rebsgo.pilots.state.options.option import Option
from rebsgo.pilots.state.options.option_kind import OptionKind
from rebsgo.pilots.state.options.kinds.option_kinds import OptionFlag
from rebsgo.protocol.wire_base import BgoProtocol
from rebsgo.protocol.protocol_id import ProtocolID
from rebsgo.protocol.setting.setting_replies import SettingReplies


log = logging.getLogger(__name__)


class _ClientMessage(Enum):
    SaveSettings = 1
    SaveKeys = 2
    SetSyfyShip = 5
    SetFullScreen = 6

    @staticmethod
    def from_code(uzenet_kod: int):
        return _CM_BY_VALUE.get(uzenet_kod)


_CM_BY_VALUE = {member.value: member for member in _ClientMessage}

_VALUE_TYPE_MAP = {
    Option.CompletedTutorials: OptionKind.HelpScreenKind,
    Option.LootPanelPosition: OptionKind.Float2,
    Option.InventoryPanelPosition: OptionKind.Float2,
    Option.MusicVolume: OptionKind.Float,
    Option.SoundVolume: OptionKind.Float,
    Option.ViewDistance: OptionKind.Float,
    Option.FlakFieldDensity: OptionKind.Float,
    Option.DeadZoneMouse: OptionKind.Float,
    Option.DeadZoneJoystick: OptionKind.Float,
    Option.SensitivityJoystick: OptionKind.Float,
    Option.CameraZoom: OptionKind.Float,
    Option.HudIndicatorMinimizeDistance: OptionKind.Float,
    Option.HudIndicatorTextSize: OptionKind.Float,
    Option.HudIndicatorDescriptionDisplayDistance: OptionKind.Float,
    Option.MouseWheelBinding: OptionKind.Byte,
    Option.SystemMap3DTransitionMode: OptionKind.Byte,
    Option.SystemMap3DCameraView: OptionKind.Byte,
    Option.HudIndicatorColorScheme: OptionKind.Byte,
    Option.CameraMode: OptionKind.Integer,
    Option.GraphicsQuality: OptionKind.Integer,
    Option.Layout: OptionKind.Integer,
    Option.AntiAliasing: OptionKind.Integer,
    Option.FogQuality: OptionKind.Integer,
}

_BOOLEAN_SETTINGS = frozenset({
    Option.CombatGui, Option.ShowTutorial, Option.InvertedVertical, Option.Fullscreen,
    Option.StatsIndication, Option.HudIndicatorShowShipNames, Option.AssignmentsCollapsed,
    Option.ShowStarDust, Option.ShowStarFog, Option.ShowGlowEffect, Option.ShowChangeFaction,
    Option.ChatShowPrefix, Option.ChatViewLocal, Option.ChatViewGlobal, Option.AutoLoot,
    Option.Fullframe, Option.ShowPopups, Option.ShowOutpostMessages,
    Option.ShowHeavyFightingMessages, Option.ShowAugmentMessages, Option.ShowMiningShipMessages,
    Option.ShowExperienceMessages, Option.HudIndicatorShowWingNames, Option.AdvancedFlightControls,
    Option.UseProceduralTextures, Option.ShowFpsAndPing, Option.ShowBulletImpactFx,
    Option.CombatText, Option.ShowEnemyIndication, Option.ShowFriendIndication,
    Option.HudIndicatorShowMissionArrow, Option.AutomaticAmmoReload, Option.ShowWofConfirmation,
    Option.JoystickGamepadEnabled, Option.ShowXbox360Buttons, Option.HudIndicatorShowTitles,
    Option.HighResModels, Option.HighResTextures, Option.HighQualityParticles,
    Option.AnisotropicFiltering, Option.ShowCutscenes, Option.MuteSound,
    Option.ShowDamageOverlay, Option.ShowShipSkins, Option.ShowWeaponModules,
    Option.SystemMap3DShowAsteroids, Option.SystemMap3DShowDynamicMissions,
    Option.SystemMap3DFormAsteroidGroups, Option.HudIndicatorShowTargetNames,
    Option.HudIndicatorShowShipTierIcon, Option.HudIndicatorBracketResizing,
    Option.HudIndicatorSelectionCrosshair, Option.HudIndicatorHealthBar,
    Option.ShowAssignmentMessages, Option.ShowXpBar, Option.VSync, Option.FramerateCapping,
})


class SettingProtocol(BgoProtocol):
    def __init__(self, ctx):
        super().__init__(ProtocolID.Setting, ctx)
        self._writer = SettingReplies()

    @property
    def replies(self) -> SettingReplies:
        return self._writer

    def read_message(self, msg_type: int, br) -> None:
        client_message = _ClientMessage.from_code(msg_type)
        if client_message is None:
            log.warning('settings met a client message it does not know %s',
                        self.user().pilot_of().player_log)
            return
        player = self.user().pilot_of()
        if client_message == _ClientMessage.SaveSettings:
            settings = player.settings
            settings.server_saved_user_settings.read(br)
        elif client_message == _ClientMessage.SaveKeys:
            controls = self._decode_controls(br)
            settings = player.settings
            log.info('%spilot keys: %s %s', self.user().user_log(), len(controls), controls)
            settings.input_bindings.remember(*controls)
        elif client_message == _ClientMessage.SetFullScreen:
            settings = player.settings
            settings.server_saved_user_settings.set_option(Option.Fullscreen, OptionFlag(True))
        elif client_message == _ClientMessage.SetSyfyShip:
            is_on = br.read_boolean()
            log.warning('%ssyfy toggle came in carrying stat %s', self.user().user_log(), is_on)
        else:
            log.error('%sUnknown message_type in SettingProtocol: %s', self.user().user_log(),
                      msg_type)

    def _decode_controls(self, br):
        darab = br.read_length()
        input_bindings = []
        for _i in range(darab):
            try:
                input_binding = br.read_desc(KeyBinding)
                input_bindings.append(input_binding)
            except Exception:
                log.exception("a key binding would not read")
        return input_bindings

    @staticmethod
    def value_type(setting):
        if (value_type := _VALUE_TYPE_MAP.get(setting)) is not None:
            return value_type
        if setting in _BOOLEAN_SETTINGS:
            return OptionKind.Boolean
        log.warning(f'OptionKind: no value for type {setting} present, so it reads as a boolean')
        return OptionKind.Boolean

    def push_settings(self) -> None:
        player = self.user().pilot_of()
        server_saved_settings = player.settings.server_saved_user_settings
        puffer = self._writer.settings(server_saved_settings)
        self.user().send(self._writer.input_bindings(player.settings.input_bindings))
        self.user().send(puffer)

    def _decode_settings(self, br):
        szam = br.read_length()
        ertekek = {}
        for _i in range(szam):
            user_setting = Option.from_code(br.read_byte())
            value_type = OptionKind.from_code(br.read_byte())

            if value_type == OptionKind.Float:
                f = br.read_single()
                ertekek[user_setting] = f
            elif value_type == OptionKind.Boolean:
                b = br.read_boolean()
                ertekek[user_setting] = b
            elif value_type == OptionKind.Integer:
                int32 = br.read_int32()
                ertekek[user_setting] = int32
            elif value_type == OptionKind.Float2:
                f1 = br.read_single()
                f2 = br.read_single()
                ertekek[user_setting] = [f1, f2]
            elif value_type == OptionKind.HelpScreenKind:
                num_to_read = br.read_length()
                help_screen_types = []
                for _j in range(num_to_read):
                    help_screen_types.append(HelpScreenKind.from_code(br.read_uint16()))
                ertekek[user_setting] = help_screen_types
            elif value_type == OptionKind.Byte:
                b = br.read_byte()
                ertekek[user_setting] = b
            else:
                unknown_default = br.read_byte()

        return ertekek
