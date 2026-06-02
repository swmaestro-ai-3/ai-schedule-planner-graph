from __future__ import annotations

import os
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

    if not should_show_openai_oauth_button(status):
        return

    openai_label = integration_button_labels()[1]

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
    render_google_calendar_controls()
    render_openai_oauth_controls()


def render_structured_tab() -> None:
    plan_date = st.date_input("날짜", value=date(2026, 6, 3))
    st.session_state["selected_plan_date"] = plan_date
    left, middle, right = st.columns(3)
    day_start = left.time_input("하루 시작", value=time(9, 0))
    day_end = middle.time_input("하루 종료", value=time(23, 0))
    buffer_ratio = right.slider("Buffer ratio", 0.0, 0.5, 0.1, 0.05)

    if "fixed_event_rows" not in st.session_state:
        st.session_state["fixed_event_rows"] = default_fixed_event_rows()
    if "task_rows" not in st.session_state:
        st.session_state["task_rows"] = default_task_rows()

    fixed_event_rows = st.data_editor(
        st.session_state["fixed_event_rows"],
        num_rows="dynamic",
        width="stretch",
        key=f"fixed_events_{st.session_state.get('fixed_events_editor_version', 0)}",
    )
    st.session_state["fixed_event_rows"] = list(fixed_event_rows)

    task_rows = st.data_editor(
        st.session_state["task_rows"],
        num_rows="dynamic",
        width="stretch",
        key="tasks",
    )
    st.session_state["task_rows"] = list(task_rows)

    if st.button("일정안 생성", type="primary"):
        plan_input = build_structured_input(
            plan_date=plan_date,
            day_start=day_start,
            day_end=day_end,
            buffer_ratio=buffer_ratio,
            fixed_event_rows=list(fixed_event_rows),
            task_rows=list(task_rows),
        )
        st.session_state["plan_input"] = plan_input
        st.session_state["planner_state"] = run_planner(plan_input)

    if st.session_state.get("planner_state") and st.session_state.get("plan_input"):
        render_result(st.session_state["planner_state"], st.session_state["plan_input"])
        approve_col, reject_col = st.columns(2)
        if approve_col.button("승인"):
            st.session_state["planner_state"] = run_planner(
                st.session_state["plan_input"],
                approval_status="approved",
            )
            render_result(
                st.session_state["planner_state"],
                st.session_state["plan_input"],
            )
        rejection_reason = reject_col.text_input("거절 사유")
        if reject_col.button("재계획") and rejection_reason:
            graph = build_planner_graph()
            st.session_state["planner_state"] = graph.invoke(
                {
                    "parsed_input": st.session_state["plan_input"],
                    "approval_status": "rejected",
                    "rejection_reason": rejection_reason,
                }
            )
            render_result(
                st.session_state["planner_state"],
                st.session_state["plan_input"],
            )


def render_natural_language_tab() -> None:
    raw_input = st.text_area("자연어 일정 입력", height=160)
    if st.button("자연어 입력 구조화"):
        try:
            plan_input = parse_natural_language_input(raw_input)
        except LLMParserError as exc:
            st.error(str(exc))
            return
        st.session_state["plan_input"] = plan_input
        st.session_state["planner_state"] = run_planner(plan_input)
        render_result(st.session_state["planner_state"], plan_input)


def main() -> None:
    st.set_page_config(
        page_title="AI Schedule Planner Graph",
        page_icon="calendar",
        layout="wide",
    )
    st.title("AI Schedule Planner Graph")
    render_auth_sidebar()
    natural_tab, structured_tab = st.tabs(["자연어 입력", "구조화 입력"])
    with natural_tab:
        render_natural_language_tab()
    with structured_tab:
        render_structured_tab()


if __name__ == "__main__":
    main()
