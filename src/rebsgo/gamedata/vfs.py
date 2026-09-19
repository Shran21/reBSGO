# github.com/Shran21

from __future__ import annotations

import logging
from pathlib import Path

from rebsgo import paths
from rebsgo.gamedata import pak

log = logging.getLogger(__name__)

PAK_UTVONAL = paths.JATEKADAT / "gamedata.pak"


class _GameDataVFS:
    def __init__(self):
        self._pak: dict[str, bytes] | None = None
        self._mod = "lemez"
        self._betolt()

    def _betolt(self) -> None:
        if paths.JATEKADAT.is_dir() and self._van_tartalom():
            self._mod = "lemez"
            log.info("GameData: from the folder (development mode)")
            return
        if PAK_UTVONAL.is_file():
            try:
                self._pak = pak.unpack(PAK_UTVONAL.read_bytes())
                self._mod = "pak"
                log.info("GameData: from the package, %d files", len(self._pak))
                return
            except pak.PakHiba as ex:
                log.error("gamedata.pak cannot be used: %s", ex)
        log.error("GameData: neither a folder nor a usable package - the content is missing")
        self._pak = {}
        self._mod = "pak"

    @staticmethod
    def _van_tartalom() -> bool:
        return ((paths.JATEKADAT / "cards").is_dir()
                or (paths.JATEKADAT / "templates").is_dir())

    @property
    def pak_mod(self) -> bool:
        return self._mod == "pak"

    def _kulcs(self, path: Path) -> str | None:
        p = Path(path)
        try:
            if p.is_absolute():
                rel = p.resolve().relative_to(paths.JATEKADAT.resolve())
            else:
                parts = p.parts
                if "GameData" not in parts:
                    return None
                rel = Path(*parts[parts.index("GameData") + 1:])
        except ValueError:
            return None
        return rel.as_posix()

    def read_bytes(self, path: Path) -> bytes | None:
        if not self.pak_mod:
            try:
                return Path(path).read_bytes()
            except OSError:
                return None
        kulcs = self._kulcs(path)
        if kulcs is None:
            return None
        return self._pak.get(kulcs)

    def read_text(self, path: Path, encoding: str = "utf-8-sig") -> str | None:
        adat = self.read_bytes(path)
        if adat is None:
            return None
        return adat.decode(encoding)

    def exists(self, path: Path) -> bool:
        if not self.pak_mod:
            return Path(path).exists()
        kulcs = self._kulcs(path)
        return kulcs is not None and kulcs in self._pak

    def json_paths_under(self, template_path: Path) -> list[Path]:
        if not self.pak_mod:
            return [f for f in sorted(Path(template_path).rglob("*.json"))
                    if "!" not in str(f)]
        elo = self._kulcs(template_path)
        if elo is None:
            return []
        elo = elo.rstrip("/")
        talalt = []
        for nev in self._pak:
            if not nev.endswith(".json") or "!" in nev:
                continue
            if nev == elo or nev.startswith(elo + "/"):
                talalt.append(paths.JATEKADAT / nev)
        return sorted(talalt)


_vfs: _GameDataVFS | None = None


def vfs() -> _GameDataVFS:
    global _vfs
    if _vfs is None:
        _vfs = _GameDataVFS()
    return _vfs
