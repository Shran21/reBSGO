# github.com/Shran21
from __future__ import annotations

from rebsgo.wire.bytes.incoming import Incoming
from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.pilots.state.permissions import HelpScreenKind
from rebsgo.pilots.state.options.option import Option
from rebsgo.pilots.state.options.option_kind import OptionKind
from rebsgo.pilots.state.options.kinds.option_kinds import OptionFlag, OptionByte, OptionDecimal, OptionPair, OptionHelpScreen, OptionNumber
from rebsgo.helpers.locks import ReentrantLock
from rebsgo.helpers.log_tags import tag


_RENDER_DEFAULT_BOOLEANS = {
    Option.ShowWeaponModules: True,
    Option.ShowShipSkins: True,
}


class Options(Outgoing, Incoming):
    def __init__(self, beallitas_tabla: dict | None = None, user_id: int = 0):
        self._settings_map = {} if beallitas_tabla is None else beallitas_tabla
        tag("userID", str(user_id))
        self._lock = ReentrantLock()

    def set_option(self, user_setting, setting_value) -> None:
        with self._lock:
            self._set_unlocked(user_setting, setting_value)

    def _set_unlocked(self, user_setting, setting_value) -> None:
        self._settings_map[user_setting] = setting_value

    def get(self, user_setting):
        with self._lock:
            return self._settings_map.get(user_setting)

    def apply_render_defaults(self) -> None:
        with self._lock:
            for user_setting, default_value in _RENDER_DEFAULT_BOOLEANS.items():
                if user_setting not in self._settings_map:
                    self._set_unlocked(user_setting, OptionFlag(default_value))

    def to_wire(self, bw) -> None:
        with self._lock:
            bw.write_length(len(self._settings_map))
            for kulcs, value in self._settings_map.items():
                bw.write_byte(kulcs.value)
                bw.write_byte(0)
                bw.write_desc(value)

    def settings_unmodifiable_map(self) -> dict:
        with self._lock:
            from types import MappingProxyType
            return MappingProxyType(self._settings_map)

    def read(self, br) -> None:
        with self._lock:
            hossz = br.read_length()
            for _ in range(hossz):
                self._read_single_user_setting(br)

    def _read_single_user_setting(self, br) -> None:
        user_setting = Option.from_code(br.read_byte())
        user_setting_value_type = OptionKind.from_code(br.read_byte())
        if user_setting_value_type == OptionKind.Byte:
            self._set_unlocked(user_setting, OptionByte(br.read_byte()))
        elif user_setting_value_type == OptionKind.Boolean:
            self._set_unlocked(user_setting, OptionFlag(br.read_boolean()))
        elif user_setting_value_type == OptionKind.Float:
            self._set_unlocked(user_setting, OptionDecimal(br.read_single()))
        elif user_setting_value_type == OptionKind.Float2:
            self._set_unlocked(user_setting, OptionPair(br.read_vector2()))
        elif user_setting_value_type == OptionKind.Integer:
            self._set_unlocked(user_setting, OptionNumber(br.read_int32()))
        elif user_setting_value_type == OptionKind.HelpScreenKind:
            screen_types_size = br.read_length()
            help_screen_types = [HelpScreenKind.from_code(br.read_uint16()) for _ in range(screen_types_size)]
            self._set_unlocked(user_setting, OptionHelpScreen(help_screen_types))
        else:
            br.read_byte()
