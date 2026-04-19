from __future__ import annotations

from typing import Any

from rich.console import Console

from bot.onboarding.steps import (
    BaseStep,
    BootstrapStep,
    DmConfigStep,
    FinalStep,
    LoginStep,
    PrereqStep,
    ReplyConfigStep,
    SchedulerInstallStep,
    TosStep,
    WriteConfigStep,
)

console = Console()


class OnboardingWizard:
    FULL_STEPS: list[type[BaseStep]] = [
        TosStep,
        PrereqStep,
        LoginStep,
        ReplyConfigStep,
        DmConfigStep,
        WriteConfigStep,
        BootstrapStep,
        SchedulerInstallStep,
        FinalStep,
    ]

    CONFIG_ONLY_STEPS: list[type[BaseStep]] = [
        ReplyConfigStep,
        DmConfigStep,
        WriteConfigStep,
    ]

    def __init__(self, steps: list[type[BaseStep]] | None = None) -> None:
        self.steps = steps if steps is not None else self.FULL_STEPS

    def run(self, state: dict[str, Any] | None = None) -> bool:
        state = state if state is not None else {}
        for step_cls in self.steps:
            step = step_cls()
            console.print(f"\n[bold cyan]>> {step.name}[/bold cyan]")
            try:
                ok = step.run(state)
            except KeyboardInterrupt:
                console.print("\n[yellow]Cancelled by user.[/yellow]")
                return False
            if not ok:
                console.print(f"[yellow]Stopped at step: {step.name}[/yellow]")
                return False
        return True
