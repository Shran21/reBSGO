# github.com/Shran21
from __future__ import annotations

from contextlib import suppress

import hashlib
import json
import logging
import pickle
import tempfile
import threading
from copy import deepcopy
from pathlib import Path

from rebsgo.config.config import Config
from rebsgo.gamedata.vfs import vfs
from rebsgo.helpers.rolling_latency_stats import (
    ENABLED as GUARDRAILS_ENABLED,
    GAMEDATA_CACHE_WARN_MS,
    GAMEDATA_FILE_WARN_MS,
    elapsed_ms,
    now_ms,
    warn_if_slow,
)

log = logging.getLogger(__name__)

_CONFIG = Config.instance()
_JSON_CACHE_ENABLED = _CONFIG.bool("rebsgo.gamedata.json-cache.enabled", True) and not vfs().pak_mod
_JSON_CACHE_DIR = Path(_CONFIG.string("rebsgo.gamedata.json-cache.dir", "cache/gamedata-json"))
_JSON_CACHE_STRICT_SIGNATURE = _CONFIG.bool("rebsgo.gamedata.json-cache.strict-signature", True)
_JSON_MEMORY_CACHE_ENABLED = _CONFIG.bool("rebsgo.gamedata.json-cache.memory.enabled", True)
_JSON_MEMORY_CACHE_MAX_ENTRIES = _CONFIG.int("rebsgo.gamedata.json-cache.memory.max-entries", 4096)
_JSON_CACHE_VERSION = 1
_CACHE_MISS = object()
_JSON_MEMORY_CACHE = {}
_JSON_MEMORY_CACHE_LOCK = threading.RLock()


