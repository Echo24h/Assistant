"""Calendar tools with a fake Google service: no network, no Google account."""

from unittest.mock import MagicMock

import pytest

from assistant.google_calendar import Calendar, event_body
from assistant.store import Store
from assistant.tools import ToolBox, ToolError

GOOGLE_EVENT = {
    "id": "abc",
    "summary": "Dentist",
    "start": {"dateTime": "2026-11-12T14:00:00+01:00"},
    "end": {"dateTime": "2026-11-12T15:00:00+01:00"},
}


@pytest.fixture
def service():
    service = MagicMock()
    events = service.events.return_value
    events.insert.return_value.execute.return_value = GOOGLE_EVENT
    events.get.return_value.execute.return_value = GOOGLE_EVENT
    events.patch.return_value.execute.return_value = GOOGLE_EVENT
    events.list.return_value.execute.return_value = {"items": [GOOGLE_EVENT]}
    return service


def make_box(service, answer: bool):
    calendar = Calendar(service, "Europe/Zurich")
    return ToolBox(Store(":memory:"), confirm=lambda q: answer, calendar=calendar)


def test_event_body_times_and_no_guests():
    body = event_body("Run", "2026-11-12T07:00", "2026-11-12T08:00", None, None,
                      "Europe/Zurich")
    assert body["start"] == {"dateTime": "2026-11-12T07:00:00", "timeZone": "Europe/Zurich"}
    assert event_body(start="2026-11-12")["start"] == {"date": "2026-11-12"}
    assert "attendees" not in body


def test_create_needs_confirmation_and_sends_no_email(service):
    args = {"summary": "Dentist", "start": "2026-11-12T14:00", "end": "2026-11-12T15:00",
            "description": None, "location": None}
    events = service.events.return_value

    with pytest.raises(ToolError, match="declined"):
        make_box(service, answer=False).run("create_event", args)
    events.insert.assert_not_called()

    make_box(service, answer=True).run("create_event", args)
    kwargs = events.insert.call_args.kwargs
    assert kwargs["sendUpdates"] == "none"
    assert "attendees" not in kwargs["body"]


def test_list_events_needs_no_confirmation(service):
    box = make_box(service, answer=False)
    assert '"Dentist"' in box.run("list_events", {"start_date": "2026-11-12",
                                                  "end_date": "2026-11-12"})


def test_delete_sends_no_email(service):
    make_box(service, answer=True).run("delete_event", {"event_id": "abc"})
    assert service.events.return_value.delete.call_args.kwargs["sendUpdates"] == "none"


def test_calendar_tools_only_when_connected():
    box = ToolBox(Store(":memory:"), confirm=lambda q: True)
    names = {t["name"] for t in box.definitions}
    assert "list_events" not in names
    with pytest.raises(ToolError, match="Unknown tool"):
        box.run("list_events", {"start_date": "2026-11-12", "end_date": "2026-11-12"})


def test_end_before_start_is_refused_before_asking(service):
    """The pizza bug: 'until midnight' sent as 00:00 of the SAME day."""
    asked = []
    calendar = Calendar(service, "Europe/Zurich")
    box = ToolBox(Store(":memory:"), confirm=lambda q: asked.append(q) or True,
                  calendar=calendar)
    args = {"event_id": "abc", "summary": None, "start": None,
            "end": "2026-11-12T00:00", "description": None, "location": None}

    with pytest.raises(ToolError, match="NEXT day"):
        box.run("update_event", args)
    assert asked == []  # the user was not bothered
    service.events.return_value.patch.assert_not_called()

    box.run("update_event", {**args, "end": "2026-11-13T00:00"})  # next day: OK
    assert len(asked) == 1
