# github.com/Shran21

from __future__ import annotations


def sparkline(values, width: int = 240, height: int = 34, pad: int = 3,
              ceiling: float | None = None) -> dict | None:
    points = [float(v or 0) for v in values]
    if len(points) < 2:
        return None
    top = ceiling or max(max(points), 1.0)
    step = width / (len(points) - 1)
    xy = [(i * step, height - pad - (min(v, top) / top) * (height - 2 * pad))
          for i, v in enumerate(points)]
    line = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in xy)
    return {"line": line,
            "fill": f"{line} L{width} {height} L0 {height} Z",
            "x": round(xy[-1][0], 1), "y": round(xy[-1][1], 1),
            "lo": round(min(points)), "hi": round(max(points)), "last": round(points[-1])}
