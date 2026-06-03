from datetime import date, time

from planner.models import (
    AvailabilityWindow,
    DayPlanInput,
    FixedEvent,
    Task,
    UnassignedReasonCode,
)
from planner.validators import (
    normalize_fixed_events,
    normalize_tasks,
    validate_day_plan_input,
)


def make_input(*, fixed_events=None, tasks=None, availability_windows=None):
    return DayPlanInput(
        date=date(2026, 6, 3),
        day_start=time(9, 0),
        day_end=time(23, 0),
        availability_windows=availability_windows or [],
        fixed_events=fixed_events or [],
        tasks=tasks or [],
    )


def test_normalizes_fixed_event_to_day_start_offsets():
    plan_input = make_input(
        fixed_events=[
            FixedEvent(
                id="class-1",
                title="전공 수업",
                start_time=time(10, 0),
                end_time=time(12, 0),
            )
        ]
    )

    normalized = normalize_fixed_events(plan_input)

    assert normalized[0].start_offset == 60
    assert normalized[0].end_offset == 180


def test_invalid_fixed_event_time_creates_blocking_issue():
    plan_input = make_input(
        fixed_events=[
            FixedEvent(
                id="bad-event",
                title="잘못된 일정",
                start_time=time(14, 0),
                end_time=time(13, 0),
            )
        ]
    )

    issues = validate_day_plan_input(plan_input)

    assert any(issue.code == "INVALID_TIME_RANGE" and issue.blocking for issue in issues)


def test_overlapping_fixed_events_create_blocking_issue():
    plan_input = make_input(
        fixed_events=[
            FixedEvent(
                id="class-1",
                title="전공 수업",
                start_time=time(10, 0),
                end_time=time(12, 0),
            ),
            FixedEvent(
                id="meeting-1",
                title="팀플 회의",
                start_time=time(11, 30),
                end_time=time(13, 0),
            ),
        ]
    )

    issues = validate_day_plan_input(plan_input)

    assert any(issue.code == "FIXED_EVENT_OVERLAP" and issue.blocking for issue in issues)


def test_task_without_duration_is_marked_missing_duration():
    plan_input = make_input(
        tasks=[
            Task(
                id="task-1",
                title="알고리즘 과제",
                estimated_minutes=None,
                priority=5,
                splittable=True,
            )
        ]
    )

    normalized = normalize_tasks(plan_input)

    assert normalized[0].estimated_minutes is None
    issues = validate_day_plan_input(plan_input)
    assert any(issue.code == UnassignedReasonCode.MISSING_DURATION.value for issue in issues)


def test_task_end_date_before_start_date_is_blocking():
    plan_input = make_input(
        tasks=[
            Task(
                id="task-1",
                title="알고리즘 과제",
                estimated_minutes=120,
                start_date=date(2026, 6, 5),
                end_date=date(2026, 6, 4),
                splittable=True,
            )
        ]
    )

    issues = validate_day_plan_input(plan_input)

    assert any(issue.code == "INVALID_TASK_DATE_RANGE" and issue.blocking for issue in issues)


def test_availability_window_outside_day_range_is_blocking():
    plan_input = make_input(
        availability_windows=[
            AvailabilityWindow(
                id="late",
                day_offset=0,
                start_time=time(8, 0),
                end_time=time(10, 0),
            )
        ]
    )

    issues = validate_day_plan_input(plan_input)

    assert any(issue.code == "AVAILABILITY_OUT_OF_DAY" and issue.blocking for issue in issues)


def test_blank_fixed_event_title_gets_display_fallback():
    plan_input = make_input(
        fixed_events=[
            FixedEvent(
                id="event-1",
                title="",
                start_time=time(10, 0),
                end_time=time(11, 0),
            )
        ]
    )

    normalized = normalize_fixed_events(plan_input)

    assert normalized[0].title == "제목 없는 일정"
