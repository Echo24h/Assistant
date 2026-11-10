"""Google Calendar access, called directly through Google's Python client.

Safety rules (see docs/PLAN.md):
- scope `calendar.events` (see auth.py);
- events never get guests, and every call sends `sendUpdates="none"`:
  a guest receives an email, which would be a way to send data out.
- create / update / delete are confirmed by the user (see tools.py).
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from googleapiclient.errors import HttpError

CALENDAR_ID = "primary"  # the user's main calendar
NO_EMAILS = "none"  # value of sendUpdates: Google never emails anyone

# The model picks one of these words; the code writes the Google rule itself
# (RFC 5545 RRULE), so the model never sends a raw rule.
REPEAT_RULES = {
    "daily": "RRULE:FREQ=DAILY",
    "weekly": "RRULE:FREQ=WEEKLY",
    "monthly": "RRULE:FREQ=MONTHLY",
    "yearly": "RRULE:FREQ=YEARLY",  # birthdays, anniversaries
}
# Holidays like "3rd Sunday of June" or "last Sunday of May": the rule is
# computed from the start date (see weekday_rule).
WEEKDAY_REPEATS = ("yearly_nth_weekday", "yearly_last_weekday")
DAY_CODES = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


def weekday_rule(start: str, repeat: str) -> str:
    """"2027-06-20" (3rd Sunday of June) -> "RRULE:FREQ=YEARLY;BYMONTH=6;BYDAY=3SU"."""
    day = date.fromisoformat(start[:10])
    if repeat == "yearly_last_weekday":
        if (day + timedelta(days=7)).month == day.month:
            raise ValueError(f"{day} is not the last {day:%A} of its month.")
        position = -1
    else:
        position = (day.day - 1) // 7 + 1  # 1st, 2nd, 3rd... of the month
    return f"RRULE:FREQ=YEARLY;BYMONTH={day.month};BYDAY={position}{DAY_CODES[day.weekday()]}"


def to_google_time(value: str, tz: str) -> dict:
    """"2026-11-12" -> all-day event; "2026-11-12T14:30" -> timed event."""
    if len(value) == 10:
        return {"date": date.fromisoformat(value).isoformat()}
    return {"dateTime": datetime.fromisoformat(value).isoformat(), "timeZone": tz}


def event_body(summary=None, start=None, end=None, description=None,
               location=None, tz="UTC", repeat=None) -> dict:
    """Build the JSON sent to Google. There is deliberately no 'attendees'."""
    body = {}
    if repeat in WEEKDAY_REPEATS:
        body["recurrence"] = [weekday_rule(start, repeat)]
    elif repeat not in (None, "never"):
        if repeat not in REPEAT_RULES:
            raise ValueError(f"Unknown repeat value: {repeat}.")
        body["recurrence"] = [REPEAT_RULES[repeat]]
    if summary is not None:
        body["summary"] = summary
    if start is not None:
        body["start"] = to_google_time(start, tz)
    if end is not None:
        body["end"] = to_google_time(end, tz)
    if description is not None:
        body["description"] = description
    if location is not None:
        body["location"] = location
    return body


def short_event(event: dict) -> dict:
    """Keep only what the model needs (less text = fewer tokens)."""
    short = {
        "id": event["id"],
        "summary": event.get("summary", "(no title)"),
        "start": event["start"].get("dateTime", event["start"].get("date")),
        "end": event["end"].get("dateTime", event["end"].get("date")),
        "location": event.get("location"),
        # Event text can be written by strangers (invitations): keep it short.
        "description": (event.get("description") or "")[:200] or None,
        "has_guests": bool(event.get("attendees")),
        # One occurrence of a repeating event: its id changes only this date,
        # the series_id changes every occurrence.
        "series_id": event.get("recurringEventId"),
    }
    # Only on a repeating event (as Google returns it after creating it):
    # the model can then confirm "every year" instead of guessing.
    rules = event.get("recurrence") or []
    words = [word for word, rule in REPEAT_RULES.items() if rule in rules]
    if words:
        short["repeats"] = words[0]
    elif rules:
        short["repeats"] = rules[0].removeprefix("RRULE:")  # e.g. "FREQ=YEARLY;BYDAY=3SU"
    return short


class Calendar:
    def __init__(self, service, tz: str):
        self.events = service.events()  # the Google API "events" resource
        self.tz = tz

    def list_events(self, start_date: str, end_date: str) -> list[dict]:
        """Events from start_date 00:00 to end_date 24:00 (local time)."""
        zone = ZoneInfo(self.tz)
        time_min = datetime.combine(date.fromisoformat(start_date), datetime.min.time(), zone)
        time_max = datetime.combine(date.fromisoformat(end_date) + timedelta(days=1),
                                    datetime.min.time(), zone)
        result = self._call(self.events.list(
            calendarId=CALENDAR_ID,
            timeMin=time_min.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,  # expand recurring events
            orderBy="startTime",
            maxResults=50,
        ))
        return [short_event(e) for e in result.get("items", [])]

    def check_times(self, start: str | None, end: str | None, event_id: str | None = None):
        """Raise ValueError if the event would end before it starts.

        Called BEFORE asking the user to confirm, so that an obviously wrong
        change goes back to the model instead of bothering the user.
        For an update, a missing start or end is taken from the current event.
        """
        if event_id and (start is None or end is None):
            current = self.get_event(event_id)
            start = start or current["start"]
            end = end or current["end"]
        if start is None or end is None:
            return
        first, last = self._local(start), self._local(end)
        if type(first) is type(last) and last <= first:
            raise ValueError(f"End ({end}) is not after start ({start}). "
                             "Midnight at the end of a day is 00:00 of the NEXT day.")

    def pretty(self, value: str) -> str:
        """"2026-11-13T19:00:00+01:00" -> "Fri 13 Nov 19:00" (for humans, no tokens)."""
        moment = self._local(value)
        if isinstance(moment, datetime):
            return moment.strftime("%a %d %b %H:%M")
        return moment.strftime("%a %d %b") + " (all day)"

    def pretty_range(self, start: str, end: str) -> str:
        """"Fri 13 Nov 19:00 → 22:00", or the full end date if it's another day."""
        if len(start) == 10 and len(end) == 10:
            # All-day events: Google's end is the day AFTER the last day.
            last_day = date.fromisoformat(end) - timedelta(days=1)
            if last_day <= date.fromisoformat(start):  # a single day
                return self.pretty(start)
            return f"{self.pretty(start)[:10]} → {last_day:%a %d %b} (all day)"
        first, last = self.pretty(start), self.pretty(end)
        if first[:10] == last[:10] and "all day" not in first:
            last = last[11:]  # same day: show only the hour
        return f"{first} → {last}"

    def _local(self, value: str):
        """"2026-11-13" -> date; any date-time -> naive local datetime."""
        if len(value) == 10:
            return date.fromisoformat(value)
        moment = datetime.fromisoformat(value)
        if moment.tzinfo:  # e.g. "+01:00" from Google: convert to local time
            moment = moment.astimezone(ZoneInfo(self.tz)).replace(tzinfo=None)
        return moment

    def get_event(self, event_id: str) -> dict:
        return short_event(self._call(self.events.get(calendarId=CALENDAR_ID, eventId=event_id)))

    def create_event(self, summary, start, end, description, location, repeat=None) -> dict:
        body = event_body(summary, start, end, description, location, self.tz, repeat)
        created = self._call(self.events.insert(
            calendarId=CALENDAR_ID, body=body, sendUpdates=NO_EMAILS))
        return short_event(created)

    def add_birthday(self, person: str, day: str) -> dict:
        """A real birthday: shown in Google's "Birthdays" calendar.

        Google's rules for eventType "birthday": one all-day event, repeating
        yearly, transparent (not "busy") and private.
        """
        first = date.fromisoformat(day)
        body = {
            "summary": f"Anniversaire {person}",
            "start": {"date": first.isoformat()},
            "end": {"date": (first + timedelta(days=1)).isoformat()},
            "recurrence": [REPEAT_RULES["yearly"]],
            "eventType": "birthday",
            "birthdayProperties": {"type": "birthday"},
            "transparency": "transparent",
            "visibility": "private",
        }
        created = self._call(self.events.insert(
            calendarId=CALENDAR_ID, body=body, sendUpdates=NO_EMAILS))
        return short_event(created)

    def update_event(self, event_id, summary, start, end, description, location) -> dict:
        body = event_body(summary, start, end, description, location, self.tz)
        if not body:
            raise ValueError("Nothing to change.")
        updated = self._call(self.events.patch(  # patch = change only these fields
            calendarId=CALENDAR_ID, eventId=event_id, body=body, sendUpdates=NO_EMAILS))
        return short_event(updated)

    def delete_event(self, event_id: str) -> dict:
        self._call(self.events.delete(
            calendarId=CALENDAR_ID, eventId=event_id, sendUpdates=NO_EMAILS))
        return {"ok": True}

    @staticmethod
    def _call(request) -> dict:
        """Run a Google API request; turn HTTP errors into ValueError for the model."""
        try:
            return request.execute()
        except HttpError as e:
            raise ValueError(f"Google Calendar error {e.status_code}: {e.reason}") from e
