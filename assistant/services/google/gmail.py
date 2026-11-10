"""Gmail, read-only, called directly through Google's Python client.

Email is written by strangers, so everything read here is UNTRUSTED:
- the scope is gmail.readonly: nothing here can send, delete or label mail;
- results are wrapped in a field named "untrusted_email" and truncated;
- tool outputs from Gmail are not written to the local log (tools.py),
  so email content is never stored (docs/PLAN.md, "Données").
"""

import base64
import re
from html import unescape

from googleapiclient.errors import HttpError

MAX_BODY_CHARS = 3000  # enough to understand an email, limits tokens


def header(message: dict, name: str) -> str | None:
    for h in message.get("payload", {}).get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return None


def decode(data: str) -> str:
    """Gmail sends bodies in base64url."""
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")


def html_to_text(html: str) -> str:
    """Rough HTML -> text: drop styles, scripts and tags, keep the words."""
    html = re.sub(r"(?is)<(style|script)\b.*?</\1>", " ", html)
    text = unescape(re.sub(r"<[^>]+>", " ", html))
    return re.sub(r"\s+", " ", text).strip()


def body_text(payload: dict) -> str:
    """Find the text of an email: text/plain first, else text/html, in all parts."""
    plain, html = [], []

    def walk(part: dict) -> None:
        data = part.get("body", {}).get("data")
        if data and part.get("mimeType") == "text/plain":
            plain.append(decode(data))
        elif data and part.get("mimeType") == "text/html":
            html.append(decode(data))
        for child in part.get("parts", []):
            walk(child)

    walk(payload)
    if plain:
        return "\n".join(plain).strip()
    return html_to_text(" ".join(html))


def summary(message: dict) -> dict:
    return {
        "id": message["id"],
        "from": header(message, "From"),
        "subject": header(message, "Subject"),
        "date": header(message, "Date"),
        "unread": "UNREAD" in message.get("labelIds", []),
        "snippet": unescape(message.get("snippet", "")),
    }


class Gmail:
    def __init__(self, service):
        self.messages = service.users().messages()  # the Gmail "messages" resource

    def search(self, query: str, max_results: int) -> dict:
        """Search like in the Gmail search box, e.g. "is:unread newer_than:1d"."""
        max_results = max(1, min(max_results, 20))
        found = self._call(self.messages.list(userId="me", q=query, maxResults=max_results))
        emails = []
        for ref in found.get("messages", []):
            message = self._call(self.messages.get(
                userId="me", id=ref["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]))
            emails.append(summary(message))
        return {"untrusted_email": emails}

    def read(self, message_id: str) -> dict:
        message = self._call(self.messages.get(userId="me", id=message_id, format="full"))
        email = summary(message)
        del email["snippet"]
        email["body"] = body_text(message.get("payload", {}))[:MAX_BODY_CHARS]
        return {"untrusted_email": email}

    @staticmethod
    def _call(request) -> dict:
        """Run a Google API request; turn HTTP errors into ValueError for the model."""
        try:
            return request.execute()
        except HttpError as e:
            raise ValueError(f"Gmail error {e.status_code}: {e.reason}") from e
