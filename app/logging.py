from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.config import settings

_CONFIGURED = False


def _configure_once() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(settings.log_dir / "contxt.log", maxBytes=5_000_000, backupCount=3)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger("contxt")
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure_once()
    return logging.getLogger(name)
