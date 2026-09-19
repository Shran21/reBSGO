# github.com/Shran21
from __future__ import annotations

from rebsgo.pilots.state.options.key_bindings import KeyBindings
from rebsgo.pilots.state.options.options import Options
from rebsgo.helpers.log_tags import tag


class Settings:
    def __init__(self, user_id: int):
        self._server_saved_user_settings = Options(user_id=user_id)
        self._input_bindings = KeyBindings.create(user_id)
        tag("userID", str(user_id))

    @property
    def server_saved_user_settings(self) -> Options:
        return self._server_saved_user_settings


    @property
    def input_bindings(self) -> KeyBindings:
        return self._input_bindings
