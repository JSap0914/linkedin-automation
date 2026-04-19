from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from bot import updater
from bot.config_io import DEFAULT_PATH, dump_raw, load_raw
from bot.config_migrate import MigrationError, migrate
from bot.scheduler import UnsupportedPlatformError, get_scheduler

console = Console()
err_console = Console(stderr=True)


def _reinstall_scheduler() -> bool:
    sched = get_scheduler()
    try:
        sched.uninstall()
        sched.install(project_root=Path.cwd(), python_path=Path.cwd() / ".venv" / "bin" / "python")
        return True
    except UnsupportedPlatformError:
        return False


def run(
    dry_run: bool = typer.Option(False, "--dry-run", help="Inspect only, no pull/install/migrate"),
    skip_tests: bool = typer.Option(False, "--skip-tests", help="Skip post-update pytest smoke"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip interactive confirmations"),
) -> None:
    result = updater.UpdateResult(dry_run=dry_run)

    dirty = updater.is_dirty()
    if dirty:
        err_console.print(
            f"[red]Working tree is dirty. Commit or stash before update:[/red]\n{dirty}"
        )
        raise typer.Exit(code=1)

    result.pre_sha = updater.current_sha()

    if dry_run:
        console.print(f"[cyan][dry-run][/cyan] Pre-update SHA: {result.pre_sha}")
        console.print("[cyan][dry-run][/cyan] Would run: git pull --ff-only origin main")
        console.print("[green]OK[/green] Dry run complete.")
        raise typer.Exit(code=0)

    try:
        updater.pull_ff_only()
    except updater.UpdateError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    result.pulled = True
    result.post_sha = updater.current_sha()

    if result.pre_sha == result.post_sha:
        console.print("[green]OK[/green] Already up to date.")
        raise typer.Exit(code=0)

    result.changed_files = updater.changed_paths_between(result.pre_sha, result.post_sha)
    drift = updater.detect_drift(result.changed_files)

    if drift["pyproject"]:
        console.print("[cyan]•[/cyan] pyproject.toml changed — running pip install -e .[dev]")
        try:
            updater.pip_install_editable()
            result.pip_installed = True
        except updater.UpdateError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc

    if drift["config_schema"] and DEFAULT_PATH.exists():
        console.print("[cyan]•[/cyan] Config schema changed — running migration")
        current = load_raw()
        try:
            merged, added, removed = migrate(current)
        except MigrationError as exc:
            err_console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc
        if added or removed:
            dump_raw(merged)
            result.config_migrated_added = added
            result.config_migrated_removed = removed
            if added:
                console.print(f"  Added: {', '.join(added)}")
            if removed:
                console.print(f"  Removed unknown fields: {', '.join(removed)}")
        else:
            console.print("  No config changes needed.")

    if drift["scheduler_templates"]:
        console.print("[cyan]•[/cyan] Scheduler template changed — reinstalling scheduler")
        if _reinstall_scheduler():
            result.scheduler_reinstalled = True
        else:
            console.print("  (Scheduler not supported on this platform — skipped)")

    if not skip_tests:
        console.print("[cyan]•[/cyan] Running post-update test smoke")
        passed = updater.run_pytest_smoke()
        result.tests_passed = passed
        if not passed:
            err_console.print("[red]pytest failed after update — review output above[/red]")
            raise typer.Exit(code=1)

    console.print(
        f"\n[green]OK[/green] Updated {result.pre_sha[:8]} -> {result.post_sha[:8]}. "
        f"pip_installed={result.pip_installed}, "
        f"config_migrated={'yes' if result.config_migrated_added or result.config_migrated_removed else 'no'}, "
        f"scheduler_reinstalled={result.scheduler_reinstalled}, "
        f"tests_passed={result.tests_passed}"
    )
    raise typer.Exit(code=0)
