# LinkedIn Auto-Reply Bot

Cross-platform CLI that auto-replies to new comments on **your own** LinkedIn posts and, optionally, sends a follow-up DM to the commenter. Ships as a `linkedin-autoreply` command with a guided `init` wizard.

---

## ⚠ ToS Disclaimer

LinkedIn's User Agreement prohibits automated access and interactions with the platform. This tool operates in a **gray zone** — it acts only on **your own posts**, at **low volume**, from **your own device and IP**. Risk is not zero.

**By running this tool you accept that LinkedIn may restrict, suspend, or permanently ban your account. Use at your own risk.**

---

## Platform Support

| Platform | Status |
|---|---|
| macOS (Apple Silicon + Intel) | ✅ Developed & live-tested |
| Windows 10/11 | ⚠️ **Code ready, live validation pending** — unit tests pass via subprocess mocks, but no end-to-end run on a real Windows host yet. Please [open an issue](https://github.com/JSap0914/linkedin-automation/issues) if something breaks. |
| Linux | ⚠️ CLI + bot work, but **no scheduler integration** (launchd is macOS-only, Task Scheduler is Windows-only). You need to run `linkedin-autoreply run` from cron/systemd yourself. |

---

## Requirements

- Python 3.11 or newer
- Active LinkedIn account (you'll log in once, session cookies are stored locally)
- ~500 MB free disk space (Chromium browser for `scrapling` + virtualenv)

---

## One-Line Install

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/JSap0914/linkedin-automation/main/install.sh | bash
```

### Windows (PowerShell)

```powershell
iex (iwr -useb https://raw.githubusercontent.com/JSap0914/linkedin-automation/main/install.ps1).Content
```

What the installer does:
- clones to `~/.linkedin-automation`
- creates `.venv`
- runs `pip install -e ".[dev]"`
- runs `scrapling install`
- creates a global wrapper command (`linkedin-autoreply`) that always runs from the install root
- immediately launches `linkedin-autoreply init`

If the install directory already exists as a clean git checkout, the installer fast-forwards it. If it has uncommitted changes, it aborts rather than overwriting them.

---

## Manual Install

### macOS / Linux

```bash
git clone https://github.com/JSap0914/linkedin-automation.git
cd linkedin-automation
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
scrapling install
linkedin-autoreply init
```

### Windows (PowerShell)

```powershell
git clone https://github.com/JSap0914/linkedin-automation.git
cd linkedin-automation
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
scrapling install
linkedin-autoreply init
```

---

## What the `init` Wizard Does

Each step is skippable (answer "no") except ToS + login. Defaults in brackets.

1. **ToS acknowledgement** — accept the automation risk (no default, must type `y`)
2. **Prerequisite check** — Python version + `scrapling` importable
3. **LinkedIn login** — opens a Chromium window; log in manually (you have 5 minutes); session cookies are cached in `.profile/`
4. **Reply config**
   - Enable auto-reply? `[Y/n]`
   - Use the default 3 Korean thank-you templates? `[Y/n]` — answer `n` to enter your own 3
   - Reply delay seconds (0 = instant) `[0]`
   - Polling interval seconds (must be ≥ 60) `[60]`
5. **DM config** (optional — skip if you only want replies)
   - Enable auto-DM? `[y/N]`
   - Only DM 1st-degree connections? `[Y/n]` (recommended yes)
   - Auto-accept pending invitations from commenters? `[Y/n]`
   - Use default 3 Korean DM templates? `[Y/n]`
   - Max DMs per day `[30]`
   - DM delay seconds `[0]`
6. **Write config** → `replies.yaml` (validated against pydantic schema before write)
7. **Bootstrap existing comments?** `[Y/n]` — marks all current comments on your posts as "seen" so the bot won't reply to old ones
8. **Install scheduler?** `[Y/n]` — registers a launchd agent (macOS) or Task Scheduler task (Windows) that runs the bot every 60 seconds
9. **Star on GitHub?** `[Y/n]` — if `gh` CLI is installed and authenticated, stars the repo in-place via `gh api --silent --method PUT /user/starred/<repo>`. Otherwise opens the repo in your browser so you can star manually. Skipped automatically in non-TTY/CI. Pattern inspired by [oh-my-openagent](https://github.com/code-yeongyu/oh-my-openagent).
10. **Done** — prints next-step commands

### What gets created on disk

| Path | What it is | Safe to delete? |
|---|---|---|
| `replies.yaml` | Your configuration | No (regenerate via `config reset`) |
| `.profile/` | Chromium profile + cookies (~100 MB) | No (you'll need to re-login) |
| `.cache/own_urn` | Cached LinkedIn person URN | Yes (auto-regenerated) |
| `seen_comments.db` | SQLite log of replied comments | Yes (but you may re-reply to old comments) |
| `logs/bot.log` | Rotating bot log | Yes |
| `~/Library/LaunchAgents/com.user.linkedin-autoreply.plist` (macOS) | Scheduler entry | Yes (run `uninstall` instead) |
| Task Scheduler `LinkedInAutoReply` (Windows) | Scheduler entry | Yes (run `uninstall` instead) |

---

## All Commands

```
linkedin-autoreply init              # full setup wizard
linkedin-autoreply run [--dry-run] [--bootstrap]
linkedin-autoreply setup             # re-login only (no config changes)
linkedin-autoreply update [--dry-run] [--skip-tests]

linkedin-autoreply config show
linkedin-autoreply config set <dotted.path> <value>
linkedin-autoreply config edit       # opens in $EDITOR
linkedin-autoreply config wizard     # re-run config section only
linkedin-autoreply config reset      # overwrite with defaults
linkedin-autoreply config migrate    # fill missing fields after schema change

linkedin-autoreply start             # install + enable scheduler
linkedin-autoreply stop              # disable (keep entry)
linkedin-autoreply uninstall         # remove scheduler entry
linkedin-autoreply status            # scheduler state + recent logs
linkedin-autoreply logs [-n N]       # tail bot.log
```

### Config paths you'll actually change

```bash
linkedin-autoreply config set dm.enabled true
linkedin-autoreply config set dm.max_per_day 50
linkedin-autoreply config set enabled false              # kill switch
linkedin-autoreply config set reply_delay_seconds_min 30
linkedin-autoreply config set reply_delay_seconds_max 120
linkedin-autoreply config set polling_min_interval_seconds 300  # 5 min
```

---

## Verifying Your Install Works

Run these in order after `init`:

```bash
# 1. Config is valid
linkedin-autoreply config show

# 2. Scheduler is registered
linkedin-autoreply status
# → should show "Installed: yes" + "Enabled: yes"

# 3. Bot can actually call LinkedIn (no write, safe)
linkedin-autoreply run --dry-run
# → logs should show "Fetched N comments" and "Dry run complete"

# 4. Check logs
linkedin-autoreply logs -n 20

# 5. (macOS) verify launchd picked it up
launchctl list | grep linkedin-autoreply
# → should print one line

# 6. (Windows PowerShell) verify Task Scheduler
schtasks /Query /TN LinkedInAutoReply
```

---

## Updating to the Latest Version

```bash
linkedin-autoreply update
```

If you installed via `install.sh` / `install.ps1`, this works from **any current working directory** because the global wrapper command always `cd`s into the install root before invoking the CLI.

This:
1. Aborts if your working tree is dirty (run `git status` to see)
2. `git pull --ff-only origin main` (refuses non-fast-forward)
3. Re-runs `pip install -e ".[dev]"` if `pyproject.toml` changed
4. Runs `config migrate` if `bot/config.py` or `bot/config_defaults.py` changed (fills new fields with defaults, drops removed fields — your values are preserved)
5. Reinstalls the scheduler if `bot/scheduler/templates/` changed
6. Runs the pytest smoke suite (`--skip-tests` to skip)

Flags:
- `--dry-run` — inspect only, no pull/install/migrate
- `--skip-tests` — don't run pytest after update

---

## Kill Switch

Stops the bot without uninstalling:

```bash
linkedin-autoreply config set enabled false
```

The next scheduled run exits cleanly with no LinkedIn API calls. Re-enable with `... set enabled true`.

---

## Full Uninstall

```bash
linkedin-autoreply uninstall   # removes scheduler entry
deactivate                     # exit venv
rm -rf .venv .profile .cache seen_comments.db logs replies.yaml
cd ..
rm -rf linkedin-automation     # manual-install path
```

If you used the one-line installer, remove the installer-managed directory instead:

```bash
linkedin-autoreply uninstall
rm -rf ~/.linkedin-automation
rm -f ~/.local/bin/linkedin-autoreply
```

Windows (PowerShell):

```powershell
linkedin-autoreply uninstall
Remove-Item -Recurse -Force $HOME\.linkedin-automation
Remove-Item -Force "$HOME\AppData\Local\Microsoft\WindowsApps\linkedin-autoreply.cmd" -ErrorAction SilentlyContinue
```

---

## Migration from Pre-CLI Workflow

| Before | After |
|---|---|
| `python setup.py` | `linkedin-autoreply setup` (setup.py is gone) |
| `bash launchd/install.sh` | `linkedin-autoreply start` (bash script is a shim) |
| `bash launchd/uninstall.sh` | `linkedin-autoreply uninstall` (shim) |
| edit `replies.yaml` by hand | `linkedin-autoreply config set …` or `config edit` |
| manual re-bootstrap | `linkedin-autoreply config reset` then `run --bootstrap` |

`python bot.py [--dry-run] [--bootstrap]` still works as a compatibility shim.

---

## Troubleshooting

### `scrapling install` fails / browser not found
```bash
scrapling install --force   # re-download Chromium
```
If behind a corporate proxy, set `HTTPS_PROXY` first.

### `AuthExpiredError` in logs
Session cookie expired (LinkedIn rotates them every ~1 year, or sooner if you log in elsewhere):
```bash
linkedin-autoreply setup
```

### Login step hangs
Browser window didn't open? Check that you have a display server. Over SSH you need `-X` forwarding or a local terminal.

### "Another instance holds logs/bot.lock"
A previous run crashed. Safe to delete:
```bash
rm logs/bot.lock logs/bot.lock.lock 2>/dev/null
```

### Bot replies to comments from weeks ago
You skipped bootstrap. Run:
```bash
linkedin-autoreply run --bootstrap
```
This marks every current comment as "seen" without replying.

### `linkedin-autoreply: command not found`
Your virtualenv isn't activated, or `pip install -e .` failed:
```bash
source .venv/bin/activate   # macOS/Linux
.venv\Scripts\Activate.ps1  # Windows
pip install -e ".[dev]"
```

### Tests fail with `ModuleNotFoundError: filelock`
```bash
pip install -e ".[dev]"  # reinstall deps
```

### launchd (macOS) won't start
```bash
launchctl list | grep linkedin-autoreply
# If present but "Status: 78" or similar error code:
launchctl unload ~/Library/LaunchAgents/com.user.linkedin-autoreply.plist
linkedin-autoreply start  # reinstalls
```

### Windows Task Scheduler blocks the task
`schtasks /Create` requires the user to have "Log on as a batch job" right. Some corporate Windows images disable this. Workaround: run `linkedin-autoreply run` manually from an elevated PowerShell, or skip the `start` step and invoke `run` via your own scheduler.

---

## How It Works

Uses LinkedIn's internal Voyager API (`/voyager/api/voyagerSocialDashNormComments` for replies, `/voyager/api/voyagerMessagingDashMessengerMessages` for DMs) — the same API the web app calls. Authenticates via browser session cookies stored in `.profile/` (not username/password).

Every 60 seconds the OS scheduler runs one poll cycle:
1. Load session cookies from `.profile/`
2. Fetch your posts from the last N days (default 30)
3. For each post, fetch comments
4. Filter out: your own comments, nested replies, already-seen comments (tracked in `seen_comments.db`)
5. For each new comment:
   - Pick a reply template (per-post binding > keyword match > random default)
   - Personalize with `{name}님` (Korean honorific) using the commenter's first name
   - Wait `reply_delay_seconds` (0 = instant)
   - POST the reply
   - If `dm.enabled` + commenter passes `only_first_degree_connections` check: auto-accept any pending invitation from them, wait for connection, then send a DM
   - Record success in `seen_comments.db`

All pre-existing comments at the time of `linkedin-autoreply init` (bootstrap step) or `run --bootstrap` are marked seen without reply. New comments landing after that moment are what the bot responds to.

See [Scrapling](https://github.com/D4Vinci/Scrapling) for the underlying Patchright-based browser automation.

---

## Known Limitations

- **Single LinkedIn account per install** — multi-account would need separate clones
- **No retry on Voyager 429** — the bot logs + exits; next scheduled run picks up where it left off
- **No rich text replies** — plain text only (LinkedIn supports mentions but this bot doesn't emit them)
- **Korean-first templates** — defaults are in Korean (`{name}님 ...`); override via wizard or `config set`
- **Windows live validation pending** — see Platform Support above

---

## Project Layout

```
bot/
├── cli.py                    # Typer CLI entry point
├── cli_commands/             # One file per subcommand
├── onboarding/               # init wizard steps
├── scheduler/                # launchd / Task Scheduler abstraction
│   └── templates/
├── config.py                 # pydantic schema
├── config_defaults.py        # single source of truth for defaults
├── config_io.py              # YAML read/write + dotted-path setter
├── config_migrate.py         # schema drift detection + safe merge
├── updater.py                # git pull + pip install + drift detection
├── orchestrator.py           # main poll cycle
├── auth.py                   # browser login + cookie extraction
├── voyager.py                # Voyager API client (scrapling)
├── comments.py, posts.py, replies.py   # endpoint wrappers
├── messaging.py, connections.py, invitations.py  # DM + connection logic
├── templates.py, personalization.py    # template matching + {name} substitution
├── db.py                     # SQLite seen_comments / dm_sent
├── lockfile.py               # cross-platform singleton lock (filelock)
├── killswitch.py
└── logging_config.py

tests/                        # 255 unit tests (pytest)
launchd/                      # macOS launchd shim scripts (legacy path)
pyproject.toml                # deps, entry points, pyright config
```

---

## Contributing / Issues

Found a bug, especially on Windows? [Open an issue](https://github.com/JSap0914/linkedin-automation/issues). Include:
- OS + Python version
- Output of `linkedin-autoreply status`
- Last 50 lines of `logs/bot.log`
- What you ran + what you expected

---

## License

MIT
