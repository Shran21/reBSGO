# github.com/Shran21

from __future__ import annotations

from rebsgo.pilots.state.options.input_actions import Action
from rebsgo.geometry.primitives.vector2 import Vector2
from rebsgo.geometry.primitives.vector3 import Vector3


class QWEASD:
    def __init__(self, bitmask: int = 0):
        self._bitmask = bitmask
        self._input_changed = False

    @property
    def bitmask(self) -> int:
        return self._bitmask

    def clear_keys(self) -> None:
        self._bitmask = 0

    _IRANYOK = (Vector3.up, Vector3.left, Vector3.down, Vector3.right)

    def __str__(self) -> str:
        return f'<QWEASD bitmask={self._bitmask}, input_changed={self._input_changed}>'

    @property
    def any_key_down(self) -> bool:
        return self._bitmask > 0

    @bitmask.setter
    def bitmask(self, bitmask: int) -> None:
        self._bitmask = bitmask

    @property
    def pitch(self) -> int:
        return self._key_state(0) - self._key_state(2)

    @property
    def roll(self) -> int:
        return self._key_state(4) - self._key_state(5)

    @property
    def yaw(self) -> int:
        return self._key_state(3) - self._key_state(1)

    def direction_from_keys(self) -> Vector2:
        hova = Vector3.zero()
        for bit, irany in enumerate(QWEASD._IRANYOK):
            hova.add_(Vector3.mult(irany(), self._key_state(bit)))
        return Vector2(hova.x, hova.y)

    def hold_key(self, bit: int, b_active: bool) -> None:
        if b_active:
            self._bitmask |= bit
        else:
            self._bitmask &= (63 - bit)

    def toggle_if_allowed(self, action: Action, b_active: bool) -> bool:
        if action == Action.SlopeForwardOrSlideUp:
            bit = 1
        elif action == Action.TurnOrSlideLeft:
            bit = 2
        elif action == Action.SlopeBackwardOrSlideDown:
            bit = 4
        elif action == Action.TurnOrSlideRight:
            bit = 8
        elif action == Action.RollLeft:
            bit = 16
        elif action == Action.RollRight:
            bit = 32
        else:
            return False
        self._input_changed = True
        self.hold_key(bit, b_active)
        return True

    def _key_state(self, n: int) -> int:
        return (self._bitmask & (1 << n)) >> n
