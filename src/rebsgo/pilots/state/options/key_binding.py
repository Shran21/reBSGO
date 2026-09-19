# github.com/Shran21
from __future__ import annotations

from rebsgo.wire.bytes.incoming import Incoming
from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.pilots.state.options.input_actions import Action
from rebsgo.vocabulary.client import KeyCode, KeyHeld


class KeyBinding(Incoming, Outgoing):
    def __init__(self, action=None, key_code=None, modifier=None, device: int = 0,
                 flags: int = 0, profile_no: int = 0):
        self.action = action
        self.device_trigger_code = KeyBinding._wire_number(key_code, KeyCode, "wire_code")
        self.device_modifier_code = KeyBinding._wire_number(modifier, KeyHeld, "value")
        self.device = device
        self.flags = flags
        self.profile_no = profile_no

    @staticmethod
    def _wire_number(ertek, fajta, mezo: str) -> int:
        if isinstance(ertek, fajta):
            return getattr(ertek, mezo)
        return ertek or 0

    def read(self, br) -> None:
        self.device_trigger_code = br.read_uint16()
        self.action = Action.from_code(br.read_uint16())
        self.device_modifier_code = br.read_byte()
        self.device = br.read_byte()
        self.flags = br.read_byte()
        self.profile_no = br.read_byte()

    def to_wire(self, bw) -> None:
        bw.write_uint16(self.device_trigger_code)
        bw.write_uint16(self.action.int_value)
        bw.write_byte(self.device_modifier_code)
        bw.write_byte(self.device)
        bw.write_byte(self.flags)
        bw.write_byte(self.profile_no)

    def __str__(self) -> str:
        tartva = f'+{self.device_modifier_code}' if self.device_modifier_code else ''
        return (f'<key {self.device_trigger_code}{tartva} on device {self.device}'
                f' -> {self.action} (flags {self.flags}, profile {self.profile_no})>')
