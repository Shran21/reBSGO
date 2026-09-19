# github.com/Shran21

from __future__ import annotations

import logging
import logging.handlers

from panel.settings import ROOT

_LOG_DIR = ROOT / "logs"


def _logger() -> logging.Logger:
    logger = logging.getLogger("panel.audit")
    if logger.handlers:
        return logger
    _LOG_DIR.mkdir(exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        _LOG_DIR / "panel-audit.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def record(who: str, action: str, *, target: str = "", outcome: str = "ok") -> None:
    _logger().info("who=%s action=%s target=%s outcome=%s", who, action, target, outcome)
