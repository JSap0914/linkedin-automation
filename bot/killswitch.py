from __future__ import annotations

import logging
import sys

from bot.config import RepliesConfig

logger = logging.getLogger(__name__)


def check_kill_switch(config: RepliesConfig) -> None:
    """MUST be called FIRST in main flow, before auth/Voyager/SQLite."""
    if config.enabled is False:
        logger.info("Kill switch active (replies.yaml enabled: false) — exiting cleanly")
        sys.exit(0)
