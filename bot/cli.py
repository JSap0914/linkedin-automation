from __future__ import annotations

import typer

from bot.cli_commands import (
    config_cmd,
    init_cmd,
    logs_cmd,
    run_cmd,
    scheduler_cmd,
    setup_cmd,
    status_cmd,
    update_cmd,
)

app = typer.Typer(
    name="linkedin-autoreply",
    help="LinkedIn comment auto-reply bot",
    no_args_is_help=True,
    add_completion=True,
)

app.command(name="init", help="First-time setup wizard (login + config + scheduler)")(init_cmd.run)
app.command(name="run", help="Run one poll/reply cycle")(run_cmd.run)
app.command(name="setup", help="Re-login to LinkedIn (no config changes)")(setup_cmd.run)
app.command(name="update", help="Pull latest code + migrate config + reinstall scheduler")(update_cmd.run)
app.command(name="start", help="Install + enable scheduler (launchd / Task Scheduler)")(scheduler_cmd.start)
app.command(name="stop", help="Disable scheduler (keep entry)")(scheduler_cmd.stop)
app.command(name="uninstall", help="Disable + remove scheduler entry")(scheduler_cmd.uninstall)
app.command(name="status", help="Show scheduler state + recent logs")(status_cmd.run)
app.command(name="logs", help="Tail the bot log file")(logs_cmd.run)

app.add_typer(config_cmd.app, name="config")


if __name__ == "__main__":
    app()
