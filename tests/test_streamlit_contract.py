from datetime import date, time

from app import (
    build_structured_input,
    schedule_items_to_rows,
    warning_summary_rows,
)
from planner.models import (
    ScheduleItem,
    ScheduleItemType,
    Task,
    UnassignedReasonCode,
    UnassignedTask,
    ValidationIssue,
)


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
