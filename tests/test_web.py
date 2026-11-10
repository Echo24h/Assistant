"""Web interface: who may connect, CSRF protection, confirmations.
A fake agent is used: no API key, no network except localhost."""

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from types import SimpleNamespace as NS

import pytest

from assistant import web
from assistant.config import parse_users
from assistant.web import App, Session, make_handler


class FakeAgent:
    """Asks for confirmation if the text contains 'delete', then replies."""

    def __init__(self, confirm):
        self.confirm = confirm
        self.input_tokens = self.output_tokens = 0

    def ask(self, text):
        if "delete" in text:
            return "Deleted." if self.confirm("Delete task «x»?") else "Kept."
        return f"echo: {text}"


def test_parse_users():
    assert parse_users(" Me@Gmail.com=Grégory, her@x.com=Anna ,bad") == {
        "me@gmail.com": "Grégory", "her@x.com": "Anna"}


def test_session_confirmation_round_trip():
    session = Session(FakeAgent)
    assert session.ask("hello")["text"] == "echo: hello"

    event = session.ask("delete x")
    assert event == {"type": "question", "text": "Delete task «x»?"}
    assert session.answer(False)["text"] == "Kept."

    assert session.answer(True)["type"] == "error"  # no question waiting


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setattr(web, "build_agent", lambda cfg, confirm, cal, gm: FakeAgent(confirm))
    cfg = NS(web_users={"me@gmail.com": "Grégory"}, web_dev_user=None)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(App(cfg, None, None)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def call(url, path, body=b'{"text": "hi"}', headers=None):
    headers = {"Content-Type": "application/json", **(headers or {})}
    request = urllib.request.Request(url + path, data=body, headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as e:
        return e.code, None


ME = {"Tailscale-User-Login": "me@gmail.com"}


def test_allowed_user_can_chat(server):
    assert call(server, "/api/ask", headers=ME) == (200, {"type": "reply", "text": "echo: hi",
                                                          "tokens": {"in": 0, "out": 0}})


def test_unknown_or_missing_login_is_refused(server):
    assert call(server, "/api/ask")[0] == 403  # no Tailscale header
    assert call(server, "/api/ask", headers={"Tailscale-User-Login": "x@evil.com"})[0] == 403
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen(server + "/")  # the page too


def test_csrf_is_blocked(server):
    # a form on another website can only send text/plain, never JSON without preflight
    assert call(server, "/api/ask", headers={**ME, "Content-Type": "text/plain"})[0] == 400
    assert call(server, "/api/ask", headers={**ME, "Origin": "https://evil.example"})[0] == 403
