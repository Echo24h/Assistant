"""Settings read from the environment (and from .env, which is never committed)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    model: str  # main agent
    fast_model: str  # simple repeated tasks (email triage, later)
    effort: str  # how hard the model thinks: low / medium / high
    timezone: str  # IANA name, e.g. Europe/Zurich
    language: str  # language of the answers, e.g. French
    data_dir: Path  # real data lives here, outside the repository
    google_client_id: str | None  # OAuth client from Google Cloud (Desktop app)
    google_client_secret: str | None
    web_port: int  # the web interface listens on 127.0.0.1:web_port only
    web_users: dict[str, str]  # Tailscale login -> display name
    web_dev_user: str | None  # local testing without Tailscale (never on a server)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "assistant.db"

    @property
    def log_path(self) -> Path:
        return self.data_dir / "tool_calls.jsonl"

    @property
    def google_token_path(self) -> Path:  # created by `python -m assistant login`
        return self.data_dir / "token.json"

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)


def load_config() -> Config:
    load_dotenv()  # reads .env in the current directory, if present
    data_dir = Path(os.getenv("ASSISTANT_DATA_DIR", "~/.local/share/assistant")).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)
    data_dir.chmod(0o700)  # personal data and tokens: only this user can read them
    return Config(
        model=os.getenv("ASSISTANT_MODEL", "claude-haiku-5-5"),
        fast_model=os.getenv("ASSISTANT_FAST_MODEL", "claude-haiku-5-5"),
        effort=os.getenv("ASSISTANT_EFFORT", "low"),
        timezone=os.getenv("ASSISTANT_TIMEZONE", "Europe/Zurich"),
        language=os.getenv("ASSISTANT_LANGUAGE", "English"),
        data_dir=data_dir,
        google_client_id=os.getenv("GOOGLE_CLIENT_ID") or None,
        google_client_secret=os.getenv("GOOGLE_CLIENT_SECRET") or None,
        web_port=int(os.getenv("ASSISTANT_WEB_PORT", "8765")),
        web_users=parse_users(os.getenv("ASSISTANT_WEB_USERS", "")),
        web_dev_user=os.getenv("ASSISTANT_WEB_DEV_USER") or None,
    )


def parse_users(value: str) -> dict[str, str]:
    """"me@gmail.com=Grégory, her@gmail.com=Anna" -> {login: name}."""
    users = {}
    for item in value.split(","):
        if "=" in item:
            login, name = item.split("=", 1)
            users[login.strip().lower()] = name.strip()
    return users
