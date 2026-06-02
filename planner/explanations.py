from __future__ import annotations

from planner.models import DraftPlan, ScheduleItemType


def build_rule_based_explanation(draft_plan: DraftPlan) -> str:
    task_items = [
        item for item in draft_plan.schedule_items if item.type == ScheduleItemType.TASK
    ]
    parts: list[str] = []

    if task_items:
        first_task = task_items[0]
        parts.append(f"{first_task.title}을 먼저 배치했습니다.")
    else:
        parts.append("배치된 작업이 없습니다.")

    if draft_plan.unassigned_tasks:
        parts.append(f"미배치 작업 {len(draft_plan.unassigned_tasks)}개가 있습니다.")

    if draft_plan.target_buffer_minutes:
        parts.append(f"목표 buffer는 {draft_plan.target_buffer_minutes}분입니다.")

    return " ".join(parts)
