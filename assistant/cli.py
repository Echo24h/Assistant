"""Command-line interface: chat in the terminal, morning brief, Google login,
and the web interface for the phone (`python -m assistant web`)."""

import sys

import anthropic

from .agent import Agent
from .app import api_error_message, build_agent, connect_google, open_database
from .config import load_config


def confirm_in_terminal(question: str) -> bool:
    answer = input(f"  ⚠ {question} [y/N] ").strip().lower()
    return answer in {"y", "yes", "o", "oui"}


BRIEF_PROMPT = """Morning brief. In a few short lines:
1. today's calendar events;
2. unread emails from the last 24 hours that look important or need an \
answer (ignore newsletters and ads);
3. to-do tasks due today or overdue.
Do not change anything."""


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
    if args not in ([], ["brief"], ["web"]):
        sys.exit("Usage: python -m assistant [login | brief | web]")

    calendar, gmail = connect_google(cfg, interactive=False)

    if args == ["web"]:
        from .web.server import serve  # imported here: the CLI doesn't need it
        return serve(cfg, calendar, gmail)

    _, owner = open_database(cfg)  # the terminal acts as the owner
    agent = build_agent(cfg, confirm_in_terminal, owner, calendar, gmail)
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
    except anthropic.APIError as e:
        print(api_error_message(e))
        return not isinstance(e, anthropic.AuthenticationError)
    return True


if __name__ == "__main__":
    main()