class GameDataLoader:
    def __init__(self, sablon_ut):
        self.template_path = self._resolve_template_path(Path(sablon_ut))

    @staticmethod
    def _resolve_template_path(sablon_ut: Path) -> Path:
        if vfs().pak_mod:
            parts = sablon_ut.parts
            if parts and parts[0] != "GameData":
                return Path("GameData") / sablon_ut
            return sablon_ut
        if sablon_ut is not None and sablon_ut.exists():
            return sablon_ut
        parts = sablon_ut.parts
        if len(parts) == 0:
            return sablon_ut
        if parts[0] == "GameData" and len(parts) > 1:
            remainder = Path(*parts[1:])
        else:
            remainder = sablon_ut
        mostani = Path.cwd().resolve()
        while mostani is not None:
            jelolt = mostani / "GameData" / remainder
            if jelolt.exists():
                if GUARDRAILS_ENABLED:
                    log.info("GameDataLoader resolved '%s' to '%s'", sablon_ut, jelolt)
                return jelolt
            if mostani.parent == mostani:
                break
            mostani = mostani.parent
        return sablon_ut

    def raw_text(self, file_name) -> str | None:
        if file_name is None:
            return None
        path = Path(file_name)
        started_ms = now_ms() if GUARDRAILS_ENABLED else 0.0
        if vfs().pak_mod:
            szoveg = vfs().read_text(path)
            if szoveg is None:
                log.error("could not read %s from the pak", file_name)
            return szoveg
        try:
            szoveg = path.read_text(encoding="utf-8-sig")
            if GUARDRAILS_ENABLED:
                try:
                    size = path.stat().st_size
                except OSError:
                    size = -1
                warn_if_slow(
                    log,
                    elapsed_ms(started_ms),
                    GAMEDATA_FILE_WARN_MS,
                    "Slow GameData file read path=%s bytes=%s",
                    path,
                    size,
                )
            return szoveg
        except OSError as ex:
            log.error("could not read %s: %s", file_name, ex)
            return None

    def read_json(self, file_name):
        if file_name is None:
            return None
        path = Path(file_name)
        metadata_signature = self._file_metadata_signature(path) if _JSON_CACHE_ENABLED else None

        if (
                _JSON_CACHE_ENABLED
                and _JSON_MEMORY_CACHE_ENABLED
                and not _JSON_CACHE_STRICT_SIGNATURE
                and metadata_signature is not None
        ):
            cached = self._read_json_memory_cache(path, metadata_signature)
            if cached is not _CACHE_MISS:
                return cached

        raw_bytes = None
        if _JSON_CACHE_ENABLED and _JSON_CACHE_STRICT_SIGNATURE:
            raw_bytes = self._read_raw_bytes(path)
            if raw_bytes is None:
                return None
        signature = self._file_signature(path, raw_bytes, metadata_signature)

        if _JSON_CACHE_ENABLED and _JSON_MEMORY_CACHE_ENABLED and signature is not None:
            cached = self._read_json_memory_cache(path, signature)
            if cached is not _CACHE_MISS:
                return cached

        if _JSON_CACHE_ENABLED and signature is not None:
            cached = self._read_json_cache(path, signature)
            if cached is not _CACHE_MISS:
                self._write_json_memory_cache(path, signature, cached)
                return cached

        if raw_bytes is None:
            raw_text = self.raw_text(path)
            if raw_text is None:
                return None
        else:
            raw_text = raw_bytes.decode("utf-8-sig")
        parsed = json.loads(raw_text)

        if _JSON_CACHE_ENABLED and signature is not None:
            self._write_json_cache(path, signature, parsed)
            self._write_json_memory_cache(path, signature, parsed)
        return parsed

    @staticmethod
    def _read_raw_bytes(path: Path) -> bytes | None:
        started_ms = now_ms() if GUARDRAILS_ENABLED else 0.0
        if vfs().pak_mod:
            adat = vfs().read_bytes(path)
            if adat is None:
                log.error("could not read %s from the pak", path)
            return adat
        try:
            raw_bytes = path.read_bytes()
            if GUARDRAILS_ENABLED:
                warn_if_slow(
                    log,
                    elapsed_ms(started_ms),
                    GAMEDATA_FILE_WARN_MS,
                    "Slow GameData file read path=%s bytes=%s",
                    path,
                    len(raw_bytes),
                )
            return raw_bytes
        except OSError as ex:
            log.error("could not read %s: %s", path, ex)
            return None

    @staticmethod
    def _file_metadata_signature(path: Path) -> dict | None:
        try:
            stat = path.stat()
            return {
                "path": str(path.resolve()),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "ctime_ns": stat.st_ctime_ns,
            }
        except OSError:
            return None

    @staticmethod
    def _file_signature(path: Path, raw_bytes: bytes | None = None,
                        metadata_signature: dict | None = None) -> dict | None:
        signature = (
            dict(metadata_signature)
            if metadata_signature is not None
            else GameDataLoader._file_metadata_signature(path)
        )
        if signature is None:
            return None
        if raw_bytes is not None:
            signature["sha256"] = hashlib.sha256(raw_bytes).hexdigest()
        return signature

    @staticmethod
    def _json_cache_path(path: Path) -> Path:
        resolved = str(path.resolve())
        digest = hashlib.sha256(resolved.encode("utf-8")).hexdigest()
        cache_dir = _JSON_CACHE_DIR if _JSON_CACHE_DIR.is_absolute() else Path.cwd() / _JSON_CACHE_DIR
        return cache_dir / (digest + ".pickle")

    @staticmethod
    def _json_memory_cache_key(path: Path) -> str:
        return str(path.resolve())

    def _read_json_memory_cache(self, path: Path, metadata_signature: dict):
        kulcs = self._json_memory_cache_key(path)
        started_ms = now_ms() if GUARDRAILS_ENABLED else 0.0
        with _JSON_MEMORY_CACHE_LOCK:
            rakomany = _JSON_MEMORY_CACHE.get(kulcs)
            if (
                    rakomany is None
                    or rakomany.get("version") != _JSON_CACHE_VERSION
                    or rakomany.get("signature") != metadata_signature
            ):
                return _CACHE_MISS
            data = deepcopy(rakomany.get("data"))
        if GUARDRAILS_ENABLED:
            warn_if_slow(
                log,
                elapsed_ms(started_ms),
                GAMEDATA_CACHE_WARN_MS,
                "Slow GameData json memory cache read source=%s",
                path,
            )
        return data

    def _write_json_memory_cache(self, path: Path, metadata_signature: dict | None, parsed) -> None:
        if not (_JSON_CACHE_ENABLED and _JSON_MEMORY_CACHE_ENABLED and metadata_signature is not None):
            return
        kulcs = self._json_memory_cache_key(path)
        rakomany = {
            "version": _JSON_CACHE_VERSION,
            "signature": dict(metadata_signature),
            "data": deepcopy(parsed),
        }
        with _JSON_MEMORY_CACHE_LOCK:
            if _JSON_MEMORY_CACHE_MAX_ENTRIES > 0 and len(_JSON_MEMORY_CACHE) >= _JSON_MEMORY_CACHE_MAX_ENTRIES:
                _JSON_MEMORY_CACHE.pop(next(iter(_JSON_MEMORY_CACHE)), None)
            _JSON_MEMORY_CACHE[kulcs] = rakomany

    def _read_json_cache(self, path: Path, signature: dict):
        cache_path = self._json_cache_path(path)
        started_ms = now_ms() if GUARDRAILS_ENABLED else 0.0
        try:
            with cache_path.open("rb") as fh:
                rakomany = pickle.load(fh)
        except FileNotFoundError:
            return _CACHE_MISS
        except (OSError, pickle.PickleError, EOFError, ValueError, TypeError):
            if GUARDRAILS_ENABLED:
                log.warning("Ignoring invalid GameData json cache path=%s", cache_path)
            with suppress(OSError):
                cache_path.unlink(missing_ok=True)
            return _CACHE_MISS

        if rakomany.get("version") != _JSON_CACHE_VERSION or rakomany.get("signature") != signature:
            return _CACHE_MISS

        if GUARDRAILS_ENABLED:
            warn_if_slow(
                log,
                elapsed_ms(started_ms),
                GAMEDATA_CACHE_WARN_MS,
                "Slow GameData json cache read source=%s cache=%s",
                path,
                cache_path,
            )
        return rakomany.get("data")

    def _write_json_cache(self, path: Path, signature: dict, parsed) -> None:
        cache_path = self._json_cache_path(path)
        tmp_name = None
        rakomany = {
            "version": _JSON_CACHE_VERSION,
            "signature": signature,
            "data": parsed,
        }
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("wb", dir=cache_path.parent, delete=False) as fh:
                tmp_name = fh.name
                pickle.dump(rakomany, fh, protocol=pickle.HIGHEST_PROTOCOL)
            Path(tmp_name).replace(cache_path)
        except OSError as ex:
            if GUARDRAILS_ENABLED:
                log.warning("Could not write GameData json cache source=%s cache=%s error=%s", path, cache_path, ex)
            if tmp_name is not None:
                with suppress(OSError):
                    Path(tmp_name).unlink(missing_ok=True)

    def file_paths(self) -> list[Path]:
        if vfs().pak_mod:
            return vfs().json_paths_under(self.template_path)
        if not self.template_path.exists():
            log.warning("GameDataLoader could not read template_path='%s' (returning empty list)", self.template_path)
            return []
        return [f for f in sorted(self.template_path.rglob("*.json")) if "!" not in str(f)]
