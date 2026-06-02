from datetime import date, time

from langgraph.checkpoint.memory import InMemorySaver

from planner.graph import build_planner_graph
from planner.models import DayPlanInput, FixedEvent, FocusType, Task


def make_valid_input():
    return DayPlanInput(
        date=date(2026, 6, 3),
        day_start=time(9, 0),
        day_end=time(12, 0),
        fixed_events=[
            FixedEvent(
                id="meeting",
                title="회의",
                start_time=time(10, 0),
                end_time=time(11, 0),
            )
        ],
        tasks=[
            Task(
                id="task-1",
                title="코드 리뷰",
                estimated_minutes=30,
                priority=3,
                splittable=False,
                focus_type=FocusType.LIGHT,
            )
        ],
        buffer_ratio=0.0,
    )


def invoke_graph(initial_state):
    graph = build_planner_graph(checkpointer=InMemorySaver())
    return graph.invoke(
        initial_state,
        config={"configurable": {"thread_id": "test-thread"}},
    )


def test_valid_structured_input_reaches_draft_plan():
    result = invoke_graph(
        {
            "parsed_input": make_valid_input(),
            "approval_status": "pending",
        }
    )

    assert result["draft_plan"].schedule_items
    assert "final_plan" not in result


def test_overlapping_fixed_events_end_as_invalid_input():
    plan_input = make_valid_input().model_copy(
        update={
            "fixed_events": [
                FixedEvent(
                    id="a",
                    title="회의 A",
                    start_time=time(10, 0),
                    end_time=time(11, 0),
                ),
                FixedEvent(
                    id="b",
                    title="회의 B",
                    start_time=time(10, 30),
                    end_time=time(11, 30),
                ),
            ]
        }
    )

    result = invoke_graph({"parsed_input": plan_input})

    assert any(issue.code == "FIXED_EVENT_OVERLAP" for issue in result["input_errors"])
    assert "draft_plan" not in result


def test_approved_input_creates_final_plan():
    result = invoke_graph(
        {
            "parsed_input": make_valid_input(),
            "approval_status": "approved",
        }
    )

    assert result["final_plan"].approval_required is True
    assert result["final_plan"].schedule_items


def test_rejected_input_creates_constraints_and_increments_count():
    result = invoke_graph(
        {
            "parsed_input": make_valid_input(),
            "approval_status": "rejected",
            "rejection_reason": "너무 빡빡해",
        }
    )

    assert result["replan_count"] == 1
    assert result["replan_constraints"].buffer_ratio_delta == 0.1
    assert result["approval_status"] == "pending"


def test_replan_limit_stops_automatic_replanning():
    result = invoke_graph(
        {
            "parsed_input": make_valid_input(),
            "approval_status": "rejected",
            "rejection_reason": "너무 빡빡해",
            "replan_count": 3,
        }
    )

    assert "자동 재계획 한도" in result["explanation"]
