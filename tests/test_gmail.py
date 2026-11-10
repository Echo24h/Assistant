"""Gmail tools with a fake Google service: no network, no Google account."""

import base64
import json
from types import SimpleNamespace as NS
from unittest.mock import MagicMock

import pytest

from assistant.agent import Agent
from assistant.services.gmail import Gmail, body_text
from assistant.services.store import Store
from assistant.agent.tools import ToolBox, ToolError


def b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


EMAIL = {
    "id": "m1",
    "labelIds": ["UNREAD", "INBOX"],
    "snippet": "Your invoice &amp; receipt",
    "payload": {
        "headers": [{"name": "From", "value": "Shop <shop@example.com>"},
                    {"name": "Subject", "value": "Invoice"}],
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/html", "body": {"data": b64("<p>Hello <b>HTML</b></p>")}},
            {"mimeType": "text/plain", "body": {"data": b64("Hello plain text")}},
        ],
    },
}


@pytest.fixture
def service():
    service = MagicMock()
    messages = service.users.return_value.messages.return_value
    messages.list.return_value.execute.return_value = {"messages": [{"id": "m1"}]}
    messages.get.return_value.execute.return_value = EMAIL
    return service


def test_body_prefers_plain_text_and_strips_html():
    assert body_text(EMAIL["payload"]) == "Hello plain text"
    html_only = {"mimeType": "text/html",
                 "body": {"data": b64("<style>p{}</style><p>Hi &amp; bye</p>")}}
    assert body_text(html_only) == "Hi & bye"


def test_results_are_marked_untrusted(service):
    gmail = Gmail(service)
    found = gmail.search("is:unread", 5)["untrusted_email"]
    assert found[0]["subject"] == "Invoice" and found[0]["unread"] is True
    assert gmail.read("m1")["untrusted_email"]["body"] == "Hello plain text"


def test_no_tool_can_send_email(service):
    box = ToolBox(Store(":memory:"), confirm=lambda q: True, gmail=Gmail(service))
    names = {t["name"] for t in box.definitions}
    assert names >= {"search_emails", "read_email"}
    assert not any("send" in n or "draft" in n for n in names)
    with pytest.raises(ToolError, match="Unknown tool"):
        box.run("send_email", {"to": "attacker@example.com"})


def test_email_content_is_not_logged(service, tmp_path):
    responses = [
        NS(stop_reason="tool_use", usage=NS(input_tokens=1, output_tokens=1),
           content=[NS(type="tool_use", id="t1", name="read_email",
                       input={"email_id": "m1"})]),
        NS(stop_reason="end_turn", usage=NS(input_tokens=1, output_tokens=1),
           content=[NS(type="text", text="An invoice.")]),
    ]
    client = NS(messages=NS(create=lambda **kw: responses.pop(0)))
    box = ToolBox(Store(":memory:"), confirm=lambda q: True, gmail=Gmail(service))
    agent = Agent(client, box, "test-model", "low", tmp_path / "log.jsonl")

    agent.ask("what is my last email?")
    entry = json.loads((tmp_path / "log.jsonl").read_text())
    assert entry["tool"] == "read_email" and entry["output"] == "(not logged)"
    assert "plain text" not in (tmp_path / "log.jsonl").read_text()
