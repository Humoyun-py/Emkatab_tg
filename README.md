# eMaktab Checker Bot

An authorized-user-only Telegram bot for recording eMaktab authentication-check
results. Credential checks are **off by default**. They run only when
`LOGIN_CHECK_ENABLED=true` is set (see [Use](#use)). The bot never retrieves
eMaktab data.

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
# Optional. Credential checks stay off unless this is true.
LOGIN_CHECK_ENABLED=false
LOGIN_URL=https://login.emaktab.uz/
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

**Enter results manually (no eMaktab contact):** tap **Natija kiritish**, then
send one line with the account type and three counts, in this order:

```text
student 3 1 0
```

That means 3 successful, 1 invalid credentials, 0 unknown. The bot saves one
batch of anonymous rows labeled `manual entry`. It never asks for credentials
in this mode. Use `/cancel` to stop. Each count must be a whole number from 0
to 1000, and the total must be at least 1.

When `LOGIN_CHECK_ENABLED` is off (the default), account selection only reports
that verification is unavailable, and the bot never asks for credentials.

When `LOGIN_CHECK_ENABLED=true`, the bot runs one login check per account
selection:

1. The user sends the eMaktab login.
2. The user sends the password.
3. The bot deletes each of those messages right away and makes one POST to
   `LOGIN_URL` with the credentials in the form body.
4. The bot saves one summary row (no login, no password) and replies with the
   outcome.

Use `/cancel` to stop an unfinished check. If Telegram refuses to delete a
credential message, the bot asks you to delete it yourself. Telegram chat
history can still hold the messages until they are removed.

Enable the check only for accounts you are authorized to check, under a
documented assignment from the school administration. Credentials are sent
only to `LOGIN_URL`. Credentials are never logged, and the bot never stores
them. The outcome mapping is: HTTP 401 or 403 means invalid credentials, and
anything else means unknown. HTTP 200 is not treated as success, because the
login form itself returns 200 without accepting the credentials.

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
