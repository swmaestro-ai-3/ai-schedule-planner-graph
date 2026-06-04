from __future__ import annotations

import re
from datetime import date, time, timedelta
from pathlib import Path
from typing import Any

from planner.graph import build_planner_graph
from planner.llm_parser import SidecarCallable, call_llm_sidecar, parse_natural_language_input
from planner.models import (
    AvailabilityWindow,
    DayPlanInput,
    FixedEvent,
    FocusType,
    ScheduleItem,
    ScheduleItemType,
    Task,
)
from planner.openai_oauth import (
    check_openai_oauth_proxy,
    find_existing_auth_file,
    start_codex_login,
    start_openai_oauth_proxy,
)


WEEKDAY_OFFSETS = {
    "월": 0,
    "화": 1,
    "수": 2,
    "목": 3,
    "금": 4,
    "토": 5,
    "일": 6,
}

PROJECT_ROOT = Path(__file__).resolve().parents[1]

OAUTH_REQUIRED_MESSAGE = (
    "OpenAI OAuth 로그인이 필요합니다. 화면 상단의 AI 미연결 버튼이나 "
    "시작 화면의 OpenAI 연결 버튼을 눌러 로그인하세요."
)


class OAuthRequiredError(RuntimeError):
    pass


def _require_openai_oauth() -> None:
    if not check_openai_oauth_proxy().connected:
        raise OAuthRequiredError(OAUTH_REQUIRED_MESSAGE)


def _http_sidecar(payload: dict[str, Any]) -> dict[str, Any]:
    return call_llm_sidecar(payload, timeout_seconds=8)


def openai_status_response() -> dict[str, Any]:
    status = check_openai_oauth_proxy()
    auth_file = find_existing_auth_file()
    return {
        "connected": status.connected,
        "message": status.message,
        "models": status.models,
        "authFileExists": auth_file is not None,
    }


def openai_connect_response() -> dict[str, Any]:
    status = check_openai_oauth_proxy()
    if status.connected:
        return {
            "connected": True,
            "action": "already_connected",
            "message": "OpenAI OAuth proxy가 이미 연결되어 있습니다.",
            "models": status.models,
        }

    auth_file = find_existing_auth_file()
    if auth_file is None:
        process = start_codex_login(cwd=PROJECT_ROOT)
        return {
            "connected": False,
            "action": "login_started",
            "pid": process.pid,
            "message": "OpenAI OAuth 로그인 페이지를 열었습니다. 로그인 후 다시 연결을 확인하세요.",
        }

    process = start_openai_oauth_proxy(cwd=PROJECT_ROOT)
    return {
        "connected": False,
        "action": "proxy_started",
        "pid": process.pid,
        "message": "OpenAI OAuth 세션을 찾았습니다. 로컬 proxy를 시작했습니다.",
    }


def _week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def _week_label(week_start: date) -> str:
    week_end = week_start + timedelta(days=6)
    return f"{week_start.strftime('%Y.%m.%d')} - {week_end.strftime('%m.%d')}"


def _minutes_from_time(value: time) -> int:
    return value.hour * 60 + value.minute


def _time_text_from_minutes(total_minutes: int) -> str:
    if total_minutes >= 24 * 60:
        return "24:00"
    clamped = max(0, min(total_minutes, 24 * 60 - 1))
    return f"{clamped // 60:02d}:{clamped % 60:02d}"


def _item_clock_text(plan_input: DayPlanInput, item: ScheduleItem, offset: int) -> str:
    return _time_text_from_minutes(_minutes_from_time(plan_input.day_start) + offset)


def _frontend_type(item: ScheduleItem) -> str | None:
    if item.type == ScheduleItemType.FIXED_EVENT:
        return "fixed"
    if item.type == ScheduleItemType.TASK:
        return "task"
    return None


def _priority_label(value: int | None) -> str | None:
    if value is None:
        return None
    if value >= 5:
        return "High"
    if value >= 3:
        return "Medium"
    return "Low"


