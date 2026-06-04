from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from datetime import date, time, timedelta
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from planner.models import (
    AvailabilityWindow,
    DayPlanInput,
    ReplanConstraints,
    ValidationIssue,
)
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

KOREAN_NUMBER_VALUES = {
    "한": 1,
    "하나": 1,
    "두": 2,
    "둘": 2,
    "세": 3,
    "셋": 3,
    "네": 4,
    "넷": 4,
    "다섯": 5,
    "여섯": 6,
}

KOREAN_TIME_PATTERN = re.compile(
    r"(?:(오전|오후|저녁|밤|아침|새벽)\s*)?(\d{1,2})시(?!간)(?:\s*(\d{1,2})분)?"
)


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


def _number_text_to_int(value: str | None) -> int | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized.isdigit():
        return int(normalized)
    return KOREAN_NUMBER_VALUES.get(normalized)


def _time_text_to_minutes(value: Any, fallback: time) -> int:
    if isinstance(value, time):
        return value.hour * 60 + value.minute
    if isinstance(value, str):
        match = re.fullmatch(r"(\d{1,2}):(\d{2})", value.strip())
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            if hour == 24 and minute == 0:
                return 24 * 60
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return hour * 60 + minute
    return fallback.hour * 60 + fallback.minute


def _minutes_to_time_text(total_minutes: int) -> str:
    clamped = max(0, min(total_minutes, 24 * 60 - 1))
    return f"{clamped // 60:02d}:{clamped % 60:02d}"


def _add_minutes_to_time_text(value: str, minutes: int) -> str:
    total_minutes = _time_text_to_minutes(value, time(9, 0)) + minutes
    return _minutes_to_time_text(total_minutes)


def _korean_time_match_to_minutes(
    match: re.Match[str],
    *,
    default_meridiem: str | None = None,
) -> int:
    return _korean_time_parts_to_minutes(
        match.group(1),
        match.group(2),
        match.group(3),
        default_meridiem=default_meridiem,
    )


def _korean_time_parts_to_minutes(
    meridiem_value: str | None,
    hour_value: str,
    minute_value: str | None,
    *,
    default_meridiem: str | None = None,
) -> int:
    meridiem = meridiem_value or default_meridiem
    hour = int(hour_value)
    minute = int(minute_value or 0)
    if meridiem in {"오후", "저녁", "밤"} and hour < 12:
        hour += 12
    if meridiem in {"오전", "새벽"} and hour == 12:
        hour = 0
    return hour * 60 + minute


def _find_first_korean_time(raw_text: str) -> tuple[int, int, re.Match[str]] | None:
    match = KOREAN_TIME_PATTERN.search(raw_text)
    if match is None:
        return None
    return _korean_time_match_to_minutes(match), match.end(), match


def _parse_duration_minutes(raw_text: str, default_minutes: int = 60) -> int:
    hour_match = re.search(
        r"(\d+|한|하나|두|둘|세|셋|네|넷|다섯|여섯)\s*시간(?:\s*(\d+)\s*분)?",
        raw_text,
    )
    if hour_match:
        hours = _number_text_to_int(hour_match.group(1)) or 0
        minutes = int(hour_match.group(2) or 0)
        return max(1, hours * 60 + minutes)
    minute_match = re.search(r"(\d+)\s*분", raw_text)
    if minute_match:
        return max(1, int(minute_match.group(1)))
    return default_minutes


def _strip_duration_words(value: str) -> str:
    cleaned = re.sub(
        r"(\d+|한|하나|두|둘|세|셋|네|넷|다섯|여섯)\s*시간(?:\s*\d+\s*분)?\s*(?:정도|쯤|가량)?",
        "",
        value,
    )
    cleaned = re.sub(r"\d+\s*분\s*(?:정도|쯤|가량)?", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" .,은는을를으로로")


def _extract_title_after_time(raw_text: str, time_end_index: int) -> str:
    tail = raw_text[time_end_index:]
    tail = re.sub(r"^\s*에\s*", "", tail)
    match = re.search(
        r"(.+?)\s*(?:일정으로|고정\s*일정|일정|루틴으로|루틴|스케줄|넣|추가|만들|생성|잡아)",
        tail,
    )
    candidate = match.group(1) if match else tail
    title = _strip_duration_words(candidate)
    return title or "일정"


def _week_start(reference_date: date) -> date:
    return reference_date - timedelta(days=reference_date.weekday())


def _unique_offsets(offsets: list[int]) -> list[int]:
    return sorted({offset for offset in offsets if 0 <= offset <= 6})


