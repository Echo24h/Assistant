"""Web interface: who may connect, CSRF protection, confirmations.
A fake agent is used: no API key, no network except localhost."""

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from types import SimpleNamespace as NS

import pytest

from assistant.web import server as web
from assistant.config import parse_users
from assistant.web.server import App, Session, make_handler


class FakeAgent:
    """Asks for confirmation if the text contains 'delete', then replies."""

    def __init__(self, confirm):
        self.confirm = confirm
        self.input_tokens = self.output_tokens = 0
        self.closed = False

    def close(self):
        self.closed = True

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

    session.close()
    assert session.agent.closed  # its database connection is released


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setattr(web, "build_agent",
                        lambda cfg, confirm, user, cal, gm: FakeAgent(confirm))
    users = {"me@gmail.com": "Grégory"}
    cfg = NS(web_users=users, people=users, web_dev_user=None, db_path=":memory:",
             currency="CHF")
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
                                                          "tokens": {"in": 0, "out": 0,
                                                                     "total_in": 0,
                                                                     "total_out": 0}})


def test_unknown_or_missing_login_is_refused(server):
    assert call(server, "/api/ask")[0] == 403  # no Tailscale header
    assert call(server, "/api/ask", headers={"Tailscale-User-Login": "x@evil.com"})[0] == 403
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen(server + "/")  # the page too


def test_csrf_is_blocked(server):
    # a form on another website can only send text/plain, never JSON without preflight
    assert call(server, "/api/ask", headers={**ME, "Content-Type": "text/plain"})[0] == 400
    assert call(server, "/api/ask", headers={**ME, "Origin": "https://evil.example"})[0] == 403


def get(url, path, headers=ME):
    request = urllib.request.Request(url + path, headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, None


def test_tasks_tab_without_model(server):
    """Add, list, complete, reopen and delete a task: no agent involved."""
    def post(path, data):
        return call(server, path, body=json.dumps(data).encode(), headers=ME)

    status, task = post("/api/tasks/add", {"title": "Pay rent", "due_date": "2026-12-01"})
    assert status == 200 and task["title"] == "Pay rent"
    tasks = lambda q="": json.loads(get(server, "/api/tasks" + q)[2])["tasks"]
    assert [t["title"] for t in tasks()] == ["Pay rent"]

    assert post("/api/tasks/done", {"id": task["id"], "done": True}) == (200, {"ok": True})
    assert tasks() == [] and len(tasks("?all=1")) == 1
    assert post("/api/tasks/done", {"id": task["id"], "done": False}) == (200, {"ok": True})
    assert task["priority"] == "normal"  # default from the page
    assert post("/api/tasks/priority", {"id": task["id"], "priority": "high"}) == (200, {"ok": True})
    assert tasks()[0]["priority"] == "high"
    assert post("/api/tasks/delete", {"id": task["id"]}) == (200, {"ok": True})
    assert tasks("?all=1") == []


def test_tasks_tab_rejects_bad_input(server):
    def status(path, data):
        return call(server, path, body=json.dumps(data).encode(), headers=ME)[0]

    assert status("/api/tasks/add", {"title": ""}) == 400
    assert status("/api/tasks/add", {"title": "x", "due_date": "tomorrow"}) == 400
    assert status("/api/tasks/done", {"id": True, "done": True}) == 400  # bool is not an id
    assert status("/api/tasks/delete", {"id": "1"}) == 400
    assert status("/api/tasks/add", {"title": "x", "priority": "urgent!!"}) == 400
    assert status("/api/tasks/priority", {"id": 1}) == 400  # priority missing


def test_tasks_need_identity(server):
    assert get(server, "/api/tasks", headers={})[0] == 403


def test_static_files_and_security_headers(server):
    status, headers, body = get(server, "/")
    assert status == 200 and b"/tasks.js" in body
    assert "'unsafe-inline'" not in headers["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert get(server, "/tasks.js")[0] == 200
    assert get(server, "/../.env")[0] == 404  # only listed files are ever sent
    assert get(server, "/server.py")[0] == 404


def test_only_the_owner_gets_google(monkeypatch):
    given = {}
    monkeypatch.setattr(web, "build_agent", lambda cfg, confirm, user, cal, gm:
                        given.update({user.name: (cal, gm)}) or FakeAgent(confirm))
    users = {"me@gmail.com": "Grégory", "her@gmail.com": "Anna"}
    cfg = NS(web_users=users, people=users, web_dev_user=None, db_path=":memory:",
             currency="CHF")
    app = App(cfg, calendar="my calendar", gmail="my gmail")

    for login in users:
        app.session(app.user({"Tailscale-User-Login": login}))
    assert given == {"Grégory": ("my calendar", "my gmail"), "Anna": (None, None)}


def test_recipes_and_shopping_tabs(server):
    def post(path, data):
        return call(server, path, body=json.dumps(data).encode(), headers=ME)

    status, recipe = post("/api/recipes/add", {
        "title": "Pâtes", "servings": 2, "ingredients": "500 g de pâtes\n\n4 tomates\nsel",
        "instructions": "Cuire."})
    assert status == 200 and len(recipe["ingredients"]) == 3  # the empty line is skipped
    listed = json.loads(get(server, "/api/recipes")[2])["recipes"]
    assert listed == [{"id": recipe["id"], "title": "Pâtes", "servings": 2}]
    assert json.loads(get(server, f"/api/recipes/get?id={recipe['id']}")[2])["title"] == "Pâtes"
    assert get(server, "/api/recipes/get?id=abc")[0] == 400

    assert post("/api/recipes/shop", {"id": recipe["id"], "servings": 4}) == (200, {"added": 3})
    status, milk = post("/api/shopping/add", {"text": "2 l de lait"})
    assert milk["quantity"] == 2000 and milk["unit"] == "ml"
    items = json.loads(get(server, "/api/shopping")[2])["items"]
    assert {i["name"]: i["quantity"] for i in items}["pâtes"] == 1000

    assert post("/api/shopping/check", {"id": milk["id"], "checked": True})[0] == 200
    assert post("/api/shopping/clear", {}) == (200, {"removed": 1})
    assert post("/api/recipes/add", {"title": "x", "servings": 2, "ingredients": ""})[0] == 400
    assert post("/api/recipes/import", {"url": "http://127.0.0.1/"})[0] == 400  # SSRF


def test_finances_tab(server):
    def post(path, data):
        return call(server, path, body=json.dumps(data).encode(), headers=ME)

    status, _ = post("/api/finances/add", {"amount": "45,50", "description": "Courses",
                                           "category": "courses", "split": "equal"})
    assert status == 200
    page = json.loads(get(server, "/api/finances")[2])
    assert page["expenses"][0]["amount"] == "45.50 CHF"
    assert page["settle"] == []  # alone in this test household: nobody owes
    assert page["by_category"] == {"courses": "45.50 CHF"}

    assert post("/api/finances/add", {"amount": "-1", "description": "x", "category": "courses",
                                      "split": "equal"})[0] == 400
    assert post("/api/finances/add", {"amount": 12, "description": "x", "category": "courses",
                                      "split": "equal"})[0] == 400  # typed text expected
    assert post("/api/finances/delete", {"id": page["expenses"][0]["id"]}) == (200, {"ok": True})
