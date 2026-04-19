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


def test_install_sh_accepts_any_python_3_11_plus():
    text = (ROOT / "install.sh").read_text()
    for bin_name in ("python3.11", "python3.12", "python3.13", "python3"):
        assert bin_name in text, f"install.sh should consider {bin_name}"
    assert "sys.version_info >= (3, 11)" in text


def test_install_ps1_accepts_any_python_3_11_plus():
    text = (ROOT / "install.ps1").read_text()
    for ver in ("3.11", "3.12", "3.13"):
        assert f"'{ver}'" in text or f'"{ver}"' in text, f"install.ps1 should consider {ver}"
    assert "[version]'3.11'" in text


def test_install_ps1_has_resolve_python_helper():
    text = (ROOT / "install.ps1").read_text()
    assert "function Resolve-Python" in text
    assert "throw 'Python 3.11+ is required.'" in text


def test_readme_warns_about_powershell_activate_pitfall():
    text = (ROOT / "README.md").read_text()
    assert "CouldNotAutoLoadModule" in text
    assert ".\\.venv\\Scripts\\Activate.ps1" in text