def _extract_day_offsets(raw_text: str, reference_date: date) -> list[int] | None:
    range_match = re.search(
        r"([월화수목금토일])요일부터\s*([월화수목금토일])요일까지",
        raw_text,
    )
    if range_match:
        start_day = WEEKDAY_INDEXES[range_match.group(1)]
        end_day = WEEKDAY_INDEXES[range_match.group(2)]
        if end_day >= start_day:
            return list(range(start_day, end_day + 1))

    relative_match = re.search(
        r"(오늘|내일|모레|글피)?(?:부터)?\s*(\d+)일\s*동안.*?매일",
        raw_text,
    )
    if relative_match:
        relative_days = {"오늘": 0, None: 0, "내일": 1, "모레": 2, "글피": 3}
        start_offset = reference_date.weekday() + relative_days[relative_match.group(1)]
        duration_days = int(relative_match.group(2))
        return _unique_offsets(
            list(range(start_offset, start_offset + duration_days))
        )

    if "평일" in raw_text:
        return list(range(5))
    if "주말" in raw_text:
        return [5, 6]

    shorthand_offsets = {
        "월화수목금": [0, 1, 2, 3, 4],
        "월수금": [0, 2, 4],
        "화목": [1, 3],
        "토일": [5, 6],
    }
    for token, offsets in shorthand_offsets.items():
        if token in raw_text:
            return offsets

    weekday_names = re.findall(r"([월화수목금토일])요일", raw_text)
    if weekday_names:
        return _unique_offsets([WEEKDAY_INDEXES[name] for name in weekday_names])

    if "매일" in raw_text:
        return list(range(7))
    return None


def _looks_like_fixed_event_request(raw_text: str) -> bool:
    if "가능" in raw_text and "부터" in raw_text and "루틴" not in raw_text:
        return any(marker in raw_text for marker in ("고정", "일정으로", "일정 추가"))
    return any(
        marker in raw_text
        for marker in ("루틴", "고정", "일정", "스케줄", "캘린더", "넣어", "추가")
    )


def _extract_weekday_recurring_fixed_events(
    raw_text: str,
    *,
    reference_date: date,
) -> tuple[date, list[dict[str, Any]]] | None:
    if not _looks_like_fixed_event_request(raw_text):
        return None

    day_offsets = _extract_day_offsets(raw_text, reference_date)
    time_match = _find_first_korean_time(raw_text)
    if not day_offsets or time_match is None:
        return None

    start_minutes, time_end_index, _match = time_match
    duration_minutes = _parse_duration_minutes(raw_text)
    title = _extract_title_after_time(raw_text, time_end_index)
    start_time = _minutes_to_time_text(start_minutes)
    end_time = _minutes_to_time_text(start_minutes + duration_minutes)
    return (
        _week_start(reference_date),
        [
            {
                "id": f"fixed-{day_offset}-{title}",
                "title": title,
                "day_offset": day_offset,
                "start_time": start_time,
                "end_time": end_time,
            }
            for day_offset in day_offsets
        ],
    )


def _extract_explicit_availability_windows(
    raw_text: str,
    *,
    reference_date: date,
) -> list[dict[str, Any]] | None:
    if "가능" not in raw_text and "가용" not in raw_text:
        return None
    match = re.search(
        r"(?:(오전|오후|저녁|밤|아침|새벽)\s*)?(\d{1,2})시(?!간)(?:\s*(\d{1,2})분)?\s*부터\s*"
        r"(?:(오전|오후|저녁|밤|아침|새벽)\s*)?(\d{1,2})시(?!간)(?:\s*(\d{1,2})분)?",
        raw_text,
    )
    if match is None:
        return None

    start_minutes = _korean_time_parts_to_minutes(
        match.group(1),
        match.group(2),
        match.group(3),
    )
    end_minutes = _korean_time_parts_to_minutes(
        match.group(4),
        match.group(5),
        match.group(6),
        default_meridiem=match.group(1),
    )
    if end_minutes <= start_minutes:
        end_minutes += 12 * 60
    if end_minutes <= start_minutes:
        return None

    day_offsets = _extract_day_offsets(raw_text, reference_date) or list(range(7))
    return [
        {
            "id": f"available-{day_offset}",
            "day_offset": day_offset,
            "start_time": _minutes_to_time_text(start_minutes),
            "end_time": _minutes_to_time_text(end_minutes),
        }
        for day_offset in day_offsets
    ]


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
        start_minutes = _time_text_to_minutes(
            normalized_event.get("start_time"),
            time(9, 0),
        )
        end_minutes = _time_text_to_minutes(
            normalized_event.get("end_time"),
            time(10, 0),
        )
        if end_minutes <= start_minutes:
            end_minutes = start_minutes + 60
        normalized_event["start_time"] = _minutes_to_time_text(start_minutes)
        normalized_event["end_time"] = _minutes_to_time_text(end_minutes)
        normalized_events.append(normalized_event)
    plan["fixed_events"] = normalized_events


