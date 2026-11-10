"""Web interface for the phone, with Python's standard library only.

Security model (see docs/PLAN.md):
- the server listens on 127.0.0.1 only: nothing is reachable from the
  network. `tailscale serve` forwards HTTPS requests from MY devices
  (tailnet) to it, and adds the header Tailscale-User-Login.
- a request is accepted only if that login is in ASSISTANT_WEB_USERS.
  No header = refused (except ASSISTANT_WEB_DEV_USER, for local tests).
- against CSRF (another website making my browser post here): only JSON
  bodies are accepted (forces a CORS preflight, which we never allow) and
  the Origin header, when present, must be this site.
- replies are inserted as text in the page, never as HTML (static/), and
  the Content-Security-Policy forbids any inline script.

How a confirmation works: the agent runs in a background thread. When a
tool needs confirmation, the thread puts the question in an "outbox"
queue and waits for the answer in an "answers" queue. The browser gets
the question as the response to its request, shows ✅ / ❌, and posts the
answer, which wakes the thread up.
"""

import json
import queue
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import anthropic

from ..app import api_error_message, build_agent
from ..services.store import Store
from .api import BadRequest, TasksAPI

STATIC_DIR = Path(__file__).parent / "static"
# The only files the server will ever send: URL path -> (file, content type).
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/chat.js": ("chat.js", "text/javascript; charset=utf-8"),
    "/tasks.js": ("tasks.js", "text/javascript; charset=utf-8"),
}
# No inline script or style is allowed: even injected HTML could not run code.
CSP = ("default-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
       "form-action 'self'; object-src 'none'")
MAX_BODY = 10_000  # bytes: a chat message, not a file upload
ANSWER_TIMEOUT = 300  # seconds to answer a confirmation, then it counts as "no"
TURN_TIMEOUT = 600  # seconds max for one agent turn


class Session:
    """One user's conversation with the agent, run in a background thread."""

    def __init__(self, make_agent):
        self.agent = make_agent(self.confirm)
        self.outbox = queue.Queue()  # events for the browser: question / reply / error
        self.answers = queue.Queue()  # the user's yes/no for a pending question
        self.busy = False
        self.waiting_answer = False

    # --- called from the agent's thread ---

    def confirm(self, question: str) -> bool:
        self.waiting_answer = True
        self.outbox.put({"type": "question", "text": question})
        try:
            return self.answers.get(timeout=ANSWER_TIMEOUT)
        except queue.Empty:
            return False  # no answer = no
        finally:
            self.waiting_answer = False

    def _run(self, text: str) -> None:
        try:
            event = {"type": "reply", "text": self.agent.ask(text)}
        except anthropic.APIError as e:
            event = {"type": "error", "text": api_error_message(e)}
        except Exception as e:  # never leave the browser waiting forever
            event = {"type": "error", "text": f"Unexpected error: {e}"}
        event["tokens"] = {"in": self.agent.input_tokens, "out": self.agent.output_tokens}
        self.busy = False
        self.outbox.put(event)

    # --- called from the web server's threads ---

    def ask(self, text: str) -> dict:
        if self.busy:
            return {"type": "error", "text": "Still working on the previous message."}
        self.busy = True
        threading.Thread(target=self._run, args=(text,), daemon=True).start()
        return self._next_event()

    def answer(self, yes: bool) -> dict:
        if not self.waiting_answer:
            return {"type": "error", "text": "No question is waiting for an answer."}
        self.answers.put(yes)
        return self._next_event()

    def _next_event(self) -> dict:
        try:
            return self.outbox.get(timeout=TURN_TIMEOUT)
        except queue.Empty:
            return {"type": "error", "text": "Timed out."}


class App:
    """Who may connect, and one Session per user."""

    def __init__(self, cfg, calendar, gmail):
        self.cfg = cfg
        self.calendar = calendar
        self.gmail = gmail
        self.sessions: dict[str, Session] = {}
        self.lock = threading.Lock()
        self.tasks = TasksAPI(Store(cfg.db_path))  # direct features, no model

    def user(self, headers) -> str | None:
        """The allowed user's login for this request, or None."""
        login = (headers.get("Tailscale-User-Login") or "").strip().lower()
        if login:
            return login if login in self.cfg.web_users else None
        return self.cfg.web_dev_user  # None unless testing locally

    def session(self, login: str, new: bool = False) -> Session:
        with self.lock:
            if new or login not in self.sessions:
                self.sessions[login] = Session(
                    lambda confirm: build_agent(self.cfg, confirm, self.calendar, self.gmail))
            return self.sessions[login]


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if not app.user(self.headers):
                return self.send_json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
            url = urlsplit(self.path)
            if url.path in STATIC:
                return self.send_static(*STATIC[url.path])
            query = {k: v[0] for k, v in parse_qs(url.query).items()}
            result = app.tasks.get(url.path, query)
            if result is None:
                return self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            self.send_json(result)

        def send_static(self, name: str, content_type: str) -> None:
            body = (STATIC_DIR / name).read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")  # always the latest version
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            login = app.user(self.headers)
            if not login:
                return self.send_json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
            if not self.same_origin():
                return self.send_json({"error": "bad origin"}, HTTPStatus.FORBIDDEN)
            data = self.read_json()
            if data is None:
                return self.send_json({"error": "expected a small JSON body"},
                                      HTTPStatus.BAD_REQUEST)

            if self.path == "/api/ask" and isinstance(data.get("text"), str):
                event = app.session(login).ask(data["text"].strip()[:4000])
            elif self.path == "/api/confirm" and isinstance(data.get("yes"), bool):
                event = app.session(login).answer(data["yes"])
            elif self.path == "/api/reset":
                app.session(login, new=True)
                event = {"type": "reset", "name": app.cfg.web_users.get(login, login)}
            else:  # direct features (web/api.py)
                try:
                    event = app.tasks.post(self.path, data)
                except BadRequest as e:
                    return self.send_json({"error": str(e)}, HTTPStatus.BAD_REQUEST)
                if event is None:
                    return self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            self.send_json(event)

        def same_origin(self) -> bool:
            origin = self.headers.get("Origin")
            if not origin:  # same-origin requests from some browsers have none
                return True
            # Behind `tailscale serve`, the public name may be in X-Forwarded-Host.
            ours = {self.headers.get("Host"), self.headers.get("X-Forwarded-Host")}
            return origin.split("://", 1)[-1] in ours

        def read_json(self) -> dict | None:
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return None
            length = int(self.headers.get("Content-Length") or 0)
            if not 0 < length <= MAX_BODY:
                return None
            try:
                data = json.loads(self.rfile.read(length))
            except ValueError:
                return None
            return data if isinstance(data, dict) else None

        def send_json(self, data: dict, status=HTTPStatus.OK) -> None:
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")  # personal data
            self.end_headers()
            self.wfile.write(body)

        def end_headers(self):
            """Security headers on every response."""
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            super().end_headers()

        def log_message(self, format, *args):  # keep the terminal quiet
            pass

    return Handler


def serve(cfg, calendar, gmail) -> None:
    if not cfg.web_users and not cfg.web_dev_user:
        raise SystemExit("Set ASSISTANT_WEB_USERS in .env (see .env.example).")
    server = ThreadingHTTPServer(("127.0.0.1", cfg.web_port), make_handler(App(cfg, calendar, gmail)))
    print(f"Web interface on http://127.0.0.1:{cfg.web_port} (local only).")
    print(f"For the phone: sudo tailscale serve --bg {cfg.web_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
