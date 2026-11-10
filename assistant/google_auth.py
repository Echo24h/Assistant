"""Log in to Google once (OAuth) and reuse the saved token.

One token for every Google service the agent uses. Scopes are the minimum
(see docs/PLAN.md):
- calendar.events: read and edit events. NOT `calendar`, which could also
  share the whole calendar with someone else.
- gmail.readonly: read email. Never send (no gmail.send, no gmail.modify).
"""

import json
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.readonly",
]


class LoginRequired(Exception):
    """No valid Google token: the user must run `python -m assistant login`."""


def client_config(client_id: str, client_secret: str) -> dict:
    """The content of Google's "Desktop app" JSON file, built from .env values."""
    return {"installed": {
        "client_id": client_id,
        "client_secret": client_secret,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }}


def load_token(token_path: Path) -> Credentials | None:
    """The saved token, or None if missing or if it lacks a scope we need
    (e.g. an old token made before Gmail was added)."""
    if not token_path.exists():
        return None
    granted = set(json.loads(token_path.read_text()).get("scopes") or [])
    if not set(SCOPES) <= granted:
        return None
    return Credentials.from_authorized_user_file(str(token_path), SCOPES)


def get_credentials(client_id: str, client_secret: str, token_path: Path,
                    interactive: bool) -> Credentials:
    """Return valid Google credentials.

    interactive=True (the `login` command): open the browser if needed.
    interactive=False (normal use): never open the browser, raise LoginRequired.
    The token is saved in token_path (chmod 600) and refreshed automatically.
    """
    creds = load_token(token_path)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:  # e.g. revoked, or the 7-day limit in test mode
            creds = None

    if not creds or not creds.valid:
        if not interactive:
            raise LoginRequired()
        flow = InstalledAppFlow.from_client_config(client_config(client_id, client_secret), SCOPES)
        creds = flow.run_local_server(port=0)  # opens the browser

    token_path.write_text(creds.to_json())
    token_path.chmod(0o600)
    return creds


def google_service(name: str, version: str, creds: Credentials):
    """e.g. google_service("calendar", "v3", creds)."""
    return build(name, version, credentials=creds, cache_discovery=False)
