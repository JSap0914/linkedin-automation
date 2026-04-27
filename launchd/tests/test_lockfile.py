# pyright: reportMissingImports=false

from __future__ import annotations

import subprocess
import sys
import textwrap
import os
from pathlib import Path

import pytest

from bot.lockfile import AlreadyRunningError, acquire_lock


def test_acquire_release_cleans_up(tmp_path):
    lock_path = tmp_path / "bot.lock"

    with acquire_lock(lock_path):
        assert lock_path.exists()
        assert lock_path.read_text().splitlines()[0] == str(os.getpid())

    assert not lock_path.exists()


def test_concurrent_raises(tmp_path):
    lock_path = tmp_path / "bot.lock"
    script = textwrap.dedent(
        """
        import sys
        import time
        from pathlib import Path

        from bot.lockfile import acquire_lock

        path = Path(sys.argv[1])
        with acquire_lock(path):
            print('ready', flush=True)
            time.sleep(5)
        """
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", script, str(lock_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    try:
        assert proc.stdout is not None
        assert proc.stdout.readline().strip() == "ready"

        with pytest.raises(AlreadyRunningError):
            with acquire_lock(lock_path):
                pass
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_stale_lock_recovery(tmp_path):
    lock_path = tmp_path / "bot.lock"
    lock_path.write_text("99999999\n2020-01-01T00:00:00Z\n")

    with acquire_lock(lock_path):
        assert lock_path.exists()
