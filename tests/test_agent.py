"""Test the agent loop with a fake client: no network, no API key."""

from types import SimpleNamespace as NS

from assistant.agent import Agent
from helpers import memory_data
from assistant.agent.tools import ToolBox


def text(t):
    return NS(type="text", text=t)


def tool_use(id, name, input):
    return NS(type="tool_use", id=id, name=name, input=input)


def reply(stop_reason, *content):
    return NS(stop_reason=stop_reason, content=list(content),
              usage=NS(input_tokens=10, output_tokens=5))


class FakeClient:
    """Returns pre-written responses in order and records each request."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.messages = self  # so that client.messages.create(...) works

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.responses.pop(0)


def make_agent(client, tmp_path, confirm=lambda q: True):
    data = memory_data()
    agent = Agent(client, ToolBox(data, confirm), "test-model", "medium",
                  tmp_path / "log.jsonl")
    return agent, data


def test_tool_call_then_answer(tmp_path):
    client = FakeClient([
        reply("tool_use", tool_use("t1", "add_task", {"title": "Buy milk", "due_date": None, "priority": "normal", "private": False})),
        reply("end_turn", text("Added.")),
    ])
    agent, data = make_agent(client, tmp_path)

    assert agent.ask("add buy milk") == "Added."
    assert data.tasks.list(False)[0]["title"] == "Buy milk"
    # second request carries the tool result, linked by id
    result = agent.messages[2]["content"][0]  # user, assistant, tool results
    assert result["tool_use_id"] == "t1" and result["is_error"] is False
    assert (tmp_path / "log.jsonl").read_text().count("\n") == 1


def test_errors_are_sent_back_to_the_model(tmp_path):
    client = FakeClient([
        reply("tool_use", tool_use("t1", "send_email", {"to": "x@example.com"})),
        reply("end_turn", text("I can't send emails.")),
    ])
    agent, _ = make_agent(client, tmp_path)

    agent.ask("email this")
    result = agent.messages[2]["content"][0]  # user, assistant, tool results
    assert result["is_error"] is True and "Unknown tool" in result["content"]


def test_loop_stops_after_max_steps(tmp_path):
    looping = reply("tool_use", tool_use("t", "list_tasks", {"include_done": False}))
    client = FakeClient([looping] * 50)
    agent, _ = make_agent(client, tmp_path)

    assert "Stopped" in agent.ask("loop")
    assert len(client.requests) == 10


def test_refusal_rolls_back_the_turn(tmp_path):
    client = FakeClient([reply("refusal")])
    agent, _ = make_agent(client, tmp_path)

    assert "declined" in agent.ask("something")
    assert agent.messages == []
