"""The 🐞 button: report a bug from any tab (services/bugs.py)."""

import base64

from ..version import code_version
from .api import BadRequest, SharedDB, field


class BugsAPI:
    def __init__(self, db: SharedDB):
        self.db = db

    def get(self, user, path: str, query: dict) -> dict | None:
        return None  # the owner reads them in the terminal: python -m assistant bugs

    def post(self, user, path: str, data: dict) -> dict | None:
        if path != "/api/bugs/report":
            return None
        with self.db.data_for(user) as mine:
            return mine.bugs.report(
                field(data, "description", str),
                field(data, "place", str),
                field(data, "details", str, optional=True),
                version=code_version(),
                image=image_of(field(data, "image", str, optional=True)),
            )


def image_of(data_url: str | None) -> bytes | None:
    """"data:image/jpeg;base64,/9j/..." (what the page sends) -> the image bytes.
    Its real type is checked by services/bugs.py, from its first bytes."""
    if not data_url:
        return None
    header, _, encoded = data_url.partition(",")
    if not (header.startswith("data:image/") and header.endswith(";base64")):
        raise BadRequest("image: a data:image/...;base64 URL")
    try:
        return base64.b64decode(encoded, validate=True)
    except ValueError:  # binascii.Error is a ValueError
        raise BadRequest("image: invalid base64") from None
