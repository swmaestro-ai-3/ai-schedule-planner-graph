from datetime import date, time

from planner.google_calendar import (
    GOOGLE_CALENDAR_EVENTS_SCOPE,
    build_authorization_url,
    build_task_event_body,
    calendar_events_to_fixed_events,
    import_fixed_events_for_day,
)
from planner.models import ScheduleItem, ScheduleItemType


class FakeFlow:
    def __init__(self):
        self.redirect_uri = None

    def authorization_url(self, **kwargs):
        assert GOOGLE_CALENDAR_EVENTS_SCOPE in kwargs["scope"]
        assert kwargs["access_type"] == "offline"
        return ("https://accounts.google.com/o/oauth2/auth?state=fake", "fake-state")


class FakeEventsResource:
    def __init__(self, events):
        self.events = events
        self.list_kwargs = None

    def list(self, **kwargs):
        self.list_kwargs = kwargs
        return self

    def execute(self):
        return {"items": self.events}


class FakeCalendarService:
    def __init__(self, events):
        self.events_resource = FakeEventsResource(events)

    def events(self):
        return self.events_resource


def test_build_authorization_url_uses_calendar_events_scope():
    flow = FakeFlow()

    url, state = build_authorization_url(
        flow,
        redirect_uri="http://localhost:8501",
    )

    assert state == "fake-state"
    assert url.startswith("https://accounts.google.com/")
    assert flow.redirect_uri == "http://localhost:8501"


def test_calendar_events_to_fixed_events_maps_timed_events():
    fixed_events = calendar_events_to_fixed_events(
        [
            {
                "id": "event-1",
                "summary": "회의",
                "start": {"dateTime": "2026-06-03T10:00:00+09:00"},
                "end": {"dateTime": "2026-06-03T11:00:00+09:00"},
            }
        ]
    )

    assert fixed_events[0].id == "gcal-event-1"
    assert fixed_events[0].title == "회의"
    assert fixed_events[0].start_time == time(10, 0)
    assert fixed_events[0].end_time == time(11, 0)


def test_import_fixed_events_for_day_queries_time_window():
    service = FakeCalendarService(
        [
            {
                "id": "event-1",
                "summary": "회의",
                "start": {"dateTime": "2026-06-03T10:00:00+09:00"},
                "end": {"dateTime": "2026-06-03T11:00:00+09:00"},
            }
        ]
    )

    fixed_events = import_fixed_events_for_day(
        service,
        target_date=date(2026, 6, 3),
        timezone="Asia/Seoul",
    )

    assert fixed_events[0].title == "회의"
    assert service.events_resource.list_kwargs["calendarId"] == "primary"
    assert service.events_resource.list_kwargs["singleEvents"] is True
    assert "2026-06-03T00:00:00" in service.events_resource.list_kwargs["timeMin"]


def test_build_task_event_body_uses_day_start_offsets():
    item = ScheduleItem(
        type=ScheduleItemType.TASK,
        title="알고리즘 과제",
        start_offset=180,
        end_offset=300,
        source_id="task-1",
        reason="오늘 마감입니다.",
    )

    body = build_task_event_body(
        item,
        plan_date=date(2026, 6, 3),
        day_start=time(9, 0),
        timezone="Asia/Seoul",
    )

    assert body["summary"] == "알고리즘 과제"
    assert body["description"] == "오늘 마감입니다."
    assert body["start"]["dateTime"] == "2026-06-03T12:00:00"
    assert body["end"]["dateTime"] == "2026-06-03T14:00:00"
    assert body["start"]["timeZone"] == "Asia/Seoul"
