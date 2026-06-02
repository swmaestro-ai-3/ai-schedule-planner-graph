from __future__ import annotations

import os
from html import escape
from datetime import date, time, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import streamlit as st
from dotenv import load_dotenv

from planner.google_calendar import (
    GoogleOAuthConfig,
    build_authorization_url,
    build_calendar_service,
    create_flow,
    exchange_code_for_credentials,
    export_schedule_items,
    import_fixed_events_for_day,
    load_credentials,
    refresh_credentials,
    save_credentials,
)
from planner.graph import build_planner_graph
from planner.llm_parser import LLMParserError, parse_natural_language_input
from planner.models import (
    DayPlanInput,
    FixedEvent,
    FocusType,
    ScheduleItem,
    ScheduleItemType,
    Task,
    UnassignedTask,
    ValidationIssue,
)
from planner.openai_oauth import (
    OpenAIOAuthStatus,
    check_openai_oauth_proxy,
    find_existing_auth_file,
    start_codex_login,
    start_openai_oauth_proxy,
)


PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")


def default_fixed_event_rows() -> list[dict[str, Any]]:
    return [
        {
            "id": "class-1",
            "title": "전공 수업",
            "start_time": time(10, 0),
            "end_time": time(12, 0),
            "category": "class",
        }
    ]


def default_task_rows() -> list[dict[str, Any]]:
    return [
        {
            "id": "task-1",
            "title": "알고리즘 과제",
            "estimated_minutes": 120,
            "priority": 5,
            "splittable": True,
            "focus_type": "deep",
        },
        {
            "id": "task-2",
            "title": "영어 단어 암기",
            "estimated_minutes": 30,
            "priority": 2,
            "splittable": True,
            "focus_type": "light",
        },
    ]


def integration_button_labels() -> list[str]:
    return ["Google Calendar 연동", "OpenAI OAuth 연동"]


def should_show_openai_oauth_button(status: OpenAIOAuthStatus) -> bool:
    return not status.connected


def structured_input_section_titles() -> list[str]:
    return ["계획 기준", "고정 일정", "배치할 작업"]


def structured_input_action_labels() -> list[str]:
    return ["일정안 생성"]


def structured_input_editor_column_order() -> dict[str, tuple[str, ...]]:
    return {
        "fixed_events": ("title", "start_time", "end_time", "category"),
        "tasks": ("title", "estimated_minutes", "priority", "focus_type", "splittable"),
    }


def structured_input_summary_cards(
    *,
    plan_date: date,
    day_start: time,
    day_end: time,
    buffer_ratio: float,
    fixed_event_rows: list[dict[str, Any]],
    task_rows: list[dict[str, Any]],
) -> list[dict[str, str]]:
    fixed_event_count = sum(1 for row in fixed_event_rows if row.get("title"))
    task_count = sum(1 for row in task_rows if row.get("title"))
    return [
        {"label": "날짜", "value": plan_date.strftime("%Y/%m/%d")},
        {
            "label": "운영 시간",
            "value": f"{day_start.strftime('%H:%M')}-{day_end.strftime('%H:%M')}",
        },
        {"label": "여유", "value": f"{buffer_ratio * 100:.0f}%"},
        {"label": "입력", "value": f"고정 {fixed_event_count}개 / 작업 {task_count}개"},
    ]


def fixed_event_editor_column_labels() -> dict[str, str]:
    return {
        "id": "ID",
        "title": "일정명",
        "start_time": "시작",
        "end_time": "종료",
        "category": "분류",
    }


def task_editor_column_labels() -> dict[str, str]:
    return {
        "id": "ID",
        "title": "작업명",
        "estimated_minutes": "소요(분)",
        "priority": "중요도",
        "splittable": "분할 가능",
        "focus_type": "집중도",
    }


def fixed_event_editor_column_config() -> dict[str, Any]:
    labels = fixed_event_editor_column_labels()
    return {
        "id": st.column_config.TextColumn(labels["id"], width="small"),
        "title": st.column_config.TextColumn(labels["title"], width="medium", required=True),
        "start_time": st.column_config.TimeColumn(labels["start_time"], format="HH:mm"),
        "end_time": st.column_config.TimeColumn(labels["end_time"], format="HH:mm"),
        "category": st.column_config.TextColumn(labels["category"], width="small"),
    }


