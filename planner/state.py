from __future__ import annotations

from typing import Any, TypedDict

from planner.models import (
    DayPlanInput,
    DraftPlan,
    FinalPlanOutput,
    FreeBlock,
    NormalizedFixedEvent,
    NormalizedTask,
    ReplanConstraints,
    ScheduleItem,
    ValidationIssue,
    ValidationResult,
)


class PlannerState(TypedDict, total=False):
    raw_user_input: str
    parsed_input: DayPlanInput
    input_errors: list[ValidationIssue]
    clarification_questions: list[str]
    normalized_events: list[NormalizedFixedEvent]
    normalized_tasks: list[NormalizedTask]
    free_blocks: list[FreeBlock]
    classified_blocks: list[FreeBlock]
    ranked_tasks: list[Any]
    draft_plan: DraftPlan
    validation_result: ValidationResult
    warnings: list[ValidationIssue]
    unassigned_tasks: list[Any]
    explanation: str
    approval_status: str
    rejection_reason: str
    replan_constraints: ReplanConstraints
    replan_count: int
    use_llm_replan: bool
    final_plan: FinalPlanOutput
    schedule_items: list[ScheduleItem]