def _validation_rows(state: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    validation = state.get("validation_result")
    if validation is not None:
        buffer_summary = validation.buffer_summary
        rows.append(
            {
                "label": "여유",
                "status": "warning" if buffer_summary.shortage_minutes else "ok",
                "detail": (
                    f"{buffer_summary.secured_minutes}/{buffer_summary.target_minutes}분"
                    if buffer_summary.target_minutes
                    else "확보됨"
                ),
            }
        )
        rows.extend(
            {
                "label": issue.code,
                "status": "warning",
                "detail": issue.message,
            }
            for issue in validation.issues
            if not issue.blocking
        )
    draft = state.get("draft_plan")
    unassigned = list(getattr(draft, "unassigned_tasks", []) or [])
    rows.extend(
        {
            "label": "미배치",
            "status": "warning",
            "detail": f"{item.task.title}: {item.reason}",
        }
        for item in unassigned
    )
    if not rows:
        rows.append({"label": "검증", "status": "ok", "detail": "문제 없음"})
    return rows


def _planner_state_to_frontend(
    *,
    state: dict[str, Any],
    plan_input: DayPlanInput,
    last_feedback: str | None = None,
) -> dict[str, Any]:
    draft = state.get("draft_plan")
    final_plan = state.get("final_plan")
    output_items = final_plan.schedule_items if final_plan else draft.schedule_items
    task_by_id = {task.id: task for task in plan_input.tasks}
    week_start = _week_start(plan_input.date)
    items: list[dict[str, Any]] = []

    for index, item in enumerate(output_items, start=1):
        frontend_type = _frontend_type(item)
        if frontend_type is None:
            continue
        item_date = plan_input.date + timedelta(days=item.day_offset)
        day_index = (item_date - week_start).days
        if day_index < 0 or day_index > 6:
            continue
        source_id = item.source_id or f"{item.type.value}-{index}"
        source_task = task_by_id.get(source_id)
        items.append(
            {
                "id": source_id,
                "type": frontend_type,
                "title": item.title,
                "dayIndex": day_index,
                "start": _item_clock_text(plan_input, item, item.start_offset),
                "end": _item_clock_text(plan_input, item, item.end_offset),
                "durationMinutes": item.duration_minutes,
                "note": item.reason,
                "priority": _priority_label(source_task.priority) if source_task else None,
            }
        )

    return {
        "weekStart": week_start.isoformat(),
        "weekLabel": _week_label(week_start),
        "reason": final_plan.explanation if final_plan else state.get("explanation", ""),
        "items": items,
        "validation": _validation_rows(state),
        "replanCount": state.get("replan_count", 0),
        "lastFeedback": last_feedback,
        "backend": {
            "planInput": plan_input.model_dump(mode="json"),
        },
    }


def _full_week_availability(day_start: time, day_end: time) -> list[AvailabilityWindow]:
    return [
        AvailabilityWindow(
            id=f"available-{day_offset}",
            day_offset=day_offset,
            start_time=day_start,
            end_time=day_end,
        )
        for day_offset in range(7)
    ]


def _parse_fixed_event(value: str, index: int) -> FixedEvent:
    match = re.search(
        r"([월화수목금토일])\s*(\d{1,2}):(\d{2})(?:\s*-\s*(\d{1,2}):(\d{2}))?\s*(.+)",
        value,
    )
    if match is None:
        return FixedEvent(
            id=f"fixed-{index}",
            title=value.strip() or f"고정 일정 {index}",
            day_offset=0,
            start_time=time(9, 0),
            end_time=time(10, 0),
        )
    day_offset = WEEKDAY_OFFSETS[match.group(1)]
    start_time = time(int(match.group(2)), int(match.group(3)))
    end_time = (
        time(int(match.group(4)), int(match.group(5)))
        if match.group(4) and match.group(5)
        else time((start_time.hour + 1) % 24, start_time.minute)
    )
    return FixedEvent(
        id=f"fixed-{index}",
        title=match.group(6).strip() or f"고정 일정 {index}",
        day_offset=day_offset,
        start_time=start_time,
        end_time=end_time,
    )


def _parse_task(value: str, index: int, plan_date: date) -> Task:
    duration_match = re.search(r"(\d+)\s*분", value)
    duration = int(duration_match.group(1)) if duration_match else 60
    priority = 5 if "High" in value else 3 if "Medium" in value else 2 if "Low" in value else 3
    title = re.sub(r"\d+\s*분", "", value)
    title = re.sub(r"\b(?:High|Medium|Low)\b", "", title).strip(" ·")
    return Task(
        id=f"task-{index}",
        title=title or f"작업 {index}",
        estimated_minutes=duration,
        priority=priority,
        start_date=plan_date,
        end_date=plan_date + timedelta(days=6),
        splittable=False,
        focus_type=FocusType.ANY,
    )


def _structured_plan_input(request: dict[str, Any], reference_date: date | None) -> DayPlanInput:
    plan_date = _week_start(reference_date or date.today())
    day_start = time(9, 0)
    day_end = time(23, 59)
    fixed_events = [
        _parse_fixed_event(value, index)
        for index, value in enumerate(request.get("fixedEvents") or [], start=1)
    ]
    tasks = [
        _parse_task(value, index, plan_date)
        for index, value in enumerate(request.get("tasks") or [], start=1)
    ]
    return DayPlanInput(
        date=plan_date,
        day_start=day_start,
        day_end=day_end,
        availability_windows=_full_week_availability(day_start, day_end),
        fixed_events=fixed_events,
        tasks=tasks,
        buffer_ratio=float(request.get("bufferRatio", 10)) / 100,
    )


def _plan_input_from_request(
    request: dict[str, Any],
    *,
    reference_date: date | None,
    sidecar: SidecarCallable | None,
) -> DayPlanInput:
    if request.get("mode") == "structured":
        return _structured_plan_input(request, reference_date)
    parser_kwargs: dict[str, Any] = {"reference_date": reference_date}
    if sidecar is not None:
        parser_kwargs["sidecar"] = sidecar
    else:
        _require_openai_oauth()
        parser_kwargs["sidecar"] = _http_sidecar
        parser_kwargs["max_retries"] = 1
    plan_input = parse_natural_language_input(str(request.get("text") or ""), **parser_kwargs)
    if "bufferRatio" in request:
        plan_input = plan_input.model_copy(
            update={"buffer_ratio": float(request["bufferRatio"]) / 100}
        )
    return plan_input


def create_plan_response(
    request: dict[str, Any],
    *,
    reference_date: date | None = None,
    sidecar: SidecarCallable | None = None,
) -> dict[str, Any]:
    plan_input = _plan_input_from_request(
        request,
        reference_date=reference_date,
        sidecar=sidecar,
    )
    state = build_planner_graph().invoke(
        {
            "parsed_input": plan_input,
            "approval_status": "pending",
        }
    )
    return _planner_state_to_frontend(state=state, plan_input=plan_input)


def _combined_replan_reason(request: dict[str, Any], *, previous_feedback: str = "") -> str:
    reason = str(request.get("reason") or "").strip()
    task_id = str(request.get("snoozeTaskId") or "").strip()
    if task_id:
        days = max(1, min(int(request.get("snoozeDays") or 1), 6))
        reason = "\n".join(
            part
            for part in [
                reason,
                f"snooze task_id={task_id} days={days}",
            ]
            if part
        )
    if previous_feedback and previous_feedback not in reason:
        reason = "\n".join(part for part in [previous_feedback, reason] if part)
    return reason


def replan_response(
    request: dict[str, Any],
    *,
    sidecar: SidecarCallable | None = None,
) -> dict[str, Any]:
    draft = request.get("draft") or {}
    backend = draft.get("backend") or {}
    plan_input = DayPlanInput.model_validate(backend.get("planInput"))
    reason = _combined_replan_reason(
        request,
        previous_feedback=str(draft.get("lastFeedback") or "").strip(),
    )
    if sidecar is None:
        _require_openai_oauth()
    use_llm_replan = sidecar is None
    state = build_planner_graph().invoke(
        {
            "parsed_input": plan_input,
            "approval_status": "rejected",
            "rejection_reason": reason,
            "conversation": request.get("conversation") or [],
            "frontend_schedule_items": draft.get("items") or [],
            "replan_count": int(draft.get("replanCount") or 0),
            "use_llm_replan": use_llm_replan,
        }
    )
    constraints = state.get("replan_constraints")
    if constraints and constraints.assistant_message and _is_message_only_replan(constraints):
        return {"agentMessage": constraints.assistant_message}
    return _planner_state_to_frontend(
        state=state,
        plan_input=state.get("parsed_input", plan_input),
        last_feedback=reason,
    )


def _is_message_only_replan(constraints: Any) -> bool:
    return not any(
        [
            constraints.buffer_ratio_delta,
            constraints.excluded_task_ids,
            constraints.excluded_fixed_event_ids,
            constraints.additional_tasks,
            constraints.additional_fixed_events,
            constraints.task_updates,
            constraints.fixed_event_updates,
            constraints.availability_overrides,
            constraints.task_day_offsets,
            constraints.preferred_windows,
            constraints.duration_multipliers,
            constraints.fixed_event_buffer_after,
            constraints.snoozed_task_days,
        ]
    )