def task_editor_column_config() -> dict[str, Any]:
    labels = task_editor_column_labels()
    return {
        "id": st.column_config.TextColumn(labels["id"], width="small"),
        "title": st.column_config.TextColumn(labels["title"], width="medium", required=True),
        "estimated_minutes": st.column_config.NumberColumn(
            labels["estimated_minutes"],
            min_value=1,
            step=15,
            width="small",
        ),
        "priority": st.column_config.NumberColumn(
            labels["priority"],
            min_value=1,
            max_value=5,
            step=1,
            width="small",
        ),
        "splittable": st.column_config.CheckboxColumn(labels["splittable"], width="small"),
        "focus_type": st.column_config.SelectboxColumn(
            labels["focus_type"],
            options=["deep", "light", "any"],
            width="small",
            format_func=lambda value: {
                "deep": "깊은 집중",
                "light": "가벼운 작업",
                "any": "상관없음",
            }.get(value, value),
        ),
    }


def mvp_sidebar_integration_labels(*, openai_status: OpenAIOAuthStatus) -> list[str]:
    labels: list[str] = []
    if should_show_openai_oauth_button(openai_status):
        labels.append(integration_button_labels()[1])
    return labels


def build_structured_input(
    *,
    plan_date: date,
    day_start: time,
    day_end: time,
    buffer_ratio: float,
    fixed_event_rows: list[dict[str, Any]],
    task_rows: list[dict[str, Any]],
) -> DayPlanInput:
    fixed_events = [
        FixedEvent(
            id=str(row.get("id") or f"event-{index}"),
            title=str(row.get("title") or "제목 없는 일정"),
            start_time=row["start_time"],
            end_time=row["end_time"],
            category=row.get("category") or None,
        )
        for index, row in enumerate(fixed_event_rows, start=1)
        if row.get("start_time") and row.get("end_time")
    ]
    tasks = [
        Task(
            id=str(row.get("id") or f"task-{index}"),
            title=str(row.get("title") or "제목 없는 작업"),
            estimated_minutes=int(row["estimated_minutes"])
            if row.get("estimated_minutes") not in (None, "")
            else None,
            priority=int(row.get("priority") or 3),
            splittable=bool(row.get("splittable", True)),
            focus_type=FocusType(row.get("focus_type") or FocusType.ANY),
        )
        for index, row in enumerate(task_rows, start=1)
        if row.get("title")
    ]
    return DayPlanInput(
        date=plan_date,
        day_start=day_start,
        day_end=day_end,
        fixed_events=fixed_events,
        tasks=tasks,
        buffer_ratio=buffer_ratio,
    )


def fixed_events_to_editor_rows(events: list[FixedEvent]) -> list[dict[str, Any]]:
    return [
        {
            "id": event.id,
            "title": event.title,
            "start_time": event.start_time,
            "end_time": event.end_time,
            "category": event.category,
        }
        for event in events
    ]


def merge_fixed_event_rows(
    existing_rows: list[dict[str, Any]],
    imported_events: list[FixedEvent],
) -> list[dict[str, Any]]:
    rows = [dict(row) for row in existing_rows]
    seen_ids = {str(row.get("id")) for row in rows if row.get("id")}
    for row in fixed_events_to_editor_rows(imported_events):
        if row["id"] in seen_ids:
            continue
        rows.append(row)
        seen_ids.add(row["id"])
    return rows


def exportable_schedule_items(planner_state: dict[str, Any]) -> list[ScheduleItem]:
    final_plan = planner_state.get("final_plan")
    if final_plan is None:
        return []
    return [
        item
        for item in final_plan.schedule_items
        if item.type == ScheduleItemType.TASK
    ]


def build_google_oauth_config(
    *,
    env: dict[str, str] | None = None,
    cwd: str | Path = PROJECT_ROOT,
) -> GoogleOAuthConfig | None:
    values = env if env is not None else os.environ
    client_id = values.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = values.get("GOOGLE_OAUTH_CLIENT_SECRET")
    redirect_uri = values.get("GOOGLE_OAUTH_REDIRECT_URI")
    if not client_id or not client_secret or not redirect_uri:
        return None

    token_file = Path(values.get("GOOGLE_TOKEN_FILE") or ".google-calendar-token.json")
    if not token_file.is_absolute():
        token_file = Path(cwd) / token_file

    return GoogleOAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        token_file=token_file,
    )


