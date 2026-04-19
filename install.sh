#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/JSap0914/linkedin-automation.git"
INSTALL_DIR="${LINKEDIN_AUTOREPLY_HOME:-$HOME/.linkedin-automation}"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
SKIP_INIT=0

for arg in "$@"; do
  case "$arg" in
    --skip-init) SKIP_INIT=1 ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

pick_python() {
  if command -v python3.11 >/dev/null 2>&1; then
    echo "python3.11"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    python3 - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
    echo "python3"
    return
  fi
  if command -v python >/dev/null 2>&1; then
    python - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
    echo "python"
    return
  fi
  return 1
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_cmd git
PYTHON_BIN="$(pick_python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "Python 3.11+ is required." >&2
  exit 1
fi

if [ -d "$INSTALL_DIR/.git" ]; then
  if [ -n "$(git -C "$INSTALL_DIR" status --porcelain)" ]; then
    echo "Existing install at $INSTALL_DIR has uncommitted changes." >&2
    echo "Commit/stash them or remove the directory first." >&2
    exit 1
  fi
  git -C "$INSTALL_DIR" pull --ff-only origin main
elif [ -e "$INSTALL_DIR" ]; then
  echo "$INSTALL_DIR exists but is not a git checkout." >&2
  exit 1
else
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

"$PYTHON_BIN" -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/python" -m pip install -e "$INSTALL_DIR[dev]"
"$INSTALL_DIR/.venv/bin/scrapling" install

mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/linkedin-autoreply" <<'WRAP'
#!/usr/bin/env bash
set -euo pipefail
export LINKEDIN_AUTOREPLY_HOME="__INSTALL_DIR__"
cd "__INSTALL_DIR__"
exec "__INSTALL_DIR__/.venv/bin/linkedin-autoreply" "$@"
WRAP
"$PYTHON_BIN" - <<'PY' "$BIN_DIR/linkedin-autoreply" "$INSTALL_DIR"
from pathlib import Path
import sys

path = Path(sys.argv[1])
install_dir = sys.argv[2]
path.write_text(path.read_text().replace("__INSTALL_DIR__", install_dir))
PY
chmod +x "$BIN_DIR/linkedin-autoreply"

printf '%s\n' "$(git -C "$INSTALL_DIR" rev-parse HEAD)" > "$INSTALL_DIR/.installer_version"
date -u +%Y-%m-%dT%H:%M:%SZ > "$INSTALL_DIR/.installer_ts"

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *)
    echo
    echo "$BIN_DIR is not on your PATH. Add one of these lines:"
    echo "  export PATH=\"$BIN_DIR:\$PATH\""
    echo
    ;;
esac

if [ "$SKIP_INIT" -eq 1 ]; then
  echo "Install complete. Run '$BIN_DIR/linkedin-autoreply init' when ready."
  exit 0
fi

exec "$BIN_DIR/linkedin-autoreply" init
