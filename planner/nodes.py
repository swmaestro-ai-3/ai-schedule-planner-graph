from __future__ import annotations

from planner.explanations import build_rule_based_explanation
from planner.llm_parser import (
    build_clarification_questions,
    call_llm_sidecar,
    interpret_rejection_reason,
    parse_natural_language_input,
)
from planner.models import DraftPlan
from planner.scheduler import (
    classify_free_blocks,
    compute_free_blocks,
    place_tasks,
)
from planner.state import PlannerState
from planner.validators import (
    build_final_output,
    normalize_fixed_events,
    normalize_tasks,
    time_to_minutes,
    validate_day_plan_input,
    validate_draft_plan,
)


def parse_input_node(state: PlannerState) -> PlannerState:
    if "parsed_input" in state:
        return {}
    if not state.get("raw_user_input"):
        return {
            "input_errors": [],
            "clarification_questions": ["일정 입력을 알려주세요."],
        }
    try:
        return {"parsed_input": parse_natural_language_input(state["raw_user_input"])}
    except Exception as exc:
        return {
            "input_errors": [],
            "clarification_questions": [str(exc)],
        }


def apply_replan_constraints_node(state: PlannerState) -> PlannerState:
    plan_input = state.get("parsed_input")
    if plan_input is None:
        return {}
    if state.get("approval_status") != "rejected":
        return {}
    if not state.get("rejection_reason"):
        return {}
    if state.get("replan_count", 0) >= 3:
        return {}

    constraints = interpret_rejection_reason(
        state.get("rejection_reason", ""),
        state,
        sidecar=call_llm_sidecar if state.get("use_llm_replan") else None,
    )
    updated_input = plan_input

    if constraints.buffer_ratio_delta:
        updated_input = updated_input.model_copy(
            update={
                "buffer_ratio": min(
                    1.0,
                    max(0.0, updated_input.buffer_ratio + constraints.buffer_ratio_delta),
                )
            }
        )

    if constraints.fixed_event_buffer_after:
        updated_input = updated_input.model_copy(
            update={
                "fixed_events": [
                    event.model_copy(
                        update={
                            "buffer_after_minutes": max(
                                event.buffer_after_minutes,
                                constraints.fixed_event_buffer_after,
                            )
                        }
                    )
                    for event in updated_input.fixed_events
                ]
            }
        )

    if constraints.excluded_task_ids:
        excluded = set(constraints.excluded_task_ids)
        updated_input = updated_input.model_copy(
            update={
                "tasks": [
                    task for task in updated_input.tasks if task.id not in excluded
                ]
            }
        )

    return {
        "parsed_input": updated_input,
        "replan_constraints": constraints,
        "replan_count": state.get("replan_count", 0) + 1,
        "approval_status": "pending",
    }


def validate_input_node(state: PlannerState) -> PlannerState:
    plan_input = state.get("parsed_input")
    if plan_input is None:
        return {"clarification_questions": ["구조화된 일정 정보가 필요합니다."]}
    return {"input_errors": validate_day_plan_input(plan_input)}


def clarification_node(state: PlannerState) -> PlannerState:
    questions = state.get("clarification_questions") or build_clarification_questions(
        state.get("input_errors", [])
    )
    return {"clarification_questions": questions}


def normalize_time_node(state: PlannerState) -> PlannerState:
    plan_input = state["parsed_input"]
    return {
        "normalized_events": normalize_fixed_events(plan_input),
        "normalized_tasks": normalize_tasks(plan_input),
    }


def compute_free_blocks_node(state: PlannerState) -> PlannerState:
    plan_input = state["parsed_input"]
    day_length = time_to_minutes(plan_input.day_end) - time_to_minutes(plan_input.day_start)
    return {
        "free_blocks": compute_free_blocks(
            0,
            day_length,
            state.get("normalized_events", []),
        )
    }


def classify_blocks_node(state: PlannerState) -> PlannerState:
    plan_input = state["parsed_input"]
    return {
        "classified_blocks": classify_free_blocks(
            state.get("free_blocks", []),
            min_task_block_minutes=plan_input.min_task_block_minutes,
            deep_work_threshold_minutes=plan_input.deep_work_threshold_minutes,
        )
    }


def rank_tasks_node(state: PlannerState) -> PlannerState:
    plan_input = state["parsed_input"]
    ranked_tasks = sorted(
        plan_input.tasks,
        key=lambda task: (
            1 if task.hard_deadline else 0,
            task.priority,
            task.estimated_minutes or 0,
        ),
        reverse=True,
    )
    return {"ranked_tasks": ranked_tasks}


def place_tasks_node(state: PlannerState) -> PlannerState:
    plan_input = state["parsed_input"]
    replan_constraints = state.get("replan_constraints")
    draft = place_tasks(
        plan_input,
        state.get("classified_blocks", []),
        ranked_tasks=state.get("ranked_tasks"),
        normalized_events=state.get("normalized_events"),
        snoozed_task_days=replan_constraints.snoozed_task_days
        if replan_constraints
        else None,
    )
    return {
        "draft_plan": draft,
        "schedule_items": draft.schedule_items,
        "unassigned_tasks": draft.unassigned_tasks,
    }


def validate_plan_node(state: PlannerState) -> PlannerState:
    draft = state.get("draft_plan") or DraftPlan()
    result = validate_draft_plan(draft)
    return {
        "validation_result": result,
        "warnings": [issue for issue in result.issues if not issue.blocking],
    }


def generate_explanation_node(state: PlannerState) -> PlannerState:
    draft = state.get("draft_plan") or DraftPlan()
    return {"explanation": build_rule_based_explanation(draft)}


def approval_node(state: PlannerState) -> PlannerState:
    if state.get("approval_status") == "rejected" and state.get("replan_count", 0) >= 3:
        return {"explanation": "자동 재계획 한도에 도달했습니다."}
    return {"approval_status": state.get("approval_status", "pending")}


def interpret_rejection_node(state: PlannerState) -> PlannerState:
    constraints = interpret_rejection_reason(state.get("rejection_reason", ""), state)
    return {
        "replan_constraints": constraints,
        "replan_count": state.get("replan_count", 0) + 1,
        "approval_status": "pending",
    }


def finalize_node(state: PlannerState) -> PlannerState:
    draft = state.get("draft_plan") or DraftPlan()
    validation = state.get("validation_result")
    issues = validation.issues if validation else []
    return {
        "final_plan": build_final_output(
            draft,
            issues,
            state.get("explanation", ""),
        )
    }
