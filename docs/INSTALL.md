# Install

Step by step, from a fresh machine to the assistant on your phone.
Steps 3 and 5 are optional: without Google, the calendar and email tools
are simply off; without Tailscale, use the terminal.

1. [Get the code](#1-get-the-code)
2. [Claude API key](#2-claude-api-key)
3. [Google Calendar and Gmail](#3-google-calendar-and-gmail-optional)
4. [First run](#4-first-run)
5. [Phone access with Tailscale](#5-phone-access-with-tailscale-optional)
6. [Keep it running (server)](#6-keep-it-running-on-a-server)
7. [Update](#7-update)
8. [Move to another machine](#8-move-to-another-machine)
9. [Troubleshooting](#9-troubleshooting)

## 1. Get the code

Needs Linux or macOS, Python 3.11+ and git.

```bash
git clone git@github.com:Echo24h/Assistant.git && cd Assistant
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env && chmod 600 .env
pytest   # fake clients: no key, no network, no cost
```

Where things live:

| What | Where | Committed? |
|---|---|---|
| Code | the repository | yes |
| Settings and secrets | `.env` (mode 600) | **never** |
| Data: tasks (SQLite), Google token, tool-call log | `~/.local/share/assistant/` (mode 700) | **never** |

Optional but recommended, a pre-commit hook that blocks secrets
([gitleaks](https://github.com/gitleaks/gitleaks) must be installed):

```bash
printf '#!/bin/sh\nexec gitleaks protect --staged --redact -c .gitleaks.toml\n' \
  > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

## 2. Claude API key

1. Create an account at [console.anthropic.com](https://console.anthropic.com)
   and buy a few dollars of credits (5 $ last a long time with Haiku).
2. *API keys* → *Create key*, then put it in `.env`:
   `ANTHROPIC_API_KEY=sk-ant-...`
3. Recommended: set a monthly spend limit in the console.

The other settings in `.env.example` have sensible defaults:

| Setting | Default | Meaning |
|---|---|---|
| `ASSISTANT_MODEL` | `claude-haiku-5-5` | model of the agent |
| `ASSISTANT_EFFORT` | `low` | thinking effort (cost) |
| `ASSISTANT_TIMEZONE` | `Europe/Zurich` | for "tomorrow", event times |
| `ASSISTANT_LANGUAGE` | `French` | language of the answers |
| `ASSISTANT_DATA_DIR` | `~/.local/share/assistant` | personal data |

## 3. Google Calendar and Gmail (optional)

One Google OAuth client serves both services. In
[console.cloud.google.com](https://console.cloud.google.com):

1. Create a project (e.g. "Assistant").
2. *APIs & Services* → *Library*: enable **Google Calendar API** and
   **Gmail API**.
3. *Google Auth Platform*:
   - *Branding*: app name and your email;
   - *Audience*: **External**, status **Testing**, and add your own
     Google account as a **test user** (*Internal* is only for Workspace
     organizations);
   - *Data access*: add only these two scopes:
     - `https://www.googleapis.com/auth/calendar.events`
       (events only: it cannot share your calendar);
     - `https://www.googleapis.com/auth/gmail.readonly` (never send).
4. *Clients* → *Create client* → type **Desktop app**. Copy the client id
   and secret into `.env`:

   ```
   GOOGLE_CLIENT_ID=....apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=GOCSPX-...
   ```

   Do not keep the downloaded JSON file in the repository.
5. Log in once. It opens the browser; Google warns that the app is not
   verified (it is yours): *Continue*.

   ```bash
   python -m assistant login
   ```

   The token is saved to `~/.local/share/assistant/token.json` (mode 600).

In *Testing* mode, Google expires the login **after 7 days**: run
`python -m assistant login` again. To avoid it, set the app to
*In production* in *Audience* (still only usable by you; Google only
reviews apps that ask for sensitive scopes for other users).

## 4. First run

```bash
python -m assistant          # chat in the terminal (quit: empty line or Ctrl+D)
python -m assistant brief    # morning brief: events, important email, tasks
```

Every change to the calendar, and every deletion, asks for confirmation
(`y` / `n`). Token use is printed at the end.

## 5. Phone access with Tailscale (optional)

The web page listens on `127.0.0.1` only. [Tailscale](https://tailscale.com)
makes it reachable from your own devices, anywhere, with HTTPS and without
opening a port.

1. Install Tailscale on the computer and log in:

   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```

2. Install the Tailscale app on the phone and log in with the **same
   account**. `tailscale status` should list both devices.
3. In the [admin console](https://login.tailscale.com/admin/dns), enable
   **MagicDNS** and **HTTPS certificates**. Leave **Funnel off**: Funnel
   would publish the page on the internet.
4. Allow your Tailscale login in `.env` (`login=name`, comma-separated):

   ```
   ASSISTANT_WEB_USERS=you@gmail.com=YourName
   ```

5. Start the page and publish it on the tailnet:

   ```bash
   python -m assistant web          # keep this terminal open
   sudo tailscale serve --bg 8765   # once; it is remembered
   ```

6. On the phone, open the `https://<machine>.<tailnet>.ts.net/` address
   printed by `tailscale serve`, then *Share* → *Add to Home Screen*.

Check that only the tailnet sees it: `tailscale serve status` must say
*tailnet only*, never *Funnel on*.

For a local test without Tailscale, set `ASSISTANT_WEB_DEV_USER` to an
allowed login and open http://127.0.0.1:8765. Never set it on a server.

## 6. Keep it running on a server

On a VPS or a Raspberry Pi, a systemd user service restarts the page
automatically (the repository must be in `~/Assistant`):

```bash
mkdir -p ~/.config/systemd/user
cp deploy/assistant-web.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now assistant-web
loginctl enable-linger $USER     # keep running after logout
sudo tailscale serve --bg 8765
```

Logs: `journalctl --user -u assistant-web -f`.

## 7. Update

```bash
git pull
pip install -e '.[dev]'    # if dependencies changed
pytest
systemctl --user restart assistant-web   # or restart `python -m assistant web`
```

Then reload the page on the phone. The database upgrades itself on start
(e.g. new columns), without losing data.

## 8. Move to another machine

1. On the new machine: steps 1 and 5 (Tailscale), without filling `.env`.
2. Copy the secrets and the data, over Tailscale:

   ```bash
   scp .env new-machine:Assistant/.env
   rsync -a ~/.local/share/assistant/ new-machine:.local/share/assistant/
   ```

3. Step 6 on the new machine, then stop the old one.

The phone address contains the machine name: name the new machine the same
in Tailscale, or open the new address.

## 9. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `(Google off: run python -m assistant login first)` | token expired (7 days in Testing) or a new scope is needed: `python -m assistant login` |
| Page answers **403** | your Tailscale login is not in `ASSISTANT_WEB_USERS`, or you opened `127.0.0.1` without `ASSISTANT_WEB_DEV_USER` |
| Phone cannot connect | Tailscale off on the phone, or `python -m assistant web` not running |
| `Invalid or missing ANTHROPIC_API_KEY` | key missing or wrong in `.env` |
| `API error 400 ... credit balance` | no credits left in the Anthropic console |
| Page looks old after an update | reload without cache (Ctrl+Shift+R; on iPhone close and reopen the tab) |
