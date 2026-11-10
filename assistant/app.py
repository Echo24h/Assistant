"""Assemble the assistant: connect the services, build an agent.

Shared by the terminal (cli.py) and the web interface (web/server.py).
"""

import anthropic

from .agent import Agent
from .agent.tools import ToolBox
from .services.google.gmail import Gmail
from .services.google.auth import LoginRequired, get_credentials, google_service
from .services.google.calendar import Calendar
from .services.household import open_household, user_data
from .services.db import connect
from .services.users import User


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


def open_database(cfg):
    """Open (and upgrade) the database, sync the household; return (conn, owner)."""
    return open_household(cfg.db_path, cfg.people)


def build_agent(cfg, confirm, user: User, calendar, gmail) -> Agent:
    """One agent = one conversation of one person. Used by the terminal and the web.

    calendar and gmail: given for the owner only (they are the owner's accounts).
    """
    data = user_data(connect(cfg.db_path), user, cfg.currency)  # own connection: runs in its own thread
    return Agent(
        client=anthropic.Anthropic(),  # reads ANTHROPIC_API_KEY from the environment
        toolbox=ToolBox(data, confirm=confirm, calendar=calendar, gmail=gmail),
        model=cfg.model,
        effort=cfg.effort,
        log_path=cfg.log_path,
        language=cfg.language,
        user_name=user.name,
    )


def api_error_message(e: anthropic.APIError) -> str:
    """A short message for the user when the Claude API fails."""
    if isinstance(e, anthropic.AuthenticationError):
        return "Invalid or missing ANTHROPIC_API_KEY (see .env.example)."
    if isinstance(e, anthropic.RateLimitError):
        return "Rate limited, try again in a moment."
    if isinstance(e, anthropic.APIStatusError):
        return f"API error {e.status_code}: {e.message}"
    if isinstance(e, anthropic.APIConnectionError):
        return "Network error: cannot reach the API."
    return f"API error: {e}"
