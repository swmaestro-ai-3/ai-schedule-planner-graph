from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from planner.models import DayPlanInput, ReplanConstraints, ValidationIssue
from planner.prompts import INTERPRET_REJECTION_PROMPT, PARSE_DAY_PLAN_PROMPT


class LLMParserError(RuntimeError):
    pass


SidecarCallable = Callable[[dict[str, Any]], dict[str, Any]]


def build_day_plan_parse_payload(
    raw_text: str,
    *,
    reference_date: date | None = None,
    timezone: str = "Asia/Seoul",
) -> dict[str, Any]:
    return {
        "task": "parse_day_plan",
        "prompt": PARSE_DAY_PLAN_PROMPT,
        "input": raw_text,
        "reference_date": (reference_date or date.today()).isoformat(),
        "timezone": timezone,
        "output_schema": {
            "type": "object",
            "required": ["day_plan"],
            "properties": {
                "day_plan": DayPlanInput.model_json_schema(),
            },
        },
    }


def build_rejection_interpretation_payload(
    reason: str,
    current_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "task": "interpret_rejection",
        "prompt": INTERPRET_REJECTION_PROMPT,
        "input": reason,
        "current_state": _summarize_state_for_rejection(current_state or {}),
        "output_schema": {
            "type": "object",
            "required": ["replan_constraints"],
            "properties": {
                "replan_constraints": ReplanConstraints.model_json_schema(),
            },
        },
    }


def _summarize_state_for_rejection(state: dict[str, Any]) -> dict[str, Any]:
    draft_plan = state.get("draft_plan")
    plan_input = state.get("parsed_input")
    return {
        "replan_count": state.get("replan_count", 0),
        "date": plan_input.date.isoformat() if plan_input else None,
        "tasks": [
            {
                "id": task.id,
                "title": task.title,
                "estimated_minutes": task.estimated_minutes,
            }
            for task in (plan_input.tasks if plan_input else [])
        ],
        "schedule_items": [
            {
                "type": item.type.value,
                "title": item.title,
                "source_id": item.source_id,
                "start_offset": item.start_offset,
                "end_offset": item.end_offset,
            }
            for item in (draft_plan.schedule_items if draft_plan else [])
        ],
    }


def call_llm_sidecar(
    payload: dict[str, Any],
    command: list[str] | None = None,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    sidecar_command = command or ["node", "llm_sidecar/openai_oauth_client.mjs"]
    try:
        completed = subprocess.run(
            sidecar_command,
            cwd=root,
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=True,
        )
    except Exception as exc:
        message = getattr(exc, "stderr", None) or str(exc)
        raise LLMParserError(f"Sidecar call failed: {message}") from exc
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise LLMParserError("Sidecar returned invalid JSON") from exc


def parse_natural_language_input(
    raw_text: str,
    sidecar: SidecarCallable = call_llm_sidecar,
    max_retries: int = 2,
    reference_date: date | None = None,
    timezone: str = "Asia/Seoul",
) -> DayPlanInput:
    last_error: Exception | None = None
    for _ in range(max_retries):
        try:
            response = sidecar(
                build_day_plan_parse_payload(
                    raw_text,
                    reference_date=reference_date,
                    timezone=timezone,
                )
            )
            return DayPlanInput.model_validate(response.get("day_plan", response))
        except (ValidationError, LLMParserError, json.JSONDecodeError) as exc:
            last_error = exc
    raise LLMParserError("Structured input is required") from last_error


def build_clarification_questions(errors: list[ValidationIssue]) -> list[str]:
    questions: list[str] = []
    for error in errors:
        if error.code in {"MISSING_DATE", "date"}:
            questions.append("계획할 날짜를 알려주세요.")
        elif error.code in {"MISSING_DAY_START", "day_start"}:
            questions.append("하루 시작 시간을 알려주세요.")
        elif error.code in {"MISSING_DAY_END", "day_end"}:
            questions.append("하루 종료 시간을 알려주세요.")
        elif error.code == "MISSING_DURATION":
            questions.append("작업의 예상 소요 시간을 알려주세요.")
        else:
            questions.append(error.message)
    return questions


def _interpret_rejection_reason_with_rules(
    reason: str,
) -> ReplanConstraints:
    constraints = ReplanConstraints(notes=[reason])
    if "빡빡" in reason or "여유" in reason:
        constraints.buffer_ratio_delta = 0.1
    if "회의 직후" in reason or "직후에는 쉬" in reason:
        constraints.fixed_event_buffer_after = 15
    if "오늘 안 해도" in reason:
        constraints.notes.append("사용자가 일부 작업 제외를 요청했습니다.")
    snooze_match = re.search(r"snooze\s+task_id=([^\s]+)\s+days=(\d+)", reason)
    if snooze_match:
        constraints.snoozed_task_days[snooze_match.group(1)] = int(
            snooze_match.group(2)
        )
    return constraints


def _normalize_snoozed_task_days(values: dict[str, int]) -> dict[str, int]:
    return {
        str(task_id): max(1, min(int(days), 6))
        for task_id, days in values.items()
        if task_id and int(days) > 0
    }


def _normalize_replan_constraints(
    constraints: ReplanConstraints,
    reason: str,
) -> ReplanConstraints:
    updates: dict[str, Any] = {}
    if (
        ("회의 직후" in reason or "수업 직후" in reason or "직후에는 쉬" in reason)
        and constraints.fixed_event_buffer_after < 15
    ):
        updates["fixed_event_buffer_after"] = 15
    normalized_snoozes = _normalize_snoozed_task_days(constraints.snoozed_task_days)
    if normalized_snoozes != constraints.snoozed_task_days:
        updates["snoozed_task_days"] = normalized_snoozes
    if updates:
        return constraints.model_copy(update=updates)
    return constraints


def _merge_rule_constraints(
    constraints: ReplanConstraints,
    reason: str,
) -> ReplanConstraints:
    rule_constraints = _interpret_rejection_reason_with_rules(reason)
    updates: dict[str, Any] = {}

    if rule_constraints.buffer_ratio_delta and not constraints.buffer_ratio_delta:
        updates["buffer_ratio_delta"] = rule_constraints.buffer_ratio_delta
    if rule_constraints.fixed_event_buffer_after > constraints.fixed_event_buffer_after:
        updates["fixed_event_buffer_after"] = rule_constraints.fixed_event_buffer_after
    if rule_constraints.snoozed_task_days:
        updates["snoozed_task_days"] = {
            **constraints.snoozed_task_days,
            **rule_constraints.snoozed_task_days,
        }

    if not updates:
        return constraints
    return constraints.model_copy(update=updates)


def interpret_rejection_reason(
    reason: str,
    current_state: dict[str, Any] | None = None,
    sidecar: SidecarCallable | None = None,
    max_retries: int = 1,
) -> ReplanConstraints:
    last_error: Exception | None = None
    if sidecar is not None:
        for _ in range(max_retries):
            try:
                response = sidecar(
                    build_rejection_interpretation_payload(reason, current_state)
                )
                return _normalize_replan_constraints(
                    _merge_rule_constraints(
                        ReplanConstraints.model_validate(
                            response.get("replan_constraints", response)
                        ),
                        reason,
                    ),
                    reason,
                )
            except (ValidationError, LLMParserError, json.JSONDecodeError) as exc:
                last_error = exc

    constraints = _interpret_rejection_reason_with_rules(reason)
    if last_error is not None:
        constraints.notes.append(f"LLM 피드백 해석 fallback: {last_error}")
    return _normalize_replan_constraints(constraints, reason)
