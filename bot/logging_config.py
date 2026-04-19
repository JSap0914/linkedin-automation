from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
MAX_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 3


def configure_logging(log_path: Path) -> logging.Logger:
    logger = logging.getLogger("bot")
    level = logging.DEBUG if os.environ.get("BOT_DEBUG") == "1" else logging.INFO
    logger.setLevel(level)
    logger.propagate = False

    if any(getattr(handler, "_bot_logging_configured", False) for handler in logger.handlers):
        return logger

    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(LOG_FORMAT)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    file_handler._bot_logging_configured = True  # type: ignore[attr-defined]

    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(level)
    stderr_handler.setFormatter(formatter)
    stderr_handler._bot_logging_configured = True  # type: ignore[attr-defined]

    logger.addHandler(file_handler)
    logger.addHandler(stderr_handler)
    return logger
