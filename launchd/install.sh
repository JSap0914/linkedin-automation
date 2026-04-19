#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

CLI="${PROJECT_ROOT}/.venv/bin/linkedin-autoreply"
if [ ! -x "${CLI}" ]; then
  echo "linkedin-autoreply CLI not found at ${CLI}" >&2
  echo "Run: pip install -e \".[dev]\"" >&2
  exit 1
fi

exec "${CLI}" start
