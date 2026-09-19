# github.com/Shran21

from __future__ import annotations


def csak_orokosen_at(peldany, alap: type) -> None:
    if type(peldany) is alap:
        raise TypeError(f"{alap.__name__} is the shape its heirs share, "
                        f"not something to build on its own")
