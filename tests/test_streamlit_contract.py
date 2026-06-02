from datetime import date, time
from pathlib import Path

from app import (
    build_google_oauth_config,
    build_structured_input,
    exportable_schedule_items,
    fixed_events_to_editor_rows,
    integration_button_labels,
    merge_fixed_event_rows,
    schedule_items_to_rows,
    should_show_openai_oauth_button,
    warning_summary_rows,
)
from planner.models import (
    FinalPlanOutput,
    FixedEvent,
    ScheduleItem,
    ScheduleItemType,
    Task,
    UnassignedReasonCode,
    UnassignedTask,
    ValidationIssue,
)
from planner.openai_oauth import OpenAIOAuthStatus


def test_structured_input_adapter_builds_day_plan_input():
    plan_input = build_structured_input(
        plan_date=date(2026, 6, 3),
        day_start=time(9, 0),
        day_end=time(23, 0),
        buffer_ratio=0.1,
        fixed_event_rows=[
            {
                "id": "class-1",
                "title": "전공 수업",
                "start_time": time(10, 0),
                "end_time": time(12, 0),
                "category": "class",
            }
        ],
        task_rows=[
            {
                "id": "task-1",
                "title": "알고리즘 과제",
                "estimated_minutes": 120,
                "priority": 5,
                "splittable": True,
                "focus_type": "deep",
            }
        ],
    )

    assert plan_input.fixed_events[0].title == "전공 수업"
    assert plan_input.tasks[0].focus_type == "deep"


def test_schedule_items_to_rows_formats_offsets():
    rows = schedule_items_to_rows(
        [
            ScheduleItem(
                type=ScheduleItemType.TASK,
                title="알고리즘 과제",
                start_offset=180,
                end_offset=300,
                reason="오늘 마감입니다.",
            )
        ],
        day_start=time(9, 0),
    )

    assert rows == [
        {
            "time": "12:00~14:00",
            "type": "task",
            "title": "알고리즘 과제",
            "reason": "오늘 마감입니다.",
        }
    ]


def test_warning_summary_rows_includes_warnings_and_unassigned_tasks():
    task = Task(
        id="low",
        title="낮은 우선순위 작업",
        estimated_minutes=60,
        priority=1,
        splittable=False,
    )
    rows = warning_summary_rows(
        warnings=[
            ValidationIssue(
                code="BUFFER_SHORTAGE",
                message="Buffer가 부족합니다.",
            )
        ],
        unassigned_tasks=[
            UnassignedTask(
                task=task,
                reason_code=UnassignedReasonCode.NO_AVAILABLE_BLOCK,
                reason="들어갈 block이 없습니다.",
            )
        ],
    )

    assert rows == [
        {"code": "BUFFER_SHORTAGE", "message": "Buffer가 부족합니다."},
        {"code": "NO_AVAILABLE_BLOCK", "message": "낮은 우선순위 작업: 들어갈 block이 없습니다."},
    ]


def test_fixed_events_to_editor_rows_maps_google_calendar_events():
    rows = fixed_events_to_editor_rows(
        [
            FixedEvent(
                id="gcal-event-1",
                title="회의",
                start_time=time(10, 0),
                end_time=time(11, 0),
                category="google_calendar",
            )
        ]
    )

    assert rows == [
        {
            "id": "gcal-event-1",
            "title": "회의",
            "start_time": time(10, 0),
            "end_time": time(11, 0),
            "category": "google_calendar",
        }
    ]


def test_merge_fixed_event_rows_dedupes_by_id():
    rows = merge_fixed_event_rows(
        [
            {
                "id": "class-1",
                "title": "전공 수업",
                "start_time": time(10, 0),
                "end_time": time(12, 0),
                "category": "class",
            }
        ],
        [
            FixedEvent(
                id="class-1",
                title="중복",
                start_time=time(10, 0),
                end_time=time(12, 0),
            ),
            FixedEvent(
                id="gcal-event-1",
                title="회의",
                start_time=time(14, 0),
                end_time=time(15, 0),
            ),
        ],
    )

    assert [row["id"] for row in rows] == ["class-1", "gcal-event-1"]


def test_exportable_schedule_items_requires_approved_final_plan():
    item = ScheduleItem(
        type=ScheduleItemType.TASK,
        title="알고리즘 과제",
        start_offset=180,
        end_offset=300,
    )

    assert exportable_schedule_items({}) == []
    assert exportable_schedule_items({"draft_plan": object()}) == []
    assert exportable_schedule_items(
        {"final_plan": FinalPlanOutput(schedule_items=[item])}
    ) == [item]


def test_build_google_oauth_config_resolves_relative_token_file(tmp_path):
    config = build_google_oauth_config(
        env={
            "GOOGLE_OAUTH_CLIENT_ID": "client-id",
            "GOOGLE_OAUTH_CLIENT_SECRET": "secret",
            "GOOGLE_OAUTH_REDIRECT_URI": "http://localhost:8501",
            "GOOGLE_TOKEN_FILE": "tokens/google.json",
        },
        cwd=tmp_path,
    )

    assert config is not None
    assert config.client_id == "client-id"
    assert config.token_file == tmp_path / "tokens" / "google.json"
    assert build_google_oauth_config(env={}, cwd=Path("/tmp")) is None


def test_integration_button_labels_are_one_per_provider():
    assert integration_button_labels() == [
        "Google Calendar 연동",
        "OpenAI OAuth 연동",
    ]


def test_openai_oauth_button_hides_when_proxy_is_connected():
    assert (
        should_show_openai_oauth_button(
            OpenAIOAuthStatus(
                connected=True,
                message="connected",
                models=["gpt-5"],
            )
        )
        is False
    )
    assert (
        should_show_openai_oauth_button(
            OpenAIOAuthStatus(
                connected=False,
                message="not connected",
            )
        )
        is True
    )
