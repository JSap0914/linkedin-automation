#!/usr/bin/env python3
import sys
import importlib.util
from collections.abc import Callable
from pathlib import Path


"""First-run setup wizard for LinkedIn Auto-Reply Bot."""


def _load_run() -> Callable[..., None]:
    orchestrator_path = Path(__file__).with_name("bot") / "orchestrator.py"
    spec = importlib.util.spec_from_file_location("linkedin_autoreply_orchestrator", orchestrator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load orchestrator from {orchestrator_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run


def ask(prompt: str, default: str = "y") -> bool:
    resp = input(f"{prompt} [{'Y/n' if default == 'y' else 'y/N'}] ").strip().lower()
    if not resp:
        return default == "y"
    return resp in ("y", "yes")


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
        print("Please run setup.py again and complete the login.")
        sys.exit(1)

    own_urn = get_or_discover_own_urn(cookies)
    print(f"✅ Own URN: {own_urn}")

    if ask(
        "\nBootstrap existing comments? (Recommended — prevents replying to old comments)",
        default="y",
    ):
        print("Bootstrapping...")
        run = _load_run()
        run(bootstrap=True)
        print("✅ Existing comments marked as seen.")

    print()
    print("=" * 50)
    print("  Setup Complete!")
    print("=" * 50)
    print()
    print("Next steps:")
    print("  1. Install auto-polling:  bash launchd/install.sh")
    print("  2. Edit sentences:        nano replies.yaml")
    print("  3. Disable anytime:       set 'enabled: false' in replies.yaml")
    print("  4. Dry run:               python bot.py --dry-run")
    print("  5. Check logs:            tail -f logs/bot.log")
    print()


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
        print("❌ Login timed out. Please run setup.py again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
