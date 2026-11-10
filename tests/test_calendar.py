"""Calendar tools with a fake Google service: no network, no Google account."""

from unittest.mock import MagicMock

import pytest

from assistant.services.google_calendar import Calendar, event_body, short_event
from helpers import memory_data
from assistant.agent.tools import ToolBox, ToolError

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
    return ToolBox(memory_data(), confirm=lambda q: answer, calendar=calendar)


def test_event_body_times_and_no_guests():
    body = event_body("Run", "2026-11-12T07:00", "2026-11-12T08:00", None, None,
                      "Europe/Zurich")
    assert body["start"] == {"dateTime": "2026-11-12T07:00:00", "timeZone": "Europe/Zurich"}
    assert event_body(start="2026-11-12")["start"] == {"date": "2026-11-12"}
    assert "attendees" not in body


def test_create_needs_confirmation_and_sends_no_email(service):
    args = {"summary": "Dentist", "start": "2026-11-12T14:00", "end": "2026-11-12T15:00",
            "description": None, "location": None, "repeat": "never"}
    events = service.events.return_value

    with pytest.raises(ToolError, match="declined"):
        make_box(service, answer=False).run("create_event", args)
    events.insert.assert_not_called()

    make_box(service, answer=True).run("create_event", args)
    kwargs = events.insert.call_args.kwargs
    assert kwargs["sendUpdates"] == "none"
    assert "attendees" not in kwargs["body"]
    assert "recurrence" not in kwargs["body"]  # once by default


def test_birthday_repeats_every_year(service):
    asked = []
    calendar = Calendar(service, "Europe/Zurich")
    box = ToolBox(memory_data(), confirm=lambda q: asked.append(q) or True,
                  calendar=calendar)
    box.run("create_event", {"summary": "Anniversaire Anna", "start": "2026-12-03",
                             "end": "2026-12-04", "description": None, "location": None,
                             "repeat": "yearly"})
    body = service.events.return_value.insert.call_args.kwargs["body"]
    assert body["recurrence"] == ["RRULE:FREQ=YEARLY"]
    assert body["start"] == {"date": "2026-12-03"}
    assert "repeats yearly" in asked[0]  # the user sees it before saying yes


def test_add_birthday_uses_google_birthday_type(service):
    asked = []
    calendar = Calendar(service, "Europe/Zurich")
    box = ToolBox(memory_data(), confirm=lambda q: asked.append(q) or True,
                  calendar=calendar)
    box.run("add_birthday", {"person": "Anna", "date": "2027-11-03"})
    kwargs = service.events.return_value.insert.call_args.kwargs
    body = kwargs["body"]
    assert body["eventType"] == "birthday"
    assert body["recurrence"] == ["RRULE:FREQ=YEARLY"]
    assert body["start"] == {"date": "2027-11-03"} and body["end"] == {"date": "2027-11-04"}
    assert kwargs["sendUpdates"] == "none" and "attendees" not in body
    assert "Anna" in asked[0]


def test_result_says_when_event_repeats():
    assert short_event({**GOOGLE_EVENT, "recurrence": ["RRULE:FREQ=YEARLY"]})["repeats"] == "yearly"
    assert "repeats" not in short_event(GOOGLE_EVENT)  # no extra tokens for one-off events


def test_holidays_follow_the_weekday_not_the_date(service):
    asked = []
    box = ToolBox(memory_data(), confirm=lambda q: asked.append(q) or True,
                  calendar=Calendar(service, "Europe/Zurich"))
    args = {"summary": "Fête des pères", "start": "2027-06-20", "end": "2027-06-21",
            "description": None, "location": None, "repeat": "yearly_nth_weekday"}
    box.run("create_event", args)
    body = service.events.return_value.insert.call_args.kwargs["body"]
    assert body["recurrence"] == ["RRULE:FREQ=YEARLY;BYMONTH=6;BYDAY=3SU"]
    assert asked[0] == ("Create «Fête des pères», Sun 20 Jun (all day), "
                        "every year on the 3rd Sunday of June?")

    box.run("create_event", {**args, "start": "2027-05-30", "end": "2027-05-31",
                             "repeat": "yearly_last_weekday"})
    body = service.events.return_value.insert.call_args.kwargs["body"]
    assert body["recurrence"] == ["RRULE:FREQ=YEARLY;BYMONTH=5;BYDAY=-1SU"]

    with pytest.raises(ToolError, match="not the last"):  # 23 May is not the last Sunday
        box.run("create_event", {**args, "start": "2027-05-23", "end": "2027-05-24",
                                 "repeat": "yearly_last_weekday"})
    assert len(asked) == 2  # refused before asking


def test_unknown_repeat_is_refused():
    with pytest.raises(ValueError, match="repeat"):
        event_body("x", repeat="RRULE:FREQ=SECONDLY")


def test_list_events_needs_no_confirmation(service):
    box = make_box(service, answer=False)
    assert '"Dentist"' in box.run("list_events", {"start_date": "2026-11-12",
                                                  "end_date": "2026-11-12"})


def test_delete_sends_no_email(service):
    make_box(service, answer=True).run("delete_event", {"event_id": "abc"})
    assert service.events.return_value.delete.call_args.kwargs["sendUpdates"] == "none"


def test_calendar_tools_only_when_connected():
    box = ToolBox(memory_data(), confirm=lambda q: True)
    names = {t["name"] for t in box.definitions}
    assert "list_events" not in names
    with pytest.raises(ToolError, match="Unknown tool"):
        box.run("list_events", {"start_date": "2026-11-12", "end_date": "2026-11-12"})


def test_end_before_start_is_refused_before_asking(service):
    """The pizza bug: 'until midnight' sent as 00:00 of the SAME day."""
    asked = []
    calendar = Calendar(service, "Europe/Zurich")
    box = ToolBox(memory_data(), confirm=lambda q: asked.append(q) or True,
                  calendar=calendar)
    args = {"event_id": "abc", "summary": None, "start": None,
            "end": "2026-11-12T00:00", "description": None, "location": None}

    with pytest.raises(ToolError, match="NEXT day"):
        box.run("update_event", args)
    assert asked == []  # the user was not bothered
    service.events.return_value.patch.assert_not_called()

    box.run("update_event", {**args, "end": "2026-11-13T00:00"})  # next day: OK
    assert len(asked) == 1
