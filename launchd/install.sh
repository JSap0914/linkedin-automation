#!/usr/bin/env bash
set -euo pipefail

# Resolve project root (parent of the launchd/ directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PLIST_SRC="${SCRIPT_DIR}/com.user.linkedin-autoreply.plist"
PLIST_DEST="${HOME}/Library/LaunchAgents/com.user.linkedin-autoreply.plist"

# Verify we're in the right directory
if [ ! -f "${PROJECT_ROOT}/pyproject.toml" ]; then
    echo "❌ Error: pyproject.toml not found at ${PROJECT_ROOT}"
    exit 1
fi

# Ensure logs dir exists
mkdir -p "${PROJECT_ROOT}/logs"

# Replace {{PROJECT_ROOT}} placeholders
sed "s|{{PROJECT_ROOT}}|${PROJECT_ROOT}|g" "${PLIST_SRC}" > "${PLIST_DEST}"
echo "✅ Plist installed to ${PLIST_DEST}"

# Unload any previous version (idempotent)
launchctl unload "${PLIST_DEST}" 2>/dev/null || true

# Load the agent
launchctl load "${PLIST_DEST}"

# Verify
if launchctl list | grep -q "com.user.linkedin-autoreply"; then
    echo "✅ LaunchAgent loaded. Bot will run every 15 minutes."
    echo "   Check logs at: ${PROJECT_ROOT}/logs/bot.log"
else
    echo "⚠️  LaunchAgent may not be running. Check: launchctl list | grep linkedin"
fi
