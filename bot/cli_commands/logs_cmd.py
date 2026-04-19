from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

console = Console()
err_console = Console(stderr=True)

LOG_PATH = Path("logs/bot.log")


def run(
    n: int = typer.Option(50, "-n", "--lines", help="Number of lines to show"),
) -> None:
    if not LOG_PATH.exists():
        console.print(f"[yellow]No logs yet at {LOG_PATH}.[/yellow]")
        raise typer.Exit(code=0)

    with LOG_PATH.open("r", encoding="utf-8", errors="replace") as handle:
        lines = handle.readlines()
    tail = lines[-n:]
    for line in tail:
        console.out(line.rstrip("\n"))
    raise typer.Exit(code=0)
