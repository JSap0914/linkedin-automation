from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.syntax import Syntax

from bot.config import RepliesConfig
from bot.config_defaults import default_config_dict
from bot.config_io import (
    ConfigIOError,
    DEFAULT_PATH,
    dump_raw,
    load_raw,
    parse_value,
    set_by_path,
)

console = Console()
err_console = Console(stderr=True)

app = typer.Typer(name="config", help="View and edit replies.yaml")


def _validate_or_exit(data: dict) -> RepliesConfig:
    try:
        return RepliesConfig(**data)
    except ValidationError as exc:
        err_console.print(f"[red]Config validation failed:[/red]\n{exc}")
        raise typer.Exit(code=1) from exc


@app.command(name="show")
def show() -> None:
    data = load_raw()
    if not data:
        err_console.print(
            f"[yellow]{DEFAULT_PATH} is empty or missing. "
            f"Run 'linkedin-autoreply init' or 'linkedin-autoreply config reset'.[/yellow]"
        )
        raise typer.Exit(code=1)
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    console.print(Syntax(text, "yaml", background_color="default"))


@app.command(name="set")
def set_value(
    path: str = typer.Argument(..., help="Dotted path, e.g. dm.max_per_day"),
    value: str = typer.Argument(..., help="Value (auto-parsed: bool/int/json/str)"),
) -> None:
    try:
        parsed = parse_value(value)
    except ConfigIOError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    data = load_raw()
    try:
        set_by_path(data, path, parsed)
    except ConfigIOError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    _validate_or_exit(data)
    dump_raw(data)
    console.print(f"[green]OK[/green] {path} = {parsed!r}")


@app.command(name="edit")
def edit() -> None:
    if not DEFAULT_PATH.exists():
        err_console.print(
            f"[yellow]{DEFAULT_PATH} not found. Run 'linkedin-autoreply config reset' first.[/yellow]"
        )
        raise typer.Exit(code=1)

    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if not editor:
        for candidate in ("vi", "nano", "notepad"):
            if shutil.which(candidate):
                editor = candidate
                break
    if not editor:
        err_console.print("[red]No $EDITOR set and no vi/nano/notepad found.[/red]")
        raise typer.Exit(code=1)

    result = subprocess.run([editor, str(DEFAULT_PATH)], check=False)
    if result.returncode != 0:
        err_console.print(f"[red]Editor exited with code {result.returncode}.[/red]")
        raise typer.Exit(code=result.returncode)

    data = load_raw()
    _validate_or_exit(data)
    console.print(f"[green]OK[/green] {DEFAULT_PATH} saved and validated.")


@app.command(name="wizard")
def wizard() -> None:
    from bot.onboarding import OnboardingWizard
    from bot.onboarding.wizard import OnboardingWizard as W

    w = OnboardingWizard(steps=W.CONFIG_ONLY_STEPS)
    ok = w.run()
    raise typer.Exit(code=0 if ok else 1)


@app.command(name="reset")
def reset(
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
) -> None:
    if DEFAULT_PATH.exists() and not yes:
        if not sys.stdin.isatty():
            err_console.print(
                f"[red]{DEFAULT_PATH} exists and stdin is not a TTY. Pass -y to overwrite.[/red]"
            )
            raise typer.Exit(code=1)
        resp = input(f"{DEFAULT_PATH} exists. Overwrite with defaults? [y/N] ").strip().lower()
        if resp not in ("y", "yes"):
            console.print("Cancelled.")
            raise typer.Exit(code=0)

    defaults = default_config_dict()
    _validate_or_exit(defaults)
    dump_raw(defaults)
    console.print(f"[green]OK[/green] {DEFAULT_PATH} reset to defaults.")


@app.command(name="migrate")
def migrate() -> None:
    console.print("[yellow]config migrate — not yet implemented (Task 7).[/yellow]")
    raise typer.Exit(code=0)
