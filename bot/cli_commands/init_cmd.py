from __future__ import annotations

import typer

from bot.onboarding import OnboardingWizard


def run() -> None:
    wizard = OnboardingWizard()
    ok = wizard.run()
    raise typer.Exit(code=0 if ok else 1)
