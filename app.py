from __future__ import annotations

from datetime import date, time, timedelta
from typing import Any

import streamlit as st

from planner.graph import build_planner_graph
from planner.llm_parser import LLMParserError, parse_natural_language_input
from planner.models import (
    DayPlanInput,
    FixedEvent,
    FocusType,
    ScheduleItem,
    Task,
    UnassignedTask,
    ValidationIssue,
)


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


def render_structured_tab() -> None:
    plan_date = st.date_input("날짜", value=date(2026, 6, 3))
    left, middle, right = st.columns(3)
    day_start = left.time_input("하루 시작", value=time(9, 0))
    day_end = middle.time_input("하루 종료", value=time(23, 0))
    buffer_ratio = right.slider("Buffer ratio", 0.0, 0.5, 0.1, 0.05)

    fixed_event_rows = st.data_editor(
        [
            {
                "id": "class-1",
                "title": "전공 수업",
                "start_time": time(10, 0),
                "end_time": time(12, 0),
                "category": "class",
            }
        ],
        num_rows="dynamic",
        width="stretch",
        key="fixed_events",
    )
    task_rows = st.data_editor(
        [
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
        ],
        num_rows="dynamic",
        width="stretch",
        key="tasks",
    )

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
    natural_tab, structured_tab = st.tabs(["자연어 입력", "구조화 입력"])
    with natural_tab:
        render_natural_language_tab()
    with structured_tab:
        render_structured_tab()


if __name__ == "__main__":
    main()
