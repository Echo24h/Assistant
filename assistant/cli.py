"""Command-line interface: a simple chat loop in the terminal."""

import sys

import anthropic

from .agent import Agent
from .config import load_config
from .gmail import Gmail
from .google_auth import LoginRequired, get_credentials, google_service
from .google_calendar import Calendar
from .store import Store
from .tools import ToolBox


def confirm_in_terminal(question: str) -> bool:
    answer = input(f"  ⚠ {question} [y/N] ").strip().lower()
    return answer in {"y", "yes", "o", "oui"}


BRIEF_PROMPT = """Morning brief. In a few short lines:
1. today's calendar events;
2. unread emails from the last 24 hours that look important or need an \
answer (ignore newsletters and ads);
3. to-do tasks due today or overdue.
Do not change anything."""


def connect_google(cfg, interactive: bool):
    """Return (calendar, gmail), or (None, None) if Google is not set up."""
    if not cfg.google_enabled:
        print("(Google off: set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env)")
        return None, None
    try:
        creds = get_credentials(cfg.google_client_id, cfg.google_client_secret,
                                cfg.google_token_path, interactive)
    except LoginRequired:
        print("(Google off: run `python -m assistant login` first)")
        return None, None
    calendar = Calendar(google_service("calendar", "v3", creds), cfg.timezone)
    gmail = Gmail(google_service("gmail", "v1", creds))
    return calendar, gmail


def login(cfg) -> None:
    """Log in to Google in the browser once; the token is saved for later runs."""
    calendar, _ = connect_google(cfg, interactive=True)
    if calendar:
        print(f"Google connected. Token saved in {cfg.google_token_path}")


def main() -> None:
    cfg = load_config()
    args = sys.argv[1:]
    if args == ["login"]:
        return login(cfg)
    if args not in ([], ["brief"]):
        sys.exit("Usage: python -m assistant [login | brief]")

    store = Store(cfg.db_path)
    calendar, gmail = connect_google(cfg, interactive=False)

    agent = Agent(
        client=anthropic.Anthropic(),  # reads ANTHROPIC_API_KEY from the environment
        toolbox=ToolBox(store, confirm=confirm_in_terminal, calendar=calendar, gmail=gmail),
        model=cfg.model,
        effort=cfg.effort,
        log_path=cfg.log_path,
        language=cfg.language,
    )
    if args == ["brief"]:  # one question, then exit (later: run by cron)
        ask_and_print(agent, BRIEF_PROMPT)
    else:
        chat(agent, cfg.model)
    print(f"\nTokens used: {agent.input_tokens} in, {agent.output_tokens} out")


def chat(agent: Agent, model: str) -> None:
    print(f"assistant ({model}) — empty line or Ctrl-D to quit")
    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text or not ask_and_print(agent, text):
            break


def ask_and_print(agent: Agent, text: str) -> bool:
    """Ask the agent and print the answer. Return False if we should stop."""
    try:
        print(agent.ask(text))
    except anthropic.AuthenticationError:
        print("Invalid or missing ANTHROPIC_API_KEY (see .env.example).")
        return False
    except anthropic.RateLimitError:
        print("Rate limited, try again in a moment.")
    except anthropic.APIStatusError as e:
        print(f"API error {e.status_code}: {e.message}")
    except anthropic.APIConnectionError:
        print("Network error: cannot reach the API.")
    return True


if __name__ == "__main__":
    main()
