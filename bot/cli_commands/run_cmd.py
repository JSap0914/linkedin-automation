from __future__ import annotations

import typer


def run(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be replied without posting"),
    bootstrap: bool = typer.Option(False, "--bootstrap", help="Mark all existing comments as seen"),
) -> None:
    from bot.orchestrator import run as orchestrator_run

    orchestrator_run(dry_run=dry_run, bootstrap=bootstrap)