def _offset_to_time(day_start: time, offset_minutes: int) -> str:
    base = timedelta(hours=day_start.hour, minutes=day_start.minute)
    current = base + timedelta(minutes=offset_minutes)
    total_minutes = int(current.total_seconds() // 60)
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def schedule_items_to_rows(
    items: list[ScheduleItem],
    *,
    day_start: time,
) -> list[dict[str, str]]:
    return [
        {
            "time": (
                f"{_offset_to_time(day_start, item.start_offset)}"
                f"~{_offset_to_time(day_start, item.end_offset)}"
            ),
            "type": item.type.value,
            "title": item.title,
            "reason": item.reason,
        }
        for item in items
    ]


def schedule_items_to_calendar_blocks(
    items: list[ScheduleItem],
    *,
    day_start: time,
    day_end: time,
) -> list[dict[str, Any]]:
    day_length = int(
        (
            timedelta(hours=day_end.hour, minutes=day_end.minute)
            - timedelta(hours=day_start.hour, minutes=day_start.minute)
        ).total_seconds()
        // 60
    )
    blocks: list[dict[str, Any]] = []
    for item in items:
        start = max(0, min(item.start_offset, day_length))
        end = max(start, min(item.end_offset, day_length))
        blocks.append(
            {
                "top": start,
                "height": max(8, end - start),
                "time": (
                    f"{_offset_to_time(day_start, item.start_offset)}"
                    f"~{_offset_to_time(day_start, item.end_offset)}"
                ),
                "type": item.type.value,
                "title": item.title,
                "reason": item.reason,
            }
        )
    return blocks


def validation_panel_rows(state: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    validation_result = state.get("validation_result")
    buffer_summary = getattr(validation_result, "buffer_summary", None)
    if buffer_summary and buffer_summary.target_minutes:
        status = "부족" if buffer_summary.shortage_minutes else "충분"
        rows.append(
            {
                "check": "buffer",
                "status": status,
                "detail": (
                    f"목표 {buffer_summary.target_minutes}분 / "
                    f"확보 {buffer_summary.secured_minutes}분"
                ),
            }
        )

    rows.extend(
        {
            "check": "warning",
            "status": "확인 필요",
            "detail": warning.message,
        }
        for warning in state.get("warnings", [])
    )
    rows.extend(
        {
            "check": "unassigned",
            "status": "미배치",
            "detail": f"{item.task.title}: {item.reason}",
        }
        for item in state.get("unassigned_tasks", [])
    )
    if not rows:
        rows.append({"check": "overall", "status": "양호", "detail": "검증 경고 없음"})
    return rows


def schedule_change_summary(
    previous_items: list[ScheduleItem],
    current_items: list[ScheduleItem],
    *,
    day_start: time,
) -> list[dict[str, str]]:
    previous_by_key = {
        item.source_id or item.title: item
        for item in previous_items
        if item.type == ScheduleItemType.TASK
    }
    rows: list[dict[str, str]] = []
    for item in current_items:
        if item.type != ScheduleItemType.TASK:
            continue
        previous = previous_by_key.get(item.source_id or item.title)
        if previous is None:
            continue
        if (
            previous.start_offset == item.start_offset
            and previous.end_offset == item.end_offset
        ):
            continue
        rows.append(
            {
                "task": item.title,
                "before": (
                    f"{_offset_to_time(day_start, previous.start_offset)}"
                    f"~{_offset_to_time(day_start, previous.end_offset)}"
                ),
                "after": (
                    f"{_offset_to_time(day_start, item.start_offset)}"
                    f"~{_offset_to_time(day_start, item.end_offset)}"
                ),
            }
        )
    return rows


def warning_summary_rows(
    *,
    warnings: list[ValidationIssue],
    unassigned_tasks: list[UnassignedTask],
) -> list[dict[str, str]]:
    rows = [
        {"code": warning.code, "message": warning.message}
        for warning in warnings
    ]
    rows.extend(
        {
            "code": item.reason_code.value,
            "message": f"{item.task.title}: {item.reason}",
        }
        for item in unassigned_tasks
    )
    return rows


def run_planner(plan_input: DayPlanInput, approval_status: str = "pending"):
    graph = build_planner_graph()
    return graph.invoke(
        {
            "parsed_input": plan_input,
            "approval_status": approval_status,
        }
    )


def render_result(state: dict[str, Any], plan_input: DayPlanInput) -> None:
    draft = state.get("draft_plan")
    final_plan = state.get("final_plan")
    output_items = final_plan.schedule_items if final_plan else draft.schedule_items
    warnings = final_plan.warnings if final_plan else state.get("warnings", [])
    unassigned = final_plan.unassigned_tasks if final_plan else draft.unassigned_tasks

    st.subheader("일정표")
    st.dataframe(
        schedule_items_to_rows(output_items, day_start=plan_input.day_start),
        width="stretch",
        hide_index=True,
    )

    summary_rows = warning_summary_rows(
        warnings=warnings,
        unassigned_tasks=unassigned,
    )
    if summary_rows:
        st.subheader("경고 및 미배치")
        st.dataframe(summary_rows, width="stretch", hide_index=True)

    st.subheader("판단 근거")
    st.write(final_plan.explanation if final_plan else state.get("explanation", ""))


def _calendar_hours(day_start: time, day_end: time) -> list[tuple[int, str]]:
    start_minutes = day_start.hour * 60 + day_start.minute
    end_minutes = day_end.hour * 60 + day_end.minute
    return [
        (minute - start_minutes, f"{minute // 60:02d}:00")
        for minute in range(start_minutes, end_minutes + 1, 60)
    ]


def _calendar_block_class(item_type: str) -> str:
    return {
        "fixed_event": "calendar-block-fixed",
        "task": "calendar-block-task",
        "buffer": "calendar-block-buffer",
        "free": "calendar-block-free",
    }.get(item_type, "calendar-block-free")


def render_calendar_view(items: list[ScheduleItem], plan_input: DayPlanInput) -> None:
    blocks = schedule_items_to_calendar_blocks(
        items,
        day_start=plan_input.day_start,
        day_end=plan_input.day_end,
    )
    day_length = max(
        60,
        int(
            (
                timedelta(hours=plan_input.day_end.hour, minutes=plan_input.day_end.minute)
                - timedelta(hours=plan_input.day_start.hour, minutes=plan_input.day_start.minute)
            ).total_seconds()
            // 60
        ),
    )
    scale = 1.2
    timeline_height = int(day_length * scale)
    hour_rows = "\n".join(
        f'<div class="calendar-hour" style="top:{offset * scale:.1f}px">{label}</div>'
        for offset, label in _calendar_hours(plan_input.day_start, plan_input.day_end)
    )
    block_html = "\n".join(
        (
            f'<div class="calendar-block {_calendar_block_class(block["type"])}" '
            f'style="top:{block["top"] * scale:.1f}px;'
            f'height:{max(22, block["height"] * scale):.1f}px">'
            f'<div class="calendar-block-time">{escape(block["time"])}</div>'
            f'<div class="calendar-block-title">{escape(block["title"])}</div>'
            f'<div class="calendar-block-reason">{escape(block["reason"])}</div>'
            "</div>"
        )
        for block in blocks
    )
    st.markdown(
        f"""
<style>
.calendar-shell {{
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr);
  gap: 12px;
  border: 1px solid #d7dde8;
  border-radius: 8px;
  background: #f8fafc;
  padding: 14px;
  margin: 8px 0 18px;
}}
.calendar-axis {{
  position: relative;
  height: {timeline_height}px;
  color: #64748b;
  font-size: 12px;
}}
.calendar-hour {{
  position: absolute;
  right: 0;
  transform: translateY(-8px);
}}
.calendar-lane {{
  position: relative;
  height: {timeline_height}px;
  border-left: 1px solid #cbd5e1;
  background: repeating-linear-gradient(
    to bottom,
    #ffffff 0,
    #ffffff 71px,
    #eef2f7 72px
  );
}}
.calendar-block {{
  position: absolute;
  left: 10px;
  right: 10px;
  overflow: hidden;
  border-radius: 6px;
  border: 1px solid rgba(15, 23, 42, 0.12);
  padding: 6px 8px;
  box-sizing: border-box;
}}
.calendar-block-fixed {{ background: #dbeafe; border-color: #93c5fd; }}
.calendar-block-task {{ background: #dcfce7; border-color: #86efac; }}
.calendar-block-buffer {{ background: #fef3c7; border-color: #fcd34d; }}
.calendar-block-free {{ background: #f1f5f9; border-color: #cbd5e1; }}
.calendar-block-time {{
  color: #475569;
  font-size: 11px;
  line-height: 1.2;
}}
.calendar-block-title {{
  color: #0f172a;
  font-size: 13px;
  font-weight: 650;
  line-height: 1.2;
  margin-top: 1px;
}}
.calendar-block-reason {{
  color: #475569;
  font-size: 11px;
  line-height: 1.2;
  margin-top: 2px;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}}
</style>
<div class="calendar-shell">
  <div class="calendar-axis">{hour_rows}</div>
  <div class="calendar-lane">{block_html}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def _current_output_items(state: dict[str, Any]) -> list[ScheduleItem]:
    final_plan = state.get("final_plan")
    if final_plan:
        return final_plan.schedule_items
    draft = state.get("draft_plan")
    return draft.schedule_items if draft else []


def render_ai_proposal_section(state: dict[str, Any], plan_input: DayPlanInput) -> None:
    st.markdown("### 2. AI 배치 제안")
    output_items = _current_output_items(state)
    render_calendar_view(output_items, plan_input)
    st.dataframe(
        schedule_items_to_rows(output_items, day_start=plan_input.day_start),
        width="stretch",
        hide_index=True,
    )
    st.markdown("#### 판단 근거")
    final_plan = state.get("final_plan")
    st.write(final_plan.explanation if final_plan else state.get("explanation", ""))


def render_user_feedback_section(state: dict[str, Any], plan_input: DayPlanInput) -> None:
    if state.get("final_plan"):
        return
    st.markdown("### 3. 사용자 검증 및 피드백")
    st.dataframe(
        validation_panel_rows(state),
        width="stretch",
        hide_index=True,
    )
    approve_col, feedback_col = st.columns(2)
    if approve_col.button("승인"):
        st.session_state["planner_state"] = run_planner(
            plan_input,
            approval_status="approved",
        )
        st.rerun()

    rejection_reason = feedback_col.text_area("피드백", key="rejection_reason")
    if feedback_col.button("피드백 반영해 재배치") and rejection_reason:
        previous_items = _current_output_items(state)
        graph = build_planner_graph()
        next_state = graph.invoke(
            {
                "parsed_input": plan_input,
                "approval_status": "rejected",
                "rejection_reason": rejection_reason,
                "replan_count": state.get("replan_count", 0),
            }
        )
        st.session_state["previous_schedule_items"] = previous_items
        st.session_state["last_feedback"] = rejection_reason
        st.session_state["planner_state"] = next_state
        st.rerun()


def render_replan_section(state: dict[str, Any], plan_input: DayPlanInput) -> None:
    if state.get("final_plan"):
        st.markdown("### 4. AI 재배치 / 확정")
        st.success("최종 일정으로 확정됨")
        return
    if not st.session_state.get("last_feedback"):
        return
    st.markdown("### 4. AI 재배치 / 확정")
    st.caption(f"반영된 피드백: {st.session_state['last_feedback']}")
    st.caption(f"재계획 횟수: {state.get('replan_count', 0)}")
    change_rows = schedule_change_summary(
        st.session_state.get("previous_schedule_items", []),
        _current_output_items(state),
        day_start=plan_input.day_start,
    )
    if change_rows:
        st.dataframe(change_rows, width="stretch", hide_index=True)
    else:
        st.info("변경된 task 시간 없음")


def render_planner_workspace(state: dict[str, Any], plan_input: DayPlanInput) -> None:
    render_ai_proposal_section(state, plan_input)
    render_user_feedback_section(state, plan_input)
    render_replan_section(state, plan_input)


def reset_replan_session_state() -> None:
    st.session_state.pop("previous_schedule_items", None)
    st.session_state.pop("last_feedback", None)
    st.session_state.pop("rejection_reason", None)


def submit_structured_plan(
    *,
    plan_date: date,
    day_start: time,
    day_end: time,
    buffer_ratio: float,
    fixed_event_rows: list[dict[str, Any]],
    task_rows: list[dict[str, Any]],
) -> None:
    plan_input = build_structured_input(
        plan_date=plan_date,
        day_start=day_start,
        day_end=day_end,
        buffer_ratio=buffer_ratio,
        fixed_event_rows=list(fixed_event_rows),
        task_rows=list(task_rows),
    )
    reset_replan_session_state()
    st.session_state["plan_input"] = plan_input
    st.session_state["planner_state"] = run_planner(plan_input)


def _query_value(name: str) -> str | None:
    value = st.query_params.get(name)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _authorization_response(config: GoogleOAuthConfig) -> str:
    params = dict(st.query_params)
    return f"{config.redirect_uri}?{urlencode(params, doseq=True)}"


def _load_google_calendar_service(config: GoogleOAuthConfig):
    credentials = load_credentials(config.token_file)
    if credentials is None:
        return None
    credentials = refresh_credentials(credentials)
    save_credentials(credentials, config.token_file)
    if not credentials.valid:
        return None
    return build_calendar_service(credentials)


def _consume_google_oauth_callback(config: GoogleOAuthConfig) -> None:
    code = _query_value("code")
    if not code:
        return

    expected_state = st.session_state.get("google_oauth_state")
    incoming_state = _query_value("state")
    if expected_state and incoming_state != expected_state:
        st.sidebar.error("Google OAuth state mismatch.")
        return

    try:
        exchange_code_for_credentials(
            config,
            authorization_response=_authorization_response(config),
        )
    except Exception as exc:
        st.sidebar.error(f"Google Calendar 로그인 실패: {exc}")
        return

    st.session_state.pop("google_auth_url", None)
    st.session_state.pop("google_oauth_state", None)
    st.query_params.clear()
    st.sidebar.success("Google Calendar 로그인 완료")


def render_google_calendar_controls() -> None:
    st.sidebar.subheader("Google Calendar")
    config = build_google_oauth_config()
    google_label = integration_button_labels()[0]
    if config is None:
        st.sidebar.caption("GOOGLE_OAUTH_CLIENT_ID/SECRET/REDIRECT_URI 필요")
        st.sidebar.button(google_label, disabled=True)
        return

    _consume_google_oauth_callback(config)
    token_ready = config.token_file.exists()
    st.sidebar.caption("연결됨" if token_ready else "로그인 필요")

    import_date = st.sidebar.date_input(
        "Calendar 가져올 날짜",
        value=st.session_state.get("selected_plan_date", date.today()),
        key="google_calendar_import_date",
    )
    if st.sidebar.button(google_label):
        try:
            if not token_ready:
                auth_url, state = build_authorization_url(
                    create_flow(config),
                    redirect_uri=config.redirect_uri,
                )
                st.session_state["google_auth_url"] = auth_url
                st.session_state["google_oauth_state"] = state
                st.sidebar.info("Google 로그인 링크를 열어 인증을 완료하세요.")
                return

            service = _load_google_calendar_service(config)
        except Exception as exc:
            st.sidebar.error(f"Google Calendar 연동 실패: {exc}")
            return
        if service is None:
            st.sidebar.warning("Google Calendar 로그인이 필요합니다.")
            return

        imported_events = import_fixed_events_for_day(
            service,
            target_date=import_date,
            timezone="Asia/Seoul",
        )
        current_rows = st.session_state.get("fixed_event_rows") or default_fixed_event_rows()
        st.session_state["fixed_event_rows"] = merge_fixed_event_rows(
            list(current_rows),
            imported_events,
        )
        st.session_state["fixed_events_editor_version"] = (
            st.session_state.get("fixed_events_editor_version", 0) + 1
        )

        plan_input = st.session_state.get("plan_input")
        planner_state = st.session_state.get("planner_state") or {}
        items = exportable_schedule_items(planner_state)
        exported: list[dict[str, Any]] = []
        if plan_input and items:
            try:
                exported = export_schedule_items(
                    service,
                    items,
                    plan_date=plan_input.date,
                    day_start=plan_input.day_start,
                    timezone=plan_input.timezone,
                )
            except Exception as exc:
                st.sidebar.error(f"Google Calendar 내보내기 실패: {exc}")
                return

        st.sidebar.success(
            f"{len(imported_events)}개 일정 불러옴, {len(exported)}개 작업 내보냄"
        )

    if st.session_state.get("google_auth_url"):
        st.sidebar.markdown(
            f"[Google 로그인 페이지 열기]({st.session_state['google_auth_url']})"
        )


def render_openai_oauth_controls() -> None:
    st.sidebar.subheader("OpenAI OAuth")
    auth_file = find_existing_auth_file()
    status = check_openai_oauth_proxy()
    if status.connected:
        suffix = f" ({', '.join(status.models[:3])})" if status.models else ""
        st.sidebar.caption(f"연결됨{suffix}")
    else:
        st.sidebar.caption("auth.json 감지됨" if auth_file else "auth.json 없음")

    labels = mvp_sidebar_integration_labels(openai_status=status)
    if not labels:
        return

    openai_label = labels[0]

    if st.sidebar.button(openai_label):
        if not auth_file:
            try:
                process = start_codex_login(cwd=PROJECT_ROOT)
            except Exception as exc:
                st.sidebar.error(f"OpenAI 로그인 시작 실패: {exc}")
            else:
                st.session_state["openai_login_pid"] = process.pid
                st.sidebar.success(f"로그인 프로세스 시작: {process.pid}")
            return

        try:
            process = start_openai_oauth_proxy(cwd=PROJECT_ROOT)
        except Exception as exc:
            st.sidebar.error(f"OpenAI proxy 시작 실패: {exc}")
        else:
            st.session_state["openai_proxy_pid"] = process.pid
            st.sidebar.success(f"proxy 프로세스 시작: {process.pid}")


def render_auth_sidebar() -> None:
    st.sidebar.header("연동")
    render_openai_oauth_controls()


def render_structured_input_styles() -> None:
    st.markdown(
        """
<style>
.structured-input-intro {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 14px 16px;
  margin: 6px 0 18px;
  background: #ffffff;
}
.structured-input-intro-title {
  font-size: 1rem;
  font-weight: 700;
  color: #1f2937;
  margin-bottom: 4px;
}
.structured-input-intro-copy {
  color: #6b7280;
  font-size: 0.9rem;
  line-height: 1.45;
}
.structured-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  margin: 12px 0 18px;
  background: #ffffff;
}
.structured-summary-item {
  padding: 10px 12px;
  border-right: 1px solid #e5e7eb;
}
.structured-summary-item:last-child {
  border-right: 0;
}
.structured-summary-label {
  color: #6b7280;
  font-size: 0.76rem;
  margin-bottom: 2px;
}
.structured-summary-value {
  color: #111827;
  font-size: 0.95rem;
  font-weight: 700;
}
.structured-section-header {
  margin: 18px 0 8px;
}
.structured-section-title {
  color: #111827;
  font-size: 1rem;
  font-weight: 700;
}
.structured-section-copy {
  color: #6b7280;
  font-size: 0.86rem;
  margin-top: 2px;
}
.structured-submit-note {
  color: #6b7280;
  font-size: 0.86rem;
  line-height: 1.45;
  padding-top: 4px;
}
@media (max-width: 760px) {
  .structured-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .structured-summary-item:nth-child(2) {
    border-right: 0;
  }
}
</style>
""",
        unsafe_allow_html=True,
    )


def render_structured_summary_cards(cards: list[dict[str, str]]) -> None:
    items = "".join(
        f"""
<div class="structured-summary-item">
  <div class="structured-summary-label">{escape(card["label"])}</div>
  <div class="structured-summary-value">{escape(card["value"])}</div>
</div>
"""
        for card in cards
    )
    st.markdown(f'<div class="structured-summary">{items}</div>', unsafe_allow_html=True)


def render_structured_section_header(title: str, copy: str) -> None:
    st.markdown(
        f"""
<div class="structured-section-header">
  <div class="structured-section-title">{escape(title)}</div>
  <div class="structured-section-copy">{escape(copy)}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_structured_tab() -> None:
    settings_title, fixed_title, task_title = structured_input_section_titles()
    primary_action_label = structured_input_action_labels()[0]
    column_order = structured_input_editor_column_order()

    render_structured_input_styles()
    st.markdown(
        """
<div class="structured-input-intro">
  <div class="structured-input-intro-title">구조화 입력</div>
  <div class="structured-input-intro-copy">
    하루의 기준 시간, 이미 정해진 일정, 배치할 작업만 직접 수정합니다.
    AI는 고정 일정을 건드리지 않고 남는 시간에 작업을 배치합니다.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    render_structured_section_header(
        settings_title,
        "일정을 배치할 날짜와 하루의 시작/종료, 확보할 여유 시간을 정합니다.",
    )
    settings_cols = st.columns([1.15, 1.0, 1.0, 1.35])
    plan_date = settings_cols[0].date_input("날짜", value=date(2026, 6, 3))
    st.session_state["selected_plan_date"] = plan_date
    day_start = settings_cols[1].time_input("하루 시작", value=time(9, 0))
    day_end = settings_cols[2].time_input("하루 종료", value=time(23, 0))
    buffer_ratio = settings_cols[3].slider("여유 비율", 0.0, 0.5, 0.1, 0.05)

    if "fixed_event_rows" not in st.session_state:
        st.session_state["fixed_event_rows"] = default_fixed_event_rows()
    if "task_rows" not in st.session_state:
        st.session_state["task_rows"] = default_task_rows()

    render_structured_summary_cards(
        structured_input_summary_cards(
            plan_date=plan_date,
            day_start=day_start,
            day_end=day_end,
            buffer_ratio=buffer_ratio,
            fixed_event_rows=list(st.session_state["fixed_event_rows"]),
            task_rows=list(st.session_state["task_rows"]),
        )
    )
    submit_cols = st.columns([0.62, 0.38])
    submit_cols[0].markdown(
        '<div class="structured-submit-note">입력값을 검토한 뒤 AI 배치 제안을 생성합니다.</div>',
        unsafe_allow_html=True,
    )
    if submit_cols[1].button(
        primary_action_label,
        type="primary",
        key="structured_generate",
        use_container_width=True,
    ):
        submit_structured_plan(
            plan_date=plan_date,
            day_start=day_start,
            day_end=day_end,
            buffer_ratio=buffer_ratio,
            fixed_event_rows=list(st.session_state["fixed_event_rows"]),
            task_rows=list(st.session_state["task_rows"]),
        )

    render_structured_section_header(
        fixed_title,
        "수업, 회의, 약속처럼 시작과 종료가 정해진 일정을 입력합니다.",
    )
    fixed_event_rows = st.data_editor(
        st.session_state["fixed_event_rows"],
        column_config=fixed_event_editor_column_config(),
        column_order=column_order["fixed_events"],
        hide_index=True,
        num_rows="dynamic",
        width="stretch",
        key=f"fixed_events_{st.session_state.get('fixed_events_editor_version', 0)}",
    )
    st.session_state["fixed_event_rows"] = list(fixed_event_rows)

    render_structured_section_header(
        task_title,
        "AI가 빈 시간에 배치해야 하는 작업과 소요 시간, 중요도, 집중도를 입력합니다.",
    )
    task_rows = st.data_editor(
        st.session_state["task_rows"],
        column_config=task_editor_column_config(),
        column_order=column_order["tasks"],
        hide_index=True,
        num_rows="dynamic",
        width="stretch",
        key="tasks",
    )
    st.session_state["task_rows"] = list(task_rows)


def render_natural_language_tab() -> None:
    raw_input = st.text_area("자연어 일정 입력", height=160)
    if st.button("자연어 입력 구조화"):
        try:
            plan_input = parse_natural_language_input(raw_input)
        except LLMParserError as exc:
            st.error(str(exc))
            return
        reset_replan_session_state()
        st.session_state["plan_input"] = plan_input
        st.session_state["planner_state"] = run_planner(plan_input)


def main() -> None:
    st.set_page_config(
        page_title="AI Schedule Planner Graph",
        page_icon="calendar",
        layout="wide",
    )
    st.title("AI Schedule Planner Graph")
    render_auth_sidebar()
    st.markdown("### 1. 사용자 입력")
    natural_tab, structured_tab = st.tabs(["자연어 입력", "구조화 입력"])
    with natural_tab:
        render_natural_language_tab()
    with structured_tab:
        render_structured_tab()
    if st.session_state.get("planner_state") and st.session_state.get("plan_input"):
        render_planner_workspace(
            st.session_state["planner_state"],
            st.session_state["plan_input"],
        )


if __name__ == "__main__":
    main()
