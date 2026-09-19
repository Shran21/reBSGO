# github.com/Shran21

from __future__ import annotations

import builtins
import math

from rebsgo.geometry.maths.maths_inner import MathsInner
from rebsgo.helpers.floats import f32


def _fel_kerekit(value: float) -> int:
    return math.floor(value + 0.5)


class Maths:
    RAD_TO_DEG = f32(57.29578)
    DEG_TO_RAD = f32(0.017453292)
    PI_DIV_2 = f32(1.5707964)
    PI = f32(3.1415927)

    EPSILON = MathsInner.FloatMinNormal if MathsInner.IsFlushToZeroEnabled else MathsInner.FloatMinDenormal

    @staticmethod
    def wrap_angle(angle: float) -> float:
        while angle <= -180.0:
            angle = f32(angle + 360.0)
        while angle > 180.0:
            angle = f32(angle - 360.0)
        return angle

    @staticmethod
    def clamp(value: float, min_v: float, max_v: float) -> float:
        if value < min_v:
            return min_v
        elif value > max_v:
            return max_v
        return value

    @staticmethod
    def clamp_safe(value: float, min_v: float, max_v: float):
        if min_v > max_v:
            return Maths.clamp_safe(value, max_v, min_v)
        if value < min_v:
            return min_v
        elif value > max_v:
            return max_v
        return value

    @staticmethod
    def round(value: float, rounding_places: int) -> float:
        decimal_factor = Maths.pow(10, rounding_places)
        return f32(_fel_kerekit(f32(value * decimal_factor)) / decimal_factor)

    @staticmethod
    def lerp(from_v: float, to_v: float, t: float) -> float:
        return f32(from_v + (to_v - from_v) * Maths.clamp01(t))

    @staticmethod
    def clamp01(value: float) -> float:
        return Maths.clamp(value, 0.0, 1.0)

    @staticmethod
    def clamp_min11(value: float) -> float:
        return Maths.clamp(value, -1.0, 1.0)

    @staticmethod
    def abs(value: float) -> float:
        return f32(builtins.abs(value))

    @staticmethod
    def acos(value: float) -> float:
        return f32(math.acos(value))

    @staticmethod
    def log(base: float, num: float) -> float:
        return f32(math.log10(num) / math.log(base))

    @staticmethod
    def min(first: float, *rest: float) -> float:
        eredmeny = first
        for v in rest:
            eredmeny = builtins.min(eredmeny, v)
        return f32(eredmeny)

    @staticmethod
    def max(first: float, *rest: float) -> float:
        eredmeny = first
        for v in rest:
            eredmeny = builtins.max(eredmeny, v)
        return f32(eredmeny)

    @staticmethod
    def ceil(value: float) -> float:
        return f32(math.ceil(value))

    @staticmethod
    def sqrt(value: float) -> float:
        return f32(math.sqrt(value))

    @staticmethod
    def asin(value: float) -> float:
        return f32(math.asin(value))

    @staticmethod
    def atan2(x: float, y: float) -> float:
        return f32(math.atan2(x, y))

    @staticmethod
    def pow(a: float, b: float) -> float:
        return f32(math.pow(a, b))

    @staticmethod
    def avg_double(*values: float) -> float:
        if values is None:
            raise TypeError('an average is required')
        return sum(values) / float(len(values))

    @staticmethod
    def avg_float(*values: float) -> float:
        if values is None:
            raise TypeError('an average is required')
        osszeg = 0.0
        for v in values:
            osszeg = f32(osszeg + v)
        return f32(osszeg / float(len(values)))

    @staticmethod
    def within_bounds_of(num: float, min_v: float, max_v: float) -> bool:
        if min_v > max_v:
            return Maths.within_bounds_of(num, max_v, min_v)
        return min_v <= num <= max_v

    @staticmethod
    def sin(ivszog: float) -> float:
        return f32(math.sin(ivszog))

    @staticmethod
    def cos(ivszog: float) -> float:
        return f32(math.cos(ivszog))

    @staticmethod
    def nearly_equal(a: float, b: float, epsilon: float) -> bool:
        difference = a - b
        return difference < epsilon and difference > -epsilon
