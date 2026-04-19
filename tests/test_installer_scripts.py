# pyright: reportMissingImports=false

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_install_sh_exists_and_wraps_cli_from_fixed_root():
    text = (ROOT / "install.sh").read_text()
    assert "LINKEDIN_AUTOREPLY_HOME" in text
    assert "~/.linkedin-automation" in text or ".linkedin-automation" in text
    assert 'cat > "$BIN_DIR/linkedin-autoreply"' in text
    assert '__INSTALL_DIR__/.venv/bin/linkedin-autoreply' in text
    assert 'replace("__INSTALL_DIR__", install_dir)' in text


def test_install_ps1_exists_and_creates_cmd_shim():
    text = (ROOT / "install.ps1").read_text()
    assert "LINKEDIN_AUTOREPLY_HOME" in text
    assert "linkedin-autoreply.cmd" in text
    assert 'cd /d "$InstallDir"' in text
    assert '.venv\\Scripts\\linkedin-autoreply.exe' in text
