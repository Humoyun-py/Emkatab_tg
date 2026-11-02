# eMaktab Checker Bot

An authorized-user-only Telegram bot scaffold for reporting authentication-check
results. **Authentication verification is currently unavailable**: no permitted
eMaktab authentication method has been confirmed. The bot does not request
eMaktab credentials, retrieve eMaktab data, or claim that a login succeeded.

## Requirements

- Ubuntu Linux
- Python 3.12
- A Telegram bot token from BotFather
- The Telegram numeric user ID(s) permitted to use the bot

## Installation

Install Python tooling and create a virtual environment:

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip
cd ~/Emaktab_tg
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If `python3.12` is not available from the configured Ubuntu repositories,
install Python 3.12 using an approved distribution or Python installation
method before continuing.

## Configuration

Create a local environment file from the example:

```bash
cp .env.example .env
nano .env
```

Set the following values in `.env`:

```dotenv
BOT_TOKEN=your_real_bot_token
AUTHORIZED_USER_IDS=your_telegram_numeric_user_id
DATABASE_URL=sqlite+aiosqlite:///./emaktab.db
```

For multiple authorized users, separate positive numeric Telegram IDs with
commas. Keep `.env` private and do not commit it or share its contents. The
`.gitignore` file excludes `.env`.

## Run

From the project directory, with the virtual environment active:

```bash
python bot.py
```

Or without activating it:

```bash
./.venv/bin/python bot.py
```

The bot creates the SQLite database and required tables on startup. Stop it
with `Ctrl+C`.

## Use

- Send `/start` to show the menu.
- Choose a student or parent account type to see the current verification
  availability.
- Use the **History** button or `/history` to view saved reports.
- Only Telegram IDs listed in `AUTHORIZED_USER_IDS` can use the bot.

Until an authentication method is confirmed as permitted, account selection
only reports that verification is unavailable. **Do not send eMaktab usernames
or passwords to the bot.** The bot does not delete Telegram messages containing
credentials and cannot guarantee their removal.

History contains only summaries that were actually recorded. It does not
display sample counts as real results or store passwords, authentication
cookies, or session tokens.

## Run tests

Tests use mock or in-memory data and do not connect to real eMaktab accounts:

```bash
./.venv/bin/pytest -q tests
```

## Troubleshooting

- **Missing `BOT_TOKEN` or `AUTHORIZED_USER_IDS`:** check `.env` exists in the
  project directory and contains non-placeholder values.
- **Unauthorized reply:** verify your Telegram numeric user ID is included in
  `AUTHORIZED_USER_IDS`, then restart the bot.
- **`Update ... is not handled`:** ensure the running process was restarted
  after code changes and that its startup output contains no configuration or
  import errors.
- **Bot does not start:** activate `.venv`, reinstall requirements, and review
  the terminal error without sharing `.env` contents.
# Emkatab_tg
