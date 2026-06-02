from datetime import date, time

import pytest
from pydantic import ValidationError

from planner.models import (
    DayPlanInput,
    FinalPlanOutput,
    FixedEvent,
    FocusType,
    ScheduleItem,
    ScheduleItemType,
    Task,
)
from planner.state import PlannerState


def test_valid_day_plan_input_uses_expected_defaults():
    plan_input = DayPlanInput(
        date=date(2026, 6, 3),
        day_start=time(9, 0),
        day_end=time(23, 0),
        fixed_events=[
            FixedEvent(
                id="class-1",
                title="전공 수업",
                start_time=time(10, 0),
                end_time=time(12, 0),
            )
        ],
        tasks=[
            Task(
                id="task-1",
                title="알고리즘 과제",
                estimated_minutes=120,
                priority=5,
                splittable=True,
                focus_type=FocusType.DEEP,
            )
        ],
    )

    assert plan_input.buffer_ratio == 0.1
    assert plan_input.min_task_block_minutes == 30
    assert plan_input.deep_work_threshold_minutes == 90
    assert plan_input.timezone == "Asia/Seoul"


def test_task_rejects_unknown_focus_type():
    with pytest.raises(ValidationError):
        Task(
            id="task-1",
            title="알고리즘 과제",
            estimated_minutes=120,
            priority=5,
            splittable=True,
            focus_type="urgent",
        )


def test_final_plan_requires_approval_by_default():
    output = FinalPlanOutput(
        schedule_items=[
            ScheduleItem(
                type=ScheduleItemType.TASK,
                title="알고리즘 과제",
                start_offset=180,
                end_offset=300,
                source_id="task-1",
                reason="오늘 마감이고 긴 집중 블록에 적합합니다.",
            )
        ],
        explanation="오늘 마감 작업을 먼저 배치했습니다.",
    )

    assert output.approval_required is True


def test_planner_state_contains_required_workflow_fields():
    required_fields = {
        "raw_user_input",
        "parsed_input",
        "input_errors",
        "validation_result",
        "draft_plan",
        "approval_status",
        "rejection_reason",
        "replan_constraints",
        "replan_count",
        "final_plan",
    }

    assert required_fields.issubset(PlannerState.__annotations__)
