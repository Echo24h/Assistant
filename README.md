# assistant

A personal AI agent that helps me manage my calendar, email, to-do list
written from scratch in Python on top of the Claude API.

Work in progress. The goal is a small, readable agent loop with tool use,
strict safety rules for untrusted content (email), and a measurable
evaluation.

## Design

- **Agent loop**: the model receives a goal, calls tools, reads the
  results and continues until the task is done. Written by hand, no agent
  framework, to keep every step visible.
- **Tools**: to-do list (local SQLite); Google Calendar
  through Google's API client, with the narrow `calendar.events` scope
  (repeating events, birthdays); Gmail read-only.
- **Model routing on a small budget**: the small model (Haiku) by default,
  with low effort; the larger one (Sonnet) only where the evaluation shows
  the small one is not good enough.

## Safety

An agent that reads email reads text written by strangers, so it must
not combine private data, untrusted content and a way to send data out
(the "lethal trifecta").

- Email access is read-only (`gmail.readonly`); the agent can never send
  email. Email content is marked untrusted and never written to the log.
- Calendar: the agent can read and edit events, but every change needs my
  confirmation, and events never get guests (a guest receives an email,
  which would be a way to send data out).
- Sensitive actions (creating an event, drafting a reply) require my
  confirmation, enforced in code, not in the prompt.
- Tools are an explicit allowlist; every tool call is logged locally.
- No secrets or personal data in this repository: keys live in `.env`,
  data lives outside the repo. Test emails are synthetic.

## Evaluation

A set of synthetic emails (meetings, invoices, spam, urgent requests and
prompt-injection attempts) measures:

- triage accuracy per category;
- correct extraction of dates and tasks;
- resistance to injection (no tool called because an email asked for it).

Results will be published here.

## Setup

Full step-by-step guide (Google console, Tailscale, server, update,
troubleshooting): [docs/INSTALL.md](docs/INSTALL.md). In short:

```bash
git clone git@github.com:Echo24h/Assistant.git && cd Assistant
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env && chmod 600 .env   # then fill in the keys below
```

All settings and secrets live in `.env` (never committed). Personal data
(SQLite database, Google token, tool-call log) lives in
`~/.local/share/assistant/`, readable only by you.

1. **Claude**: create an API key at console.anthropic.com and set
   `ANTHROPIC_API_KEY`.
2. **Google Calendar and Gmail** (optional; without them those tools are off):
   - in Google Cloud, create a project, enable the Google Calendar API
     and the Gmail API;
   - Google Auth Platform: audience *External*, status *Testing*, add
     yourself as a test user; data access: only `.../auth/calendar.events`
     and `.../auth/gmail.readonly`;
   - create an OAuth client of type *Desktop app* and copy its id and
     secret into `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`;
   - log in once (opens the browser, saves a token):
     `python -m assistant login`.

   In *Testing* mode Google expires the login after 7 days: run
   `python -m assistant login` again.

## Phone access (Tailscale)

`python -m assistant web` serves a small chat page on `127.0.0.1` only.
[Tailscale](https://tailscale.com) makes it reachable from my phone,
anywhere, without opening any port:

```bash
sudo tailscale serve --bg 8765   # HTTPS, visible only to my own devices
```

- Requests are accepted only from Tailscale logins listed in
  `ASSISTANT_WEB_USERS` (header `Tailscale-User-Login`).
- CSRF: JSON bodies only, and the `Origin` header is checked.
- Confirmations appear as ✅ / ❌ buttons; replies are inserted as text,
  never HTML, and the Content-Security-Policy forbids inline scripts, so
  email content cannot inject code into the page.
- Tabs: **Chat** (the agent, costs tokens), and **Tasks**, **Recipes**,
  **Shopping** (read and changed directly in the database: no model,
  0 tokens). Confirmations guard the model's decisions; a click is the
  user's own.
- Recipe import from a link reads the standard schema.org data of the
  page, without the model. The model has no internet tool. The download
  is protected against SSRF: http(s) and ports 80/443 only, public
  addresses only (checked at every redirect), and the connection goes to
  the address that was checked (no DNS rebinding).
- To run it on a server: `deploy/assistant-web.service`.

## Run it

```bash
python -m assistant          # chat in the terminal
python -m assistant brief    # morning brief: today's events, important email, tasks
python -m assistant web      # chat page for the phone (see above)
pytest                       # tests use fake clients: no API key, no Google account
```

Code map, in three layers:

```
assistant/
  services/   the core: data and Google access, no AI, no web
              db.py + migrations/   SQLite, numbered SQL files
              household.py          entry point: what one person can see
              users.py, tasks.py,   one module per domain
              recipes.py, shopping.py
              google/               code talking to the outside: auth.py,
              recipe_import.py      calendar.py, gmail.py; recipe downloads
  agent/      the AI: loop.py (the hand-written agent loop) and tools/
              (one module per domain; tools/__init__.py = allowlist + confirmation)
  web/        the platform: server.py (identity, CSRF) and static/ (phone page)
  app.py      assembles services + agent, shared by cli.py and web/
```

A pre-commit hook runs gitleaks with `.gitleaks.toml` to block committed
secrets (Anthropic keys, Google client secrets):

```bash
printf '#!/bin/sh\nexec gitleaks protect --staged --redact -c .gitleaks.toml\n' \
  > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

## Status

- [x] Agent loop, to-do tools (local)
- [x] Google Calendar: read, and edit with confirmation
- [x] Gmail read-only (content never logged), morning brief
- [x] Phone access: private web page through Tailscale
- [x] Tasks tab without the model (0 tokens), task priorities
- [x] Household database (migrations, users, shared or private tasks)
- [x] Recipes and shared shopping list (scaled, added up), import by link
- [ ] Evaluation on synthetic emails
- [ ] Email drafts with confirmation
