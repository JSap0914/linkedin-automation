from __future__ import annotations

import sys
from pathlib import Path


def ask(prompt: str, default: str = "y") -> bool:
    resp = input(f"{prompt} [{'Y/n' if default == 'y' else 'y/N'}] ").strip().lower()
    if not resp:
        return default == "y"
    return resp in ("y", "yes")


def _do_login(profile_dir: Path) -> None:
    print("\nOpening browser for LinkedIn login...")
    print("Please log in to LinkedIn in the browser window that appears.")
    print("You have 5 minutes.")
    print()

    from bot.auth import LoginTimeoutError, first_login

    try:
        first_login(profile_dir)
        print("✅ Login successful. Profile saved.")
    except LoginTimeoutError:
        print("❌ Login timed out. Please run `linkedin-autoreply setup` again.")
        sys.exit(1)


def main() -> None:
    print("=" * 50)
    print("  LinkedIn Auto-Reply Bot — Setup Wizard")
    print("=" * 50)
    print()

    profile_dir = Path(".profile/")
    cache_dir = Path(".cache/")
    cache_dir.mkdir(exist_ok=True)

    from bot.logging_config import configure_logging

    configure_logging(Path("logs/setup.log"))

    if profile_dir.exists() and any(profile_dir.iterdir()):
        if not ask("Profile exists. Re-login to LinkedIn?", default="n"):
            print("Using existing profile.")
        else:
            _do_login(profile_dir)
    else:
        _do_login(profile_dir)

    print("\nExtracting session cookies...")
    from bot.auth import extract_cookies, get_or_discover_own_urn

    try:
        cookies = extract_cookies(profile_dir)
    except Exception as exc:
        print(f"\n❌ Could not extract cookies: {exc}")
        print("Please run `linkedin-autoreply setup` again and complete the login.")
        sys.exit(1)

    own_urn = get_or_discover_own_urn(cookies)
    print(f"✅ Own URN: {own_urn}")

    if ask(
        "\nBootstrap existing comments? (Recommended — prevents replying to old comments)",
        default="y",
    ):
        print("Bootstrapping...")
        from bot.orchestrator import run as orchestrator_run

        orchestrator_run(bootstrap=True)
        print("✅ Existing comments marked as seen.")

    print()
    print("=" * 50)
    print("  Setup Complete!")
    print("=" * 50)
    print()
    print("Next steps:")
    print("  1. Install scheduler:   linkedin-autoreply start")
    print("  2. Edit templates:      linkedin-autoreply config edit")
    print("  3. Disable anytime:     linkedin-autoreply config set enabled false")
    print("  4. Dry run:             linkedin-autoreply run --dry-run")
    print("  5. Check logs:          linkedin-autoreply logs")
    print()


if __name__ == "__main__":
    main()
