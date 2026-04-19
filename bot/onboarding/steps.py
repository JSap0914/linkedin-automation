from __future__ import annotations

import abc
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any

import questionary
from rich.console import Console

from bot.config_defaults import default_config_dict
from bot.config_io import DEFAULT_PATH, dump_raw
from bot.scheduler import UnsupportedPlatformError, get_scheduler

console = Console()

GITHUB_REPO = "JSap0914/linkedin-automation"


class BaseStep(abc.ABC):
    name: str = ""

    @abc.abstractmethod
    def run(self, state: dict[str, Any]) -> bool: ...


def _confirm(prompt: str, default: bool = True) -> bool | None:
    return questionary.confirm(prompt, default=default).ask()


def _text(prompt: str, default: str = "", validate=None) -> str | None:
    return questionary.text(prompt, default=default, validate=validate).ask()


def _is_positive_int(v: str) -> bool | str:
    if not v.isdigit():
        return "Must be a non-negative integer"
    return True


class TosStep(BaseStep):
    name = "ToS acknowledgement"

    def run(self, state: dict) -> bool:
        console.print(
            "[bold yellow]⚠ LinkedIn User Agreement prohibits automation. "
            "This tool operates in a gray zone on your own posts, low volume. "
            "Risk is real.[/bold yellow]\n"
        )
        answer = _confirm("Do you accept the risk and continue?", default=False)
        if not answer:
            return False
        state["tos_accepted"] = True
        return True


class PrereqStep(BaseStep):
    name = "Prerequisite check"

    def run(self, state: dict) -> bool:
        console.print("[cyan]Checking prerequisites...[/cyan]")
        if sys.version_info < (3, 11):
            console.print("[red]Python 3.11+ required.[/red]")
            return False
        try:
            import scrapling
        except ImportError:
            console.print("[red]scrapling not installed. Run `pip install -e .[dev]` first.[/red]")
            return False
        console.print("[green]OK[/green] Python version + scrapling OK")
        state["prereq_ok"] = True
        return True


class LoginStep(BaseStep):
    name = "LinkedIn login"

    def run(self, state: dict) -> bool:
        console.print("[cyan]Opening browser for LinkedIn login...[/cyan]")
        profile_dir = Path(".profile/")
        cache_dir = Path(".cache/")
        cache_dir.mkdir(exist_ok=True)

        from bot.auth import (
            LoginTimeoutError,
            extract_cookies,
            first_login,
            get_or_discover_own_urn,
        )

        if profile_dir.exists() and any(profile_dir.iterdir()):
            if not _confirm("Profile exists. Re-login to LinkedIn?", default=False):
                console.print("Using existing profile.")
            else:
                try:
                    first_login(profile_dir)
                except LoginTimeoutError:
                    console.print("[red]Login timed out.[/red]")
                    return False
        else:
            try:
                first_login(profile_dir)
            except LoginTimeoutError:
                console.print("[red]Login timed out.[/red]")
                return False

        try:
            cookies = extract_cookies(profile_dir)
        except Exception as exc:
            console.print(f"[red]Cookie extraction failed: {exc}[/red]")
            return False

        own_urn = get_or_discover_own_urn(cookies)
        console.print(f"[green]OK[/green] Own URN: {own_urn}")
        state["own_urn"] = own_urn
        return True


class ReplyConfigStep(BaseStep):
    name = "Reply config"

    def run(self, state: dict) -> bool:
        defaults = state.setdefault("config", default_config_dict())

        defaults["enabled"] = bool(_confirm("Enable auto-reply?", default=True))

        if not _confirm("Use the default 3 Korean thank-you replies?", default=True):
            lines: list[str] = []
            for i in range(3):
                line = _text(f"Reply template #{i + 1}:", default=defaults["sentences"][i])
                if line is None:
                    return False
                lines.append(line.strip() or defaults["sentences"][i])
            defaults["sentences"] = lines

        raw = _text("Reply delay (seconds, 0 = instant):", default="0", validate=_is_positive_int)
        if raw is None:
            return False
        delay = int(raw)
        defaults["reply_delay_seconds_min"] = delay
        defaults["reply_delay_seconds_max"] = delay

        raw = _text(
            "Check new comments every N seconds (>=60):",
            default="60",
            validate=lambda v: (v.isdigit() and int(v) >= 60) or "Must be >= 60",
        )
        if raw is None:
            return False
        defaults["polling_min_interval_seconds"] = int(raw)

        return True


class DmConfigStep(BaseStep):
    name = "DM config"

    def run(self, state: dict) -> bool:
        defaults = state.setdefault("config", default_config_dict())
        dm = defaults["dm"]

        dm["enabled"] = bool(_confirm("Enable auto-DM?", default=False))
        if not dm["enabled"]:
            return True

        dm["only_first_degree_connections"] = bool(
            _confirm("Only DM 1st-degree connections? (recommended)", default=True)
        )
        dm["auto_accept_pending_invitations"] = bool(
            _confirm("Auto-accept pending invitations from commenters?", default=True)
        )

        if not _confirm("Use the default 3 Korean DM messages?", default=True):
            lines: list[str] = []
            for i in range(3):
                line = _text(f"DM template #{i + 1}:", default=dm["messages"][i])
                if line is None:
                    return False
                lines.append(line.strip() or dm["messages"][i])
            dm["messages"] = lines

        raw = _text("Max DMs per day:", default="30", validate=_is_positive_int)
        if raw is None:
            return False
        dm["max_per_day"] = int(raw)

        raw = _text("DM delay (seconds, 0 = instant):", default="0", validate=_is_positive_int)
        if raw is None:
            return False
        delay = int(raw)
        dm["delay_seconds_min"] = delay
        dm["delay_seconds_max"] = delay

        return True


