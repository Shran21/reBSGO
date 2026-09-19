# github.com/Shran21
from __future__ import annotations

import datetime as _dt

_EPOCH = _dt.datetime(1970, 1, 1, 0, 0)


def read_moment(nyers_szoveg: str) -> _dt.datetime:
    if nyers_szoveg == "":
        return _EPOCH
    return _dt.datetime.fromisoformat(nyers_szoveg)


def format_local_date_time(idopont) -> str:
    return "" if idopont is None else idopont.isoformat()
