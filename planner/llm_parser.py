from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from datetime import date, time, timedelta
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from planner.models import DayPlanInput, ReplanConstraints, ValidationIssue
from planner.prompts import INTERPRET_REJECTION_PROMPT, PARSE_DAY_PLAN_PROMPT


class LLMParserError(RuntimeError):
    pass


SidecarCallable = Callable[[dict[str, Any]], dict[str, Any]]

WEEKDAY_INDEXES = {
    "월": 0,
    "화": 1,
    "수": 2,
    "목": 3,
    "금": 4,
    "토": 5,
    "일": 6,
}


def _date_or_default(value: Any, fallback: date) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return fallback
    return fallback


def _time_text(value: Any, fallback: time) -> str:
    if isinstance(value, time):
        return value.strftime("%H:%M")
    if isinstance(value, str) and value:
        return value
    return fallback.strftime("%H:%M")


def _add_minutes_to_time_text(value: str, minutes: int) -> str:
    hour, minute = [int(part) for part in value.split(":", maxsplit=1)]
    total_minutes = hour * 60 + minute + minutes
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def _extract_weekday_recurring_fixed_events(
    raw_text: str,
    *,
    reference_date: date,
) -> tuple[date, list[dict[str, Any]]] | None:
    match = re.search(
        r"([월화수목금토일])요일부터\s*([월화수목금토일])요일까지.*?매일\s*(\d{1,2})시(?:\s*(\d{1,2})분)?(?:에)?\s*(.+?)\s*(?:일정|스케줄|만들|생성|잡아|추가)",
        raw_text,
    )
    if match is None:
        return None

    start_day = WEEKDAY_INDEXES[match.group(1)]
    end_day = WEEKDAY_INDEXES[match.group(2)]
    if end_day < start_day:
        return None

    hour = int(match.group(3))
    minute = int(match.group(4) or 0)
    title = match.group(5).strip() or "일정"
    start_time = f"{hour:02d}:{minute:02d}"
    end_time = _add_minutes_to_time_text(start_time, 60)
    week_start = reference_date - timedelta(days=reference_date.weekday())
    return (
        week_start,
        [
            {
                "id": f"fixed-{day_offset}-{title}",
                "title": title,
                "day_offset": day_offset,
                "start_time": start_time,
                "end_time": end_time,
            }
            for day_offset in range(start_day, end_day + 1)
        ],
    )


def _normalize_fixed_events_defaults(plan: dict[str, Any]) -> None:
    fixed_events = plan.get("fixed_events")
    if not isinstance(fixed_events, list):
        return
    normalized_events: list[Any] = []
    for index, event in enumerate(fixed_events, start=1):
        if not isinstance(event, dict):
            normalized_events.append(event)
            continue
        normalized_event = dict(event)
        normalized_event["id"] = normalized_event.get("id") or f"event-{index}"
        start_time = _time_text(normalized_event.get("start_time"), time(9, 0))
        end_time = _time_text(normalized_event.get("end_time"), time(10, 0))
        if end_time <= start_time:
            end_time = _add_minutes_to_time_text(start_time, 60)
        normalized_event["start_time"] = start_time
        normalized_event["end_time"] = end_time
        normalized_events.append(normalized_event)
    plan["fixed_events"] = normalized_events


def _apply_day_plan_defaults(
    value: Any,
    *,
    reference_date: date | None,
    raw_text: str = "",
) -> Any:
    if not isinstance(value, dict):
        return value

    plan = dict(value)
    plan_date = _date_or_default(
        plan.get("date"),
        reference_date or date.today(),
    )
    plan["date"] = plan_date.isoformat()
    plan["day_start"] = _time_text(plan.get("day_start"), time(9, 0))
    plan["day_end"] = _time_text(plan.get("day_end"), time(23, 0))
    plan.setdefault("fixed_events", [])

    recurring_events = _extract_weekday_recurring_fixed_events(
        raw_text,
        reference_date=reference_date or plan_date,
    )
    if recurring_events is not None:
        week_start, fixed_events = recurring_events
        plan_date = week_start
        plan["date"] = week_start.isoformat()
        plan["fixed_events"] = fixed_events

    _normalize_fixed_events_defaults(plan)

    if not plan.get("availability_windows"):
        plan["availability_windows"] = [
            {
                "id": f"available-{day_offset}",
                "day_offset": day_offset,
                "start_time": plan["day_start"],
                "end_time": plan["day_end"],
            }
            for day_offset in range(7)
        ]

    if "tasks" in plan and isinstance(plan["tasks"], list):
        normalized_tasks: list[Any] = []
        for index, task in enumerate(plan["tasks"], start=1):
            if not isinstance(task, dict):
                normalized_tasks.append(task)
                continue
            normalized_task = dict(task)
            normalized_task["id"] = normalized_task.get("id") or f"task-{index}"
            if normalized_task.get("priority") is None:
                normalized_task["priority"] = 3
            if normalized_task.get("splittable") is None:
                normalized_task["splittable"] = True
            normalized_task["focus_type"] = normalized_task.get("focus_type") or "any"
            normalized_task["start_date"] = (
                normalized_task.get("start_date") or plan_date.isoformat()
            )
            normalized_task["end_date"] = (
                normalized_task.get("end_date")
                or (plan_date + timedelta(days=6)).isoformat()
            )
            normalized_tasks.append(normalized_task)
        plan["tasks"] = normalized_tasks

    return plan


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
            return DayPlanInput.model_validate(
                _apply_day_plan_defaults(
                    response.get("day_plan", response),
                    reference_date=reference_date,
                    raw_text=raw_text,
                )
            )
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
