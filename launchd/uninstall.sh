#!/usr/bin/env bash
set -euo pipefail

PLIST_DEST="${HOME}/Library/LaunchAgents/com.user.linkedin-autoreply.plist"

if [ -f "${PLIST_DEST}" ]; then
    launchctl unload "${PLIST_DEST}" 2>/dev/null || true
    rm "${PLIST_DEST}"
    echo "✅ LaunchAgent unloaded and removed."
else
    echo "ℹ️  LaunchAgent not installed (plist not found)."
fi
