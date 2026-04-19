from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from bot.scheduler import get_scheduler

console = Console()

LOG_PATH = Path("logs/bot.log")
LOCK_PATH = Path("logs/bot.lock")


def _tail_log(n: int = 20) -> list[str]:
    if not LOG_PATH.exists():
        return []
    with LOG_PATH.open("r", encoding="utf-8", errors="replace") as handle:
        return handle.readlines()[-n:]


def run() -> None:
    sched = get_scheduler()
    status = sched.status()

    table = Table(title="LinkedIn Auto-Reply Status", show_header=False)
    table.add_column("Field", style="cyan")
    table.add_column("Value")
    table.add_row("Label", status.label)
    table.add_row("Installed", "yes" if status.installed else "no")
    table.add_row("Enabled", "yes" if status.enabled else "no")
    table.add_row("Interval", f"{status.interval_seconds}s")
    table.add_row("Last run", str(status.last_run) if status.last_run else "never")
    table.add_row("Lockfile", "held" if LOCK_PATH.exists() else "free")
    console.print(table)

    tail = _tail_log(20)
    if tail:
        console.print("\n[cyan]Recent log tail:[/cyan]")
        console.print("".join(tail).rstrip())
    else:
        console.print(f"\n[yellow]No logs yet at {LOG_PATH}.[/yellow]")

    raise typer.Exit(code=0)
