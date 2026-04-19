# LinkedIn Auto-Reply Bot

Automatically replies to new comments on your LinkedIn posts with a random Korean thank-you message.

---

## ⚠️ ToS Disclaimer

LinkedIn's User Agreement prohibits automated access and interactions with the platform.
This tool operates in a **gray zone**: it acts only on **your own posts**, at **low volume**, from **your own device and IP** — minimizing risk but **NOT eliminating it**.

**By running this tool, you accept that LinkedIn may restrict, temporarily suspend, or permanently ban your account. USE AT YOUR OWN RISK.**

This is a real operational risk, not a theoretical one.
Read the ToS, understand the User Agreement, and accept the risk before continuing.

---

## Prerequisites

- macOS (tested on Apple Silicon + Intel)
- Python 3.11+
- Active LinkedIn account

---

## Quick Start

```bash
# 1. Set up the virtual environment
python3.11 -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -e ".[dev]"
scrapling install   # downloads Chromium browser binary

# 3. First-time setup (opens browser → log in → bootstraps seen comments)
python setup.py

# 4. Enable auto-polling every 15 minutes
bash launchd/install.sh
```

---

## Editing Reply Sentences

Edit `replies.yaml` — the bot picks up changes on the next run, no code change needed:

```yaml
sentences:
  - "댓글 감사합니다! 🙏"
  - "관심 가져주셔서 감사해요 😊"
  - "좋은 말씀 감사드립니다!"
```

---

## Kill Switch

To stop the bot without uninstalling, set `enabled: false` in `replies.yaml`:

```yaml
enabled: false
```

The next scheduled run will exit cleanly with no LinkedIn calls.

---

## Uninstall

```bash
bash launchd/uninstall.sh
```

---

## Troubleshooting

**"AuthExpiredError"** — your LinkedIn session expired (~1 year lifetime):
```bash
python setup.py   # re-login
```

**View logs**:
```bash
tail -f logs/bot.log
tail -f logs/launchd.err.log
```

**Test without posting (dry run)**:
```bash
python bot.py --dry-run
```

**Reset seen-comments history** (re-bootstrap):
```bash
rm seen_comments.db
python bot.py --bootstrap
```

---

## How It Works

The bot uses LinkedIn's internal Voyager API (`/voyager/api/feed/comments`) — the same API the LinkedIn web app uses. It authenticates with your browser session cookies (stored in `.profile/`) rather than username/password. Every 15 minutes (via macOS launchd), it fetches new comments on your posts from the last 30 days, filters out nested replies and your own comments, waits a random 30–120 seconds (to appear human-like), then posts a reply. Each replied comment is recorded in `seen_comments.db` (SQLite) to prevent duplicate replies.

See [Scrapling](https://github.com/D4Vinci/Scrapling) for the browser automation library used.

---

## License

MIT