def _expand_day_bounds_for_fixed_events(plan: dict[str, Any]) -> None:
    fixed_events = plan.get("fixed_events")
    if not isinstance(fixed_events, list):
        return
    day_start_minutes = _time_text_to_minutes(plan.get("day_start"), time(9, 0))
    day_end_minutes = _time_text_to_minutes(plan.get("day_end"), time(23, 0))
    event_starts: list[int] = []
    event_ends: list[int] = []
    for event in fixed_events:
        if not isinstance(event, dict):
            continue
        event_starts.append(_time_text_to_minutes(event.get("start_time"), time(9, 0)))
        event_ends.append(_time_text_to_minutes(event.get("end_time"), time(10, 0)))
    if event_starts and min(event_starts) < day_start_minutes:
        plan["day_start"] = _minutes_to_time_text(min(event_starts))
    if event_ends and max(event_ends) > day_end_minutes:
        plan["day_end"] = _minutes_to_time_text(max(event_ends))


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
    _expand_day_bounds_for_fixed_events(plan)

    explicit_availability = _extract_explicit_availability_windows(
        raw_text,
        reference_date=reference_date or plan_date,
    )
    if explicit_availability is not None:
        plan["availability_windows"] = explicit_availability
    elif not plan.get("availability_windows"):
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
    state = current_state or {}
    return {
        "task": "interpret_rejection",
        "prompt": INTERPRET_REJECTION_PROMPT,
        "input": reason,
        "conversation": _summarize_conversation(state.get("conversation")),
        "current_state": _summarize_state_for_rejection(state),
        "output_schema": {
            "type": "object",
            "required": ["replan_constraints"],
            "properties": {
                "replan_constraints": ReplanConstraints.model_json_schema(),
            },
        },
    }


