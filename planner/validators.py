from __future__ import annotations

from datetime import time

from planner.models import (
    DayPlanInput,
    DraftPlan,
    FeasibilityStatus,
    FinalPlanOutput,
    NormalizedFixedEvent,
    NormalizedTask,
    ScheduleItem,
    UnassignedReasonCode,
    ValidationIssue,
)


def time_to_minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def offset_from_day_start(value: time, day_start: time) -> int:
    return time_to_minutes(value) - time_to_minutes(day_start)


def normalize_fixed_events(plan_input: DayPlanInput) -> list[NormalizedFixedEvent]:
    normalized: list[NormalizedFixedEvent] = []
    for event in sorted(plan_input.fixed_events, key=lambda item: item.start_time):
        normalized.append(
            NormalizedFixedEvent(
                id=event.id,
                title=event.title.strip() or "제목 없는 일정",
                start_offset=offset_from_day_start(event.start_time, plan_input.day_start),
                end_offset=offset_from_day_start(event.end_time, plan_input.day_start),
                category=event.category,
                buffer_before_minutes=event.buffer_before_minutes,
                buffer_after_minutes=event.buffer_after_minutes,
            )
        )
    return normalized


def normalize_tasks(plan_input: DayPlanInput) -> list[NormalizedTask]:
    return [NormalizedTask(**task.model_dump()) for task in plan_input.tasks]


def validate_day_plan_input(plan_input: DayPlanInput) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    day_start_minutes = time_to_minutes(plan_input.day_start)
    day_end_minutes = time_to_minutes(plan_input.day_end)

    if day_end_minutes <= day_start_minutes:
        issues.append(
            ValidationIssue(
                code="INVALID_DAY_RANGE",
                message="하루 종료 시간은 시작 시간보다 늦어야 합니다.",
                blocking=True,
            )
        )

    normalized_events = normalize_fixed_events(plan_input)
    for event in normalized_events:
        if event.end_offset <= event.start_offset:
            issues.append(
                ValidationIssue(
                    code="INVALID_TIME_RANGE",
                    message=f"{event.title}의 종료 시간이 시작 시간보다 빠르거나 같습니다.",
                    blocking=True,
                    source_id=event.id,
                    source_type="fixed_event",
                )
            )
        if event.start_offset < 0 or event.end_offset > day_end_minutes - day_start_minutes:
            issues.append(
                ValidationIssue(
                    code="FIXED_EVENT_OUT_OF_DAY",
                    message=f"{event.title}이 하루 계획 범위를 벗어났습니다.",
                    blocking=True,
                    source_id=event.id,
                    source_type="fixed_event",
                )
            )

    valid_events = [
        event for event in normalized_events if event.end_offset > event.start_offset
    ]
    for previous, current in zip(valid_events, valid_events[1:]):
        if current.start_offset < previous.end_offset:
            issues.append(
                ValidationIssue(
                    code="FIXED_EVENT_OVERLAP",
                    message=f"{previous.title}와 {current.title} 일정이 겹칩니다.",
                    blocking=True,
                    source_id=current.id,
                    source_type="fixed_event",
                )
            )

    seen_event_keys: set[tuple[int, int, str]] = set()
    for event in normalized_events:
        key = (event.start_offset, event.end_offset, event.title)
        if key in seen_event_keys:
            issues.append(
                ValidationIssue(
                    code="DUPLICATE_FIXED_EVENT",
                    message=f"{event.title} 일정이 같은 시간대에 중복됩니다.",
                    blocking=False,
                    source_id=event.id,
                    source_type="fixed_event",
                )
            )
        seen_event_keys.add(key)

    for task in plan_input.tasks:
        if task.estimated_minutes is None:
            issues.append(
                ValidationIssue(
                    code=UnassignedReasonCode.MISSING_DURATION.value,
                    message=f"{task.title}의 예상 소요 시간이 없습니다.",
                    blocking=False,
                    source_id=task.id,
                    source_type="task",
                )
            )

    return issues


def validate_schedule_overlaps(items: list[ScheduleItem]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    sorted_items = sorted(items, key=lambda item: (item.start_offset, item.end_offset))
    for previous, current in zip(sorted_items, sorted_items[1:]):
        if current.start_offset < previous.end_offset:
            issues.append(
                ValidationIssue(
                    code="SCHEDULE_OVERLAP",
                    message=f"{previous.title}와 {current.title} 일정이 겹칩니다.",
                    blocking=True,
                    source_id=current.source_id,
                    source_type=current.type.value,
                )
            )
    return issues


def determine_feasibility(
    issues: list[ValidationIssue],
    draft_plan: DraftPlan | None = None,
) -> FeasibilityStatus:
    if any(issue.blocking for issue in issues):
        return FeasibilityStatus.INVALID_INPUT
    if not draft_plan:
        return FeasibilityStatus.FEASIBLE
    high_priority_unassigned = any(
        item.task.priority >= 5 for item in draft_plan.unassigned_tasks
    )
    if high_priority_unassigned:
        return FeasibilityStatus.TIGHT
    if draft_plan.unassigned_tasks:
        return FeasibilityStatus.TIGHT
    return FeasibilityStatus.FEASIBLE


def build_final_output(
    draft_plan: DraftPlan,
    issues: list[ValidationIssue],
    explanation: str,
) -> FinalPlanOutput:
    warnings = [issue for issue in issues if not issue.blocking]
    return FinalPlanOutput(
        schedule_items=draft_plan.schedule_items,
        warnings=warnings,
        unassigned_tasks=draft_plan.unassigned_tasks,
        feasibility_status=determine_feasibility(issues, draft_plan),
        explanation=explanation,
    )
