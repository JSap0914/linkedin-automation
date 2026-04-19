from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console

from bot.scheduler import UnsupportedPlatformError, get_scheduler

console = Console()
err_console = Console(stderr=True)


def _project_root() -> Path:
    return Path.cwd()


def _python_path() -> Path:
    return Path(sys.executable)


def start() -> None:
    sched = get_scheduler()
    try:
        sched.install(project_root=_project_root(), python_path=_python_path())
    except UnsupportedPlatformError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(code=0) from exc
    status = sched.status()
    console.print(
        f"[green]OK[/green] Scheduler installed and enabled.\n"
        f"  Label: {status.label}\n"
        f"  Interval: {status.interval_seconds}s"
    )


def stop() -> None:
    sched = get_scheduler()
    try:
        sched.disable()
    except UnsupportedPlatformError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(code=0) from exc
    console.print("[green]OK[/green] Scheduler disabled (entry kept for re-enable).")


def uninstall() -> None:
    sched = get_scheduler()
    try:
        sched.uninstall()
    except UnsupportedPlatformError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(code=0) from exc
    console.print("[green]OK[/green] Scheduler uninstalled.")