class WriteConfigStep(BaseStep):
    name = "Write config"

    def run(self, state: dict) -> bool:
        from bot.config import RepliesConfig
        from pydantic import ValidationError

        config_dict = state.get("config")
        if not isinstance(config_dict, dict):
            console.print("[red]No config in state. Aborting.[/red]")
            return False

        try:
            RepliesConfig(**config_dict)
        except ValidationError as exc:
            console.print(f"[red]Final config invalid:[/red]\n{exc}")
            return False

        if DEFAULT_PATH.exists():
            if not _confirm(f"{DEFAULT_PATH} exists. Overwrite?", default=False):
                console.print("Kept existing config.")
                return True

        dump_raw(config_dict)
        console.print(f"[green]OK[/green] Wrote {DEFAULT_PATH}")
        return True


class BootstrapStep(BaseStep):
    name = "Bootstrap existing comments"

    def run(self, state: dict) -> bool:
        if not _confirm(
            "Bootstrap existing comments? (Recommended — marks current comments as seen)",
            default=True,
        ):
            console.print("Skipped bootstrap.")
            return True
        console.print("[cyan]Bootstrapping...[/cyan]")
        from bot.orchestrator import run as orchestrator_run

        try:
            orchestrator_run(bootstrap=True)
        except Exception as exc:
            console.print(f"[yellow]Bootstrap encountered error: {exc}[/yellow]")
            return True
        console.print("[green]OK[/green] Existing comments marked as seen.")
        return True


class SchedulerInstallStep(BaseStep):
    name = "Install scheduler"

    def run(self, state: dict) -> bool:
        if not _confirm("Install scheduler (launchd / Task Scheduler)?", default=True):
            console.print("Skipped scheduler install. Run `linkedin-autoreply start` later.")
            return True

        sched = get_scheduler()
        try:
            sched.install(project_root=Path.cwd(), python_path=Path(sys.executable))
        except UnsupportedPlatformError as exc:
            console.print(f"[yellow]{exc}[/yellow]")
            return True
        except Exception as exc:
            console.print(f"[yellow]Scheduler install failed: {exc}[/yellow]")
            return True
        console.print("[green]OK[/green] Scheduler installed and enabled.")
        return True


class GitHubStarStep(BaseStep):
    name = "Star on GitHub"
    REPO = GITHUB_REPO

    def _is_interactive(self) -> bool:
        import os
        return sys.stdin.isatty() and not os.environ.get("CI")

    def _gh_available(self) -> bool:
        return shutil.which("gh") is not None

    def _already_starred(self) -> bool:
        result = subprocess.run(
            ["gh", "api", f"/user/starred/{self.REPO}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        return result.returncode == 0

    def _star_via_gh(self) -> bool:
        result = subprocess.run(
            ["gh", "api", "--silent", "--method", "PUT", f"/user/starred/{self.REPO}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        return result.returncode == 0

    def run(self, state: dict) -> bool:
        if not self._is_interactive():
            return True

        if self._gh_available():
            try:
                if self._already_starred():
                    console.print("[green]⭐ Already starred — thanks![/green]")
                    return True
            except subprocess.TimeoutExpired:
                pass

            if not _confirm(
                "Star linkedin-automation on GitHub? (takes 1 second, helps a ton 🙏)",
                default=True,
            ):
                console.print("No worries — skipping star.")
                return True

            try:
                if self._star_via_gh():
                    console.print("[green]⭐ Starred! Thanks for the support.[/green]")
                    return True
            except subprocess.TimeoutExpired:
                pass

        if not _confirm(
            "Star linkedin-automation on GitHub? (opens in your browser)",
            default=True,
        ):
            return True
        url = f"https://github.com/{self.REPO}"
        try:
            webbrowser.open(url)
        except Exception:
            pass
        console.print(f"[green]Opened[/green] {url} — thanks for starring!")
        return True


class FinalStep(BaseStep):
    name = "Done"

    def run(self, state: dict) -> bool:
        console.print("\n[bold green]Setup complete![/bold green]\n")
        console.print("Next commands:")
        console.print("  [cyan]linkedin-autoreply status[/cyan]        — check scheduler")
        console.print("  [cyan]linkedin-autoreply logs[/cyan]          — tail logs")
        console.print("  [cyan]linkedin-autoreply config show[/cyan]   — view config")
        console.print("  [cyan]linkedin-autoreply run --dry-run[/cyan] — test a single cycle")
        console.print("  [cyan]linkedin-autoreply update[/cyan]        — pull latest code")
        return True
