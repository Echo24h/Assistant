"""Command-line interface: a simple chat loop in the terminal."""

import sys

import anthropic

from .agent import Agent
from .config import load_config
from .google_calendar import Calendar, LoginRequired
from .store import Store
from .tools import ToolBox


def confirm_in_terminal(question: str) -> bool:
    answer = input(f"  ⚠ {question} [y/N] ").strip().lower()
    return answer in {"y", "yes", "o", "oui"}


def connect_calendar(cfg, interactive: bool) -> Calendar | None:
    if not cfg.google_enabled:
        print("(Google Calendar off: set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env)")
        return None
    try:
        return Calendar.connect(cfg.google_client_id, cfg.google_client_secret,
                                cfg.google_token_path, cfg.timezone, interactive)
    except LoginRequired:
        print("(Google Calendar off: run `python -m assistant login` first)")
        return None


def login(cfg) -> None:
    """Log in to Google in the browser once; the token is saved for later runs."""
    if connect_calendar(cfg, interactive=True):
        print(f"Google Calendar connected. Token saved in {cfg.google_token_path}")


def main() -> None:
    cfg = load_config()
    args = sys.argv[1:]
    if args == ["login"]:
        return login(cfg)
    if args:
        sys.exit("Usage: python -m assistant [login]")

    store = Store(cfg.db_path)
    calendar = connect_calendar(cfg, interactive=False)

    agent = Agent(
        client=anthropic.Anthropic(),  # reads ANTHROPIC_API_KEY from the environment
        toolbox=ToolBox(store, confirm=confirm_in_terminal, calendar=calendar),
        model=cfg.model,
        effort=cfg.effort,
        log_path=cfg.log_path,
    )
    print(f"assistant ({cfg.model}) — empty line or Ctrl-D to quit")

    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            break
        try:
            print(agent.ask(text))
        except anthropic.AuthenticationError:
            print("Invalid or missing ANTHROPIC_API_KEY (see .env.example).")
            break
        except anthropic.RateLimitError:
            print("Rate limited, try again in a moment.")
        except anthropic.APIStatusError as e:
            print(f"API error {e.status_code}: {e.message}")
        except anthropic.APIConnectionError:
            print("Network error: cannot reach the API.")

    print(f"\nTokens used: {agent.input_tokens} in, {agent.output_tokens} out")


if __name__ == "__main__":
    main()
