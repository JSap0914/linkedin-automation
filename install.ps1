param(
  [switch]$SkipInit
)

$ErrorActionPreference = 'Stop'
$RepoUrl = 'https://github.com/JSap0914/linkedin-automation.git'
$InstallDir = if ($env:LINKEDIN_AUTOREPLY_HOME) { $env:LINKEDIN_AUTOREPLY_HOME } else { Join-Path $HOME '.linkedin-automation' }
$WindowsAppsDir = Join-Path $HOME 'AppData\Local\Microsoft\WindowsApps'
$FallbackBinDir = Join-Path $HOME '.local\bin'
$BinDir = if (Test-Path $WindowsAppsDir) { $WindowsAppsDir } else { $FallbackBinDir }

function Require-Command([string]$Name) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Missing required command: $Name"
  }
}

Require-Command git

function Test-PythonBinary {
  param([string[]]$Command)

  try {
    $output = & $Command[0] $Command[1..($Command.Length - 1)] `
      -c "import sys; sys.stdout.write(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
  } catch {
    return $null
  }

  if ($LASTEXITCODE -ne 0) { return $null }
  if (-not $output) { return $null }

  try {
    if ([version]$output -ge [version]'3.11') { return $Command }
  } catch {
    return $null
  }
  return $null
}

function Is-StoreStub {
  param([string]$CommandName)

  $info = Get-Command $CommandName -ErrorAction SilentlyContinue
  if (-not $info) { return $false }
  return ($info.Source -and $info.Source -like '*\WindowsApps\*')
}

function Resolve-Python {
  foreach ($cmd in @('python', 'python3', 'python3.14', 'python3.13', 'python3.12', 'python3.11')) {
    if (Is-StoreStub $cmd) { continue }
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { continue }
    $result = Test-PythonBinary @($cmd)
    if ($result) { return $result }
  }

  if (Get-Command py -ErrorAction SilentlyContinue) {
    foreach ($ver in @('3.14', '3.13', '3.12', '3.11')) {
      $result = Test-PythonBinary @('py', "-$ver")
      if ($result) { return $result }
    }
    $result = Test-PythonBinary @('py', '-3')
    if ($result) { return $result }
  }

  throw @'
Python 3.11+ is required but could not be resolved automatically.

Tried: python, python3, python3.14, python3.13, python3.12, python3.11, py -3.14/-3.13/-3.12/-3.11/-3
Microsoft Store "python" stubs (WindowsApps\*) are intentionally skipped.

Fix: install Python 3.11+ from https://www.python.org/downloads/ with
"Add python.exe to PATH" and "Install py launcher" both checked.
Then re-run this installer.
'@
}

$PythonCmd = Resolve-Python

if (Test-Path (Join-Path $InstallDir '.git')) {
  $Dirty = (& git -C $InstallDir status --porcelain)
  if ($Dirty) {
    throw "Existing install at $InstallDir has uncommitted changes. Commit/stash them or remove the directory first."
  }
  & git -C $InstallDir pull --ff-only origin main
} elseif (Test-Path $InstallDir) {
  throw "$InstallDir exists but is not a git checkout."
} else {
  & git clone $RepoUrl $InstallDir
}

if ($PythonCmd.Length -gt 1) {
  & $PythonCmd[0] $PythonCmd[1] -m venv (Join-Path $InstallDir '.venv')
} else {
  & $PythonCmd[0] -m venv (Join-Path $InstallDir '.venv')
}
$VenvPython = Join-Path $InstallDir '.venv\Scripts\python.exe'
$ScraplingExe = Join-Path $InstallDir '.venv\Scripts\scrapling.exe'
$CliExe = Join-Path $InstallDir '.venv\Scripts\linkedin-autoreply.exe'

& $VenvPython -m pip install -e "$InstallDir[dev]"
& $ScraplingExe install

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$CmdShim = Join-Path $BinDir 'linkedin-autoreply.cmd'
@"
@echo off
setlocal
set "LINKEDIN_AUTOREPLY_HOME=$InstallDir"
cd /d "$InstallDir"
call "$CliExe" %*
"@ | Set-Content -Encoding ASCII $CmdShim

& git -C $InstallDir rev-parse HEAD | Set-Content (Join-Path $InstallDir '.installer_version')
(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') | Set-Content (Join-Path $InstallDir '.installer_ts')

if (-not ($env:PATH -split ';' | Where-Object { $_ -eq $BinDir })) {
  Write-Host "`n$BinDir is not on PATH. Add it to your user PATH if needed.`n"
}

if ($SkipInit) {
  Write-Host "Install complete. Run '$CmdShim init' when ready."
  exit 0
}

& $CmdShim init
