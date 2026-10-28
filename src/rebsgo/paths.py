# github.com/Shran21

from __future__ import annotations

from pathlib import Path

CSOMAG = Path(__file__).resolve().parent

PROJEKT = CSOMAG.parents[1]


SEMA = PROJEKT / "schema"

JATEKADAT = PROJEKT / "GameData"


__all__ = ["CSOMAG", "JATEKADAT", "PROJEKT", "SEMA"]
