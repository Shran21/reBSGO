# github.com/Shran21
from __future__ import annotations


from rebsgo.wire.bytes.outgoing import Outgoing
from rebsgo.gamedata.from_json.key_binding_reader import default_key_bindings
from rebsgo.helpers.locks import ReentrantLock
from rebsgo.helpers.log_tags import tag


class KeyBindings(Outgoing):
    def __init__(self, billentyu_tabla: dict, user_id: int):
        self._input_binding_map = billentyu_tabla
        self._lock = ReentrantLock()
        tag("userID", str(user_id))

    @staticmethod
    def create(user_id: int) -> "KeyBindings":
        atmeneti = KeyBindings({}, user_id)
        atmeneti.setup_defaults()
        return atmeneti

    def remember(self, *bindings) -> None:
        with self._lock:
            for binding in bindings:
                self._input_binding_map[binding.action] = binding

    def get(self, action):
        with self._lock:
            return self._input_binding_map.get(action)

    def setup_defaults(self) -> None:
        input_bindings = default_key_bindings()
        with self._lock:
            for input_binding in input_bindings:
                self._input_binding_map[input_binding.action] = input_binding

    def to_wire(self, bw) -> None:
        with self._lock:
            bw.write_length(len(self._input_binding_map))
            for input_binding in self._input_binding_map.values():
                bw.write_desc(input_binding)

    @property
    def unmodifiable_input_bindings(self):
        return tuple(self._input_binding_map.values())
