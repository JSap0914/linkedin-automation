#!/usr/bin/env python3
from __future__ import annotations

import sys

from bot.cli import app


if __name__ == "__main__":
    app(["run", *sys.argv[1:]])
