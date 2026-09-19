# github.com/Shran21

from __future__ import annotations

import subprocess

from panel.settings import GAME_ROOT


def _read() -> str:
    marker = GAME_ROOT / "VERSION"
    if marker.is_file():
        try:
            text = marker.read_text(encoding="utf-8").strip()
            if text:
                return text[:40]
        except OSError:
            pass
    if (GAME_ROOT / ".git").exists():
        try:
            out = subprocess.run(["git", "-C", str(GAME_ROOT), "rev-parse", "--short", "HEAD"],
                                 capture_output=True, text=True, timeout=3)
            if out.returncode == 0 and out.stdout.strip():
                return "git " + out.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    return "dev"


VERSION = _read()
