from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from planner.models import FixedEvent, ScheduleItem, ScheduleItemType


GOOGLE_CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"
DEFAULT_GOOGLE_TOKEN_FILE = ".google-calendar-token.json"


@dataclass(frozen=True)
class GoogleOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    token_file: Path


def build_authorization_url(flow: Any, *, redirect_uri: str) -> tuple[str, str]:
    flow.redirect_uri = redirect_uri
    return flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        scope=[GOOGLE_CALENDAR_EVENTS_SCOPE],
    )


def create_flow(config: GoogleOAuthConfig):
    from google_auth_oauthlib.flow import Flow

    return Flow.from_client_config(
        {
            "web": {
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "redirect_uris": [config.redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=[GOOGLE_CALENDAR_EVENTS_SCOPE],
    )


def load_credentials(token_file: str | Path):
    from google.oauth2.credentials import Credentials

    path = Path(token_file)
    if not path.exists():
        return None
    return Credentials.from_authorized_user_file(str(path), [GOOGLE_CALENDAR_EVENTS_SCOPE])


def save_credentials(credentials: Any, token_file: str | Path) -> None:
    path = Path(token_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(credentials.to_json(), encoding="utf-8")


def refresh_credentials(credentials: Any) -> Any:
    from google.auth.transport.requests import Request

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    return credentials


def exchange_code_for_credentials(
    config: GoogleOAuthConfig,
    *,
    authorization_response: str,
) -> Any:
    flow = create_flow(config)
    flow.redirect_uri = config.redirect_uri
    flow.fetch_token(authorization_response=authorization_response)
    save_credentials(flow.credentials, config.token_file)
    return flow.credentials


def build_calendar_service(credentials: Any):
    from googleapiclient.discovery import build

    return build("calendar", "v3", credentials=credentials)


def _parse_google_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def calendar_events_to_fixed_events(events: list[dict[str, Any]]) -> list[FixedEvent]:
    fixed_events: list[FixedEvent] = []
    for index, event in enumerate(events, start=1):
        start_value = event.get("start", {}).get("dateTime")
        end_value = event.get("end", {}).get("dateTime")
        if not start_value or not end_value:
            continue

        event_id = str(event.get("id") or index)
        fixed_events.append(
            FixedEvent(
                id=f"gcal-{event_id}",
                title=str(event.get("summary") or "Untitled event"),
                start_time=_parse_google_datetime(start_value).timetz().replace(tzinfo=None),
                end_time=_parse_google_datetime(end_value).timetz().replace(tzinfo=None),
                category="google_calendar",
            )
        )
    return fixed_events


def _day_window(target_date: date, timezone: str) -> tuple[str, str]:
    tzinfo = ZoneInfo(timezone)
    start = datetime.combine(target_date, time.min, tzinfo=tzinfo)
    end = start + timedelta(days=1)
    return start.isoformat(), end.isoformat()


def import_fixed_events_for_day(
    service: Any,
    *,
    target_date: date,
    timezone: str,
    calendar_id: str = "primary",
) -> list[FixedEvent]:
    time_min, time_max = _day_window(target_date, timezone)
    response = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return calendar_events_to_fixed_events(response.get("items", []))


def _item_datetime(plan_date: date, day_start: time, offset_minutes: int) -> datetime:
    return datetime.combine(plan_date, day_start) + timedelta(minutes=offset_minutes)


def build_task_event_body(
    item: ScheduleItem,
    *,
    plan_date: date,
    day_start: time,
    timezone: str,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "summary": item.title,
        "description": item.reason,
        "start": {
            "dateTime": _item_datetime(plan_date, day_start, item.start_offset).isoformat(),
            "timeZone": timezone,
        },
        "end": {
            "dateTime": _item_datetime(plan_date, day_start, item.end_offset).isoformat(),
            "timeZone": timezone,
        },
    }
    if item.source_id:
        body["extendedProperties"] = {"private": {"plannerSourceId": item.source_id}}
    return body


def export_schedule_items(
    service: Any,
    items: list[ScheduleItem],
    *,
    plan_date: date,
    day_start: time,
    timezone: str,
    calendar_id: str = "primary",
) -> list[dict[str, Any]]:
    exported: list[dict[str, Any]] = []
    for item in items:
        if item.type != ScheduleItemType.TASK:
            continue
        body = build_task_event_body(
            item,
            plan_date=plan_date,
            day_start=day_start,
            timezone=timezone,
        )
        exported.append(
            service.events()
            .insert(calendarId=calendar_id, body=body)
            .execute()
        )
    return exported
