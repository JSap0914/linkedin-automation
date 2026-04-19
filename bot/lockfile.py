from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from filelock import FileLock, Timeout

logger = logging.getLogger(__name__)


class AlreadyRunningError(RuntimeError):
    pass


def _sidecar_path(lock_path: Path) -> Path:
    return lock_path.with_name(lock_path.name + ".lock")


@contextmanager
def acquire_lock(lock_path: Path) -> Iterator[None]:
    """Non-blocking lock; writes PID+UTC-ISO to lock_path, raises AlreadyRunningError on contention.

    Cross-platform via filelock (fcntl on POSIX, msvcrt on Windows); OS releases stale locks on crash.
    """
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    sidecar = _sidecar_path(lock_path)
    lock = FileLock(str(sidecar), timeout=0)

    try:
        lock.acquire()
    except Timeout as exc:
        raise AlreadyRunningError(f"Another instance holds {lock_path}") from exc

    try:
        lock_path.write_text(
            f"{os.getpid()}\n{datetime.now(timezone.utc).isoformat()}Z\n"
        )
        yield
    finally:
        try:
            lock.release()
        finally:
            lock_path.unlink(missing_ok=True)
            try:
                sidecar.unlink(missing_ok=True)
            except OSError:
                # Sidecar may be held momentarily on Windows — best-effort cleanup.
                logger.debug("Could not remove lock sidecar %s", sidecar)
