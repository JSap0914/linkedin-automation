#!/usr/bin/env python3
import argparse
import importlib.util
from collections.abc import Callable
from pathlib import Path


"""LinkedIn Auto-Reply Bot — entry point invoked by launchd."""


def _load_run() -> Callable[..., None]:
    orchestrator_path = Path(__file__).with_name("bot") / "orchestrator.py"
    spec = importlib.util.spec_from_file_location("linkedin_autoreply_orchestrator", orchestrator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load orchestrator from {orchestrator_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LinkedIn Auto-Reply Bot — replies to new comments on your posts"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be replied without posting anything",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Mark all existing comments as seen (run before first real run)",
    )
    args = parser.parse_args()

    run = _load_run()
    run(dry_run=args.dry_run, bootstrap=args.bootstrap)


if __name__ == "__main__":
    main()