def _summarize_conversation(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    messages: list[dict[str, str]] = []
    for item in value[-8:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        text = str(item.get("text") or "").strip()
        if role not in {"agent", "user"} or not text:
            continue
        messages.append({"role": role, "text": text[:500]})
    return messages


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
                "day_offset": item.day_offset,
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
            fallback_plan = _rule_based_day_plan_fallback(
                raw_text,
                reference_date=reference_date,
                timezone=timezone,
            )
            if fallback_plan is not None:
                return fallback_plan
    raise LLMParserError("Structured input is required") from last_error


def _rule_based_day_plan_fallback(
    raw_text: str,
    *,
    reference_date: date | None,
    timezone: str,
) -> DayPlanInput | None:
    fallback_date = reference_date or date.today()
    value = _apply_day_plan_defaults(
        {
            "date": fallback_date.isoformat(),
            "timezone": timezone,
            "day_start": None,
            "day_end": None,
            "availability_windows": [],
            "fixed_events": [],
            "tasks": [],
        },
        reference_date=reference_date,
        raw_text=raw_text,
    )
    if not isinstance(value, dict) or not value.get("fixed_events"):
        return None
    return DayPlanInput.model_validate(value)


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


def _tasks_from_state(current_state: dict[str, Any] | None) -> list[Any]:
    plan_input = (current_state or {}).get("parsed_input")
    return list(getattr(plan_input, "tasks", []) or [])


def _matching_task_ids_from_reason(
    reason: str,
    current_state: dict[str, Any] | None,
) -> list[str]:
    tasks = _tasks_from_state(current_state)
    matched = [
        task.id
        for task in tasks
        if getattr(task, "title", "") and getattr(task, "title", "") in reason
    ]
    if matched:
        return matched
    if len(tasks) == 1:
        return [tasks[0].id]
    return []


def _extract_snooze_days(
    reason: str,
    current_state: dict[str, Any] | None,
) -> int | None:
    relative_days = {
        "내일": 1,
        "모레": 2,
        "글피": 3,
        "하루": 1,
        "이틀": 2,
        "사흘": 3,
    }
    for token, days in relative_days.items():
        if token in reason:
            return days
    day_match = re.search(r"(\d+)일\s*(?:뒤|후|뒤로|후로)", reason)
    if day_match:
        return int(day_match.group(1))
    if "다음 주" in reason or "다음주" in reason:
        return 6
    weekday_match = re.search(r"([월화수목금토일])요일?로", reason)
    if weekday_match:
        plan_input = (current_state or {}).get("parsed_input")
        plan_date = getattr(plan_input, "date", date.today())
        target_weekday = WEEKDAY_INDEXES[weekday_match.group(1)]
        delta = target_weekday - plan_date.weekday()
        if delta <= 0:
            delta += 7
        return delta
    return None


def _extract_preferred_time(reason: str) -> str | None:
    if not any(marker in reason for marker in ("수정", "변경", "바꿔", "옮겨")):
        return None
    time_match = _find_first_korean_time(reason)
    if time_match is None:
        return None
    start_minutes, _time_end_index, _match = time_match
    return _minutes_to_time_text(start_minutes)


def _task_day_move_requested(reason: str) -> bool:
    return any(
        marker in reason
        for marker in ("옮겨", "이동", "변경", "바꿔", "수정")
    )


def _extract_task_day_offsets(
    reason: str,
    current_state: dict[str, Any] | None,
) -> dict[str, int]:
    if not _task_day_move_requested(reason):
        return {}
    plan_input = (current_state or {}).get("parsed_input")
    if not isinstance(plan_input, DayPlanInput):
        return {}
    day_offsets = _extract_day_offsets(reason, plan_input.date)
    if not day_offsets or len(day_offsets) != 1:
        return {}
    return {
        task_id: day_offsets[0]
        for task_id in _matching_task_ids_from_reason(reason, current_state)
    }


def _extract_duration_multiplier(reason: str) -> float | None:
    if "절반" in reason or "반으로" in reason:
        return 0.5
    multiplier_match = re.search(
        r"(\d+(?:\.\d+)?|한|하나|두|둘|세|셋|네|넷|다섯|여섯)\s*배",
        reason,
    )
    if multiplier_match is None:
        return None
    raw_value = multiplier_match.group(1)
    if raw_value.replace(".", "", 1).isdigit():
        return float(raw_value)
    number_value = _number_text_to_int(raw_value)
    return float(number_value) if number_value is not None else None


def _duration_multiplier_requires_task_update(reason: str) -> bool:
    return any(
        marker in reason
        for marker in (
            "시간",
            "소요",
            "분량",
            "기간",
            "늘",
            "증가",
            "줄",
            "감소",
            "걸",
            "필요",
        )
    )


def _extract_duration_multipliers(
    reason: str,
    current_state: dict[str, Any] | None,
) -> dict[str, float]:
    multiplier = _extract_duration_multiplier(reason)
    if multiplier is None or not _duration_multiplier_requires_task_update(reason):
        return {}
    return {
        task_id: multiplier
        for task_id in _matching_task_ids_from_reason(reason, current_state)
    }


def _availability_update_requested(reason: str) -> bool:
    return any(
        marker in reason
        for marker in (
            "가능",
            "가용",
            "사용할 수",
            "쓸 수",
            "시간 밖에",
            "시간밖에",
            "비어",
            "빈 시간",
        )
    )


def _extract_availability_overrides(
    reason: str,
    current_state: dict[str, Any] | None,
) -> list[AvailabilityWindow]:
    if not _availability_update_requested(reason):
        return []
    plan_input = (current_state or {}).get("parsed_input")
    if not isinstance(plan_input, DayPlanInput):
        return []

    day_offsets = _extract_day_offsets(reason, plan_input.date)
    if not day_offsets:
        return []

    explicit_windows = _extract_explicit_availability_windows(
        reason,
        reference_date=plan_input.date,
    )
    if explicit_windows is not None:
        return [
            AvailabilityWindow.model_validate(
                {
                    **window,
                    "id": f"override-available-{window['day_offset']}",
                }
            )
            for window in explicit_windows
        ]

    duration_minutes = _parse_duration_minutes(reason, default_minutes=0)
    if duration_minutes <= 0:
        return []

    preferred_start = _find_first_korean_time(reason)
    day_start_minutes = _time_text_to_minutes(plan_input.day_start, time(9, 0))
    day_end_minutes = _time_text_to_minutes(plan_input.day_end, time(18, 0))
    start_minutes = preferred_start[0] if preferred_start is not None else day_start_minutes
    start_minutes = max(day_start_minutes, min(start_minutes, day_end_minutes))
    end_minutes = min(start_minutes + duration_minutes, day_end_minutes)
    if end_minutes <= start_minutes:
        return []

    return [
        AvailabilityWindow(
            id=f"override-available-{day_offset}",
            day_offset=day_offset,
            start_time=time(start_minutes // 60, start_minutes % 60),
            end_time=time(end_minutes // 60, end_minutes % 60),
        )
        for day_offset in day_offsets
    ]


def _interpret_rejection_reason_with_rules(
    reason: str,
    current_state: dict[str, Any] | None = None,
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
    elif any(marker in reason for marker in ("미뤄", "스누즈", "내일", "모레", "다음주", "다음 주")):
        days = _extract_snooze_days(reason, current_state)
        if days is not None:
            for task_id in _matching_task_ids_from_reason(reason, current_state):
                constraints.snoozed_task_days[task_id] = days

    preferred_time = _extract_preferred_time(reason)
    if preferred_time is not None:
        for task_id in _matching_task_ids_from_reason(reason, current_state):
            constraints.preferred_windows[task_id] = preferred_time
    constraints.task_day_offsets.update(
        _extract_task_day_offsets(reason, current_state)
    )
    constraints.duration_multipliers.update(
        _extract_duration_multipliers(reason, current_state)
    )
    constraints.availability_overrides.extend(
        _extract_availability_overrides(reason, current_state)
    )
    return constraints


def _normalize_snoozed_task_days(values: dict[str, int]) -> dict[str, int]:
    return {
        str(task_id): max(1, min(int(days), 6))
        for task_id, days in values.items()
        if task_id and int(days) > 0
    }


def _normalize_task_day_offsets(values: dict[str, int]) -> dict[str, int]:
    return {
        str(task_id): max(0, min(int(day_offset), 6))
        for task_id, day_offset in values.items()
        if task_id
    }


def _normalize_duration_multipliers(values: dict[str, float]) -> dict[str, float]:
    return {
        str(task_id): max(0.25, min(float(multiplier), 6.0))
        for task_id, multiplier in values.items()
        if task_id and float(multiplier) > 0
    }


def _normalize_availability_overrides(
    values: list[AvailabilityWindow],
) -> list[AvailabilityWindow]:
    normalized_by_day: dict[int, AvailabilityWindow] = {}
    for window in values:
        if window.end_time <= window.start_time:
            continue
        normalized_by_day[window.day_offset] = window.model_copy(
            update={"id": window.id or f"override-available-{window.day_offset}"}
        )
    return [
        normalized_by_day[day_offset]
        for day_offset in sorted(normalized_by_day)
    ]


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
    normalized_task_days = _normalize_task_day_offsets(constraints.task_day_offsets)
    if normalized_task_days != constraints.task_day_offsets:
        updates["task_day_offsets"] = normalized_task_days
    normalized_multipliers = _normalize_duration_multipliers(
        constraints.duration_multipliers
    )
    if normalized_multipliers != constraints.duration_multipliers:
        updates["duration_multipliers"] = normalized_multipliers
    normalized_availability = _normalize_availability_overrides(
        constraints.availability_overrides
    )
    if normalized_availability != constraints.availability_overrides:
        updates["availability_overrides"] = normalized_availability
    if updates:
        return constraints.model_copy(update=updates)
    return constraints


def _merge_rule_constraints(
    constraints: ReplanConstraints,
    reason: str,
    current_state: dict[str, Any] | None = None,
) -> ReplanConstraints:
    rule_constraints = _interpret_rejection_reason_with_rules(reason, current_state)
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
    if rule_constraints.preferred_windows:
        updates["preferred_windows"] = {
            **constraints.preferred_windows,
            **rule_constraints.preferred_windows,
        }
    if rule_constraints.task_day_offsets:
        updates["task_day_offsets"] = {
            **constraints.task_day_offsets,
            **rule_constraints.task_day_offsets,
        }
    if rule_constraints.duration_multipliers:
        updates["duration_multipliers"] = {
            **constraints.duration_multipliers,
            **rule_constraints.duration_multipliers,
        }
    if rule_constraints.availability_overrides:
        merged_by_day = {
            window.day_offset: window for window in constraints.availability_overrides
        }
        merged_by_day.update(
            {
                window.day_offset: window
                for window in rule_constraints.availability_overrides
            }
        )
        updates["availability_overrides"] = [
            merged_by_day[day_offset]
            for day_offset in sorted(merged_by_day)
        ]

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
                        current_state,
                    ),
                    reason,
                )
            except (ValidationError, LLMParserError, json.JSONDecodeError) as exc:
                last_error = exc

    constraints = _interpret_rejection_reason_with_rules(reason, current_state)
    if last_error is not None:
        constraints.notes.append(f"LLM 피드백 해석 fallback: {last_error}")
    return _normalize_replan_constraints(constraints, reason)
