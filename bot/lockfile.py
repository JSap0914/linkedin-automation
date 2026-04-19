from __future__ import annotations

import fcntl
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


class AlreadyRunningError(RuntimeError):
    pass


@contextmanager
def acquire_lock(lock_path: Path) -> Iterator[None]:
    lock_path = Path(lock_path)
    pid: int | None = None
    if lock_path.exists():
        try:
            pid = int(lock_path.read_text().split("\n")[0].strip())
            os.kill(pid, 0)
        except (ProcessLookupError, OSError):
            logger.warning("Stale lock for PID %s, removing", pid)
            lock_path.unlink(missing_ok=True)
        except ValueError:
            lock_path.unlink(missing_ok=True)

    fd = open(lock_path, "w")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
        fd.close()
        raise AlreadyRunningError(f"Another instance holds {lock_path}")

    fd.write(f"{os.getpid()}\n{datetime.now(timezone.utc).isoformat()}Z\n")
    fd.flush()

    try:
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()
        lock_path.unlink(missing_ok=True)
