from planner.explanations import build_rule_based_explanation
from planner.models import (
    BufferSummary,
    DraftPlan,
    FeasibilityStatus,
    FreeBlock,
    ScheduleItem,
    ScheduleItemType,
    Task,
    UnassignedReasonCode,
    UnassignedTask,
)
from planner.validators import (
    build_buffer_summary,
    determine_feasibility,
    validate_draft_plan,
)


def test_overlapping_schedule_items_create_blocking_issue():
    draft = DraftPlan(
        schedule_items=[
            ScheduleItem(
                type=ScheduleItemType.TASK,
                title="작업 A",
                start_offset=0,
                end_offset=60,
                source_id="a",
            ),
            ScheduleItem(
                type=ScheduleItemType.TASK,
                title="작업 B",
                start_offset=30,
                end_offset=90,
                source_id="b",
            ),
        ]
    )

    result = validate_draft_plan(draft)

    assert any(issue.code == "SCHEDULE_OVERLAP" and issue.blocking for issue in result.issues)


def test_buffer_summary_reports_shortage():
    summary = build_buffer_summary(
        [
            FreeBlock(id="b1", start_offset=0, end_offset=25),
        ],
        target_buffer_minutes=42,
    )

    assert summary == BufferSummary(target_minutes=42, secured_minutes=25)
    assert summary.shortage_minutes == 17


def test_high_priority_unassigned_task_makes_plan_tight():
    task = Task(
        id="critical",
        title="중요 작업",
        estimated_minutes=60,
        priority=5,
        splittable=False,
    )
    draft = DraftPlan(
        unassigned_tasks=[
            UnassignedTask(
                task=task,
                reason_code=UnassignedReasonCode.NO_AVAILABLE_BLOCK,
                reason="들어갈 수 있는 block이 없습니다.",
            )
        ]
    )

    assert determine_feasibility([], draft) == FeasibilityStatus.TIGHT


def test_task_schedule_items_need_reason():
    draft = DraftPlan(
        schedule_items=[
            ScheduleItem(
                type=ScheduleItemType.TASK,
                title="작업 A",
                start_offset=0,
                end_offset=60,
                source_id="a",
            )
        ]
    )

    result = validate_draft_plan(draft)

    assert any(issue.code == "MISSING_PLACEMENT_REASON" for issue in result.issues)


def test_rule_based_explanation_mentions_unassigned_tasks():
    task = Task(
        id="low",
        title="낮은 우선순위 작업",
        estimated_minutes=60,
        priority=1,
        splittable=False,
    )
    draft = DraftPlan(
        schedule_items=[
            ScheduleItem(
                type=ScheduleItemType.TASK,
                title="중요 작업",
                start_offset=0,
                end_offset=60,
                source_id="high",
                reason="우선순위가 높습니다.",
            )
        ],
        unassigned_tasks=[
            UnassignedTask(
                task=task,
                reason_code=UnassignedReasonCode.NO_AVAILABLE_BLOCK,
                reason="들어갈 수 있는 block이 없습니다.",
            )
        ],
    )

    explanation = build_rule_based_explanation(draft)

    assert "중요 작업" in explanation
    assert "미배치 작업 1개" in explanation


def test_rule_based_explanation_mentions_fixed_events_without_tasks():
    draft = DraftPlan(
        schedule_items=[
            ScheduleItem(
                type=ScheduleItemType.FIXED_EVENT,
                title="운동",
                start_offset=360,
                end_offset=420,
                day_offset=0,
                source_id="exercise-mon",
                reason="고정 일정입니다.",
            ),
            ScheduleItem(
                type=ScheduleItemType.FIXED_EVENT,
                title="운동",
                start_offset=360,
                end_offset=420,
                day_offset=1,
                source_id="exercise-tue",
                reason="고정 일정입니다.",
            ),
        ]
    )

    explanation = build_rule_based_explanation(draft)

    assert "고정 일정 2개" in explanation
    assert "배치된 작업이 없습니다" not in explanation
