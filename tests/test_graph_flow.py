from datetime import date, time

from langgraph.checkpoint.memory import InMemorySaver

from planner.graph import build_planner_graph
from planner.models import AvailabilityWindow, DayPlanInput, FixedEvent, FocusType, Task


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


def test_graph_places_task_inside_availability_and_task_date_range():
    plan_input = DayPlanInput(
        date=date(2026, 6, 3),
        day_start=time(9, 0),
        day_end=time(18, 0),
        availability_windows=[
            AvailabilityWindow(
                id="available-0",
                day_offset=0,
                start_time=time(9, 0),
                end_time=time(12, 0),
            ),
            AvailabilityWindow(
                id="available-1",
                day_offset=1,
                start_time=time(13, 0),
                end_time=time(16, 0),
            ),
        ],
        fixed_events=[],
        tasks=[
            Task(
                id="task-1",
                title="알고리즘 과제",
                estimated_minutes=120,
                priority=5,
                start_date=date(2026, 6, 4),
                end_date=date(2026, 6, 4),
                splittable=False,
            )
        ],
        buffer_ratio=0.0,
    )

    result = invoke_graph({"parsed_input": plan_input, "approval_status": "pending"})

    task_items = [
        item
        for item in result["draft_plan"].schedule_items
        if item.source_id == "task-1"
    ]
    assert len(task_items) == 1
    assert task_items[0].day_offset == 1
    assert task_items[0].start_offset == 240


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
    assert result["parsed_input"].buffer_ratio == 0.1
    assert result["draft_plan"].target_buffer_minutes > 0


def test_rejected_input_can_use_ai_replan_interpreter(monkeypatch):
    def fake_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        assert payload["input"] == "회의 직후에는 쉬고 전체적으로 더 여유 있게 해줘"
        return {
            "replan_constraints": {
                "buffer_ratio_delta": 0.2,
                "excluded_task_ids": [],
                "preferred_windows": {},
                "fixed_event_buffer_after": 15,
                "notes": ["AI가 사용자 피드백을 재계획 제약으로 해석했습니다."],
            }
        }

    monkeypatch.setattr("planner.nodes.call_llm_sidecar", fake_sidecar)

    result = invoke_graph(
        {
            "parsed_input": make_valid_input(),
            "approval_status": "rejected",
            "rejection_reason": "회의 직후에는 쉬고 전체적으로 더 여유 있게 해줘",
            "use_llm_replan": True,
        }
    )

    assert result["replan_constraints"].buffer_ratio_delta == 0.2
    assert result["parsed_input"].buffer_ratio == 0.2
    assert result["parsed_input"].fixed_events[0].buffer_after_minutes == 15
    assert "AI가 사용자 피드백" in result["replan_constraints"].notes[0]


def test_rejected_input_can_snooze_task_to_next_day(monkeypatch):
    def fake_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        return {
            "replan_constraints": {
                "buffer_ratio_delta": 0,
                "excluded_task_ids": [],
                "preferred_windows": {},
                "fixed_event_buffer_after": 0,
                "snoozed_task_days": {"task-1": 1},
                "notes": ["사용자가 코드 리뷰를 내일로 스누즈했습니다."],
            }
        }

    monkeypatch.setattr("planner.nodes.call_llm_sidecar", fake_sidecar)

    result = invoke_graph(
        {
            "parsed_input": make_valid_input(),
            "approval_status": "rejected",
            "rejection_reason": "코드 리뷰는 내일로 미뤄줘",
            "use_llm_replan": True,
        }
    )

    task_items = [
        item
        for item in result["draft_plan"].schedule_items
        if item.source_id == "task-1"
    ]
    assert len(task_items) == 1
    assert task_items[0].day_offset == 1
    assert task_items[0].start_offset == 0
    assert result["replan_constraints"].snoozed_task_days == {"task-1": 1}


def test_rejected_input_can_add_new_task_from_ai_chat(monkeypatch):
    def fake_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        assert payload["input"] == "프로젝트 회고도 1시간 추가해줘"
        return {
            "replan_constraints": {
                "buffer_ratio_delta": 0,
                "excluded_task_ids": [],
                "additional_tasks": [
                    {
                        "id": "task-retro",
                        "title": "프로젝트 회고",
                        "estimated_minutes": 60,
                        "priority": 3,
                        "splittable": True,
                        "focus_type": "light",
                    }
                ],
                "notes": ["사용자가 프로젝트 회고 작업 추가를 요청했습니다."],
            }
        }

    monkeypatch.setattr("planner.nodes.call_llm_sidecar", fake_sidecar)

    result = invoke_graph(
        {
            "parsed_input": make_valid_input(),
            "approval_status": "rejected",
            "rejection_reason": "프로젝트 회고도 1시간 추가해줘",
            "use_llm_replan": True,
        }
    )

    added_task = next(
        task for task in result["parsed_input"].tasks if task.id == "task-retro"
    )
    added_item = next(
        item
        for item in result["draft_plan"].schedule_items
        if item.source_id == "task-retro"
    )

    assert added_task.title == "프로젝트 회고"
    assert added_task.start_date == result["parsed_input"].date
    assert added_task.end_date == result["parsed_input"].date
    assert added_item.title == "프로젝트 회고"
    assert result["replan_constraints"].additional_tasks[0].id == "task-retro"


def test_rejected_input_can_add_fixed_event_from_ai_chat(monkeypatch):
    def fake_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        assert payload["input"] == "목요일 오후 3시에 병원 예약도 추가해줘"
        return {
            "replan_constraints": {
                "additional_fixed_events": [
                    {
                        "id": "event-hospital",
                        "title": "병원 예약",
                        "day_offset": 3,
                        "start_time": "15:00",
                        "end_time": "16:00",
                    }
                ],
                "notes": ["사용자가 병원 예약 고정 일정 추가를 요청했습니다."],
            }
        }

    monkeypatch.setattr("planner.nodes.call_llm_sidecar", fake_sidecar)

    plan_input = make_valid_input().model_copy(
        update={
            "day_end": time(18, 0),
            "availability_windows": [
                AvailabilityWindow(
                    id=f"available-{day_offset}",
                    day_offset=day_offset,
                    start_time=time(9, 0),
                    end_time=time(18, 0),
                )
                for day_offset in range(7)
            ],
        }
    )

    result = invoke_graph(
        {
            "parsed_input": plan_input,
            "approval_status": "rejected",
            "rejection_reason": "목요일 오후 3시에 병원 예약도 추가해줘",
            "use_llm_replan": True,
        }
    )

    added_event = next(
        event
        for event in result["parsed_input"].fixed_events
        if event.id == "event-hospital"
    )
    added_item = next(
        item
        for item in result["draft_plan"].schedule_items
        if item.source_id == "event-hospital"
    )

    assert added_event.title == "병원 예약"
    assert added_event.day_offset == 3
    assert added_event.start_time == time(15, 0)
    assert added_item.title == "병원 예약"
    assert result["replan_constraints"].additional_fixed_events[0].id == "event-hospital"


def test_rejected_input_can_remove_fixed_event_from_ai_chat(monkeypatch):
    def fake_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        assert payload["input"] == "회의는 취소됐으니 빼줘"
        return {
            "replan_constraints": {
                "excluded_fixed_event_ids": ["meeting"],
                "notes": ["사용자가 회의 고정 일정 삭제를 요청했습니다."],
            }
        }

    monkeypatch.setattr("planner.nodes.call_llm_sidecar", fake_sidecar)

    result = invoke_graph(
        {
            "parsed_input": make_valid_input(),
            "approval_status": "rejected",
            "rejection_reason": "회의는 취소됐으니 빼줘",
            "use_llm_replan": True,
        }
    )

    assert all(event.id != "meeting" for event in result["parsed_input"].fixed_events)
    assert all(item.source_id != "meeting" for item in result["draft_plan"].schedule_items)
    assert result["replan_constraints"].excluded_fixed_event_ids == ["meeting"]


def test_rejected_input_can_update_task_fields_from_ai_chat(monkeypatch):
    def fake_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        assert payload["input"] == "코드 리뷰를 코드 리뷰 준비로 바꾸고 45분으로 수정해줘"
        return {
            "replan_constraints": {
                "task_updates": {
                    "task-1": {
                        "title": "코드 리뷰 준비",
                        "estimated_minutes": 45,
                        "focus_type": "light",
                    }
                },
                "notes": ["사용자가 작업 이름과 소요 시간을 수정했습니다."],
            }
        }

    monkeypatch.setattr("planner.nodes.call_llm_sidecar", fake_sidecar)

    result = invoke_graph(
        {
            "parsed_input": make_valid_input().model_copy(update={"fixed_events": []}),
            "approval_status": "rejected",
            "rejection_reason": "코드 리뷰를 코드 리뷰 준비로 바꾸고 45분으로 수정해줘",
            "use_llm_replan": True,
        }
    )

    updated_task = next(task for task in result["parsed_input"].tasks if task.id == "task-1")
    updated_item = next(item for item in result["draft_plan"].schedule_items if item.source_id == "task-1")

    assert updated_task.title == "코드 리뷰 준비"
    assert updated_task.estimated_minutes == 45
    assert updated_item.title == "코드 리뷰 준비"
    assert updated_item.duration_minutes == 45
    assert result["replan_constraints"].task_updates["task-1"]["estimated_minutes"] == 45


def test_rejected_input_can_update_fixed_event_fields_from_ai_chat(monkeypatch):
    def fake_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        assert payload["input"] == "회의를 짧은 회의로 바꾸고 11시부터 11시 30분으로 옮겨줘"
        return {
            "replan_constraints": {
                "fixed_event_updates": {
                    "meeting": {
                        "title": "짧은 회의",
                        "start_time": "11:00",
                        "end_time": "11:30",
                    }
                },
                "notes": ["사용자가 고정 일정 이름과 시간을 수정했습니다."],
            }
        }

    monkeypatch.setattr("planner.nodes.call_llm_sidecar", fake_sidecar)

    result = invoke_graph(
        {
            "parsed_input": make_valid_input().model_copy(update={"day_end": time(18, 0)}),
            "approval_status": "rejected",
            "rejection_reason": "회의를 짧은 회의로 바꾸고 11시부터 11시 30분으로 옮겨줘",
            "use_llm_replan": True,
        }
    )

    updated_event = next(event for event in result["parsed_input"].fixed_events if event.id == "meeting")
    updated_item = next(item for item in result["draft_plan"].schedule_items if item.source_id == "meeting")

    assert updated_event.title == "짧은 회의"
    assert updated_event.start_time == time(11, 0)
    assert updated_event.end_time == time(11, 30)
    assert updated_item.title == "짧은 회의"
    assert updated_item.start_offset == 120
    assert result["replan_constraints"].fixed_event_updates["meeting"]["title"] == "짧은 회의"


def test_rejected_input_can_apply_preferred_task_time(monkeypatch):
    def fake_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        return {
            "replan_constraints": {
                "buffer_ratio_delta": 0,
                "excluded_task_ids": [],
                "preferred_windows": {"task-1": "11:00"},
                "fixed_event_buffer_after": 0,
                "snoozed_task_days": {},
                "notes": ["사용자가 코드 리뷰 시간을 수정했습니다."],
            }
        }

    monkeypatch.setattr("planner.nodes.call_llm_sidecar", fake_sidecar)

    plan_input = make_valid_input().model_copy(
        update={
            "fixed_events": [],
            "day_end": time(18, 0),
        }
    )
    result = invoke_graph(
        {
            "parsed_input": plan_input,
            "approval_status": "rejected",
            "rejection_reason": "코드 리뷰를 11시로 수정해줘",
            "use_llm_replan": True,
        }
    )

    task_items = [
        item
        for item in result["draft_plan"].schedule_items
        if item.source_id == "task-1"
    ]
    assert len(task_items) == 1
    assert task_items[0].start_offset == 120
    assert result["replan_constraints"].preferred_windows == {"task-1": "11:00"}


def test_rejected_input_can_move_task_to_target_day_and_time():
    plan_input = DayPlanInput(
        date=date(2026, 6, 1),
        day_start=time(9, 0),
        day_end=time(18, 0),
        availability_windows=[
            AvailabilityWindow(
                id=f"available-{day_offset}",
                day_offset=day_offset,
                start_time=time(9, 0),
                end_time=time(18, 0),
            )
            for day_offset in range(7)
        ],
        fixed_events=[],
        tasks=[
            Task(
                id="task-plan",
                title="기획서 작성",
                estimated_minutes=120,
                splittable=False,
            )
        ],
        buffer_ratio=0,
    )

    result = invoke_graph(
        {
            "parsed_input": plan_input,
            "approval_status": "rejected",
            "rejection_reason": "기획서 작성을 목요일 오후 2시로 옮겨줘",
        }
    )

    task_item = next(
        item
        for item in result["draft_plan"].schedule_items
        if item.source_id == "task-plan"
    )
    task = next(task for task in result["parsed_input"].tasks if task.id == "task-plan")

    assert result["replan_constraints"].task_day_offsets == {"task-plan": 3}
    assert result["replan_constraints"].preferred_windows == {"task-plan": "14:00"}
    assert task.start_date == date(2026, 6, 4)
    assert task.end_date == date(2026, 6, 4)
    assert task_item.day_offset == 3
    assert task_item.start_offset == 300


def test_rejected_input_can_apply_task_duration_multiplier():
    plan_input = make_valid_input().model_copy(
        update={
            "fixed_events": [],
            "day_end": time(18, 0),
        }
    )

    result = invoke_graph(
        {
            "parsed_input": plan_input,
            "approval_status": "rejected",
            "rejection_reason": "코드 리뷰 시간이 3배 정도 늘어야 할 거 같아",
        }
    )

    task = next(task for task in result["parsed_input"].tasks if task.id == "task-1")
    task_items = [
        item
        for item in result["draft_plan"].schedule_items
        if item.source_id == "task-1"
    ]

    assert result["replan_constraints"].duration_multipliers == {"task-1": 3.0}
    assert task.estimated_minutes == 90
    assert task_items[0].duration_minutes == 90


def test_rejected_input_can_limit_day_availability_and_move_tasks():
    plan_input = DayPlanInput(
        date=date(2026, 6, 1),
        day_start=time(9, 0),
        day_end=time(18, 0),
        availability_windows=[
            AvailabilityWindow(
                id=f"available-{day_offset}",
                day_offset=day_offset,
                start_time=time(9, 0),
                end_time=time(18, 0),
            )
            for day_offset in range(7)
        ],
        fixed_events=[
            FixedEvent(
                id="meeting",
                title="팀 미팅",
                day_offset=0,
                start_time=time(9, 0),
                end_time=time(10, 0),
            )
        ],
        tasks=[
            Task(
                id="task-plan",
                title="기획서 작성",
                estimated_minutes=120,
                splittable=False,
            ),
            Task(
                id="task-study",
                title="개발 공부",
                estimated_minutes=120,
                splittable=False,
            ),
        ],
        buffer_ratio=0,
    )

    result = invoke_graph(
        {
            "parsed_input": plan_input,
            "approval_status": "rejected",
            "rejection_reason": "월요일 사용할 수 있는 시간이 1시간 밖에 없어. 일정을 옮겨줄래",
        }
    )

    task_items = [
        item
        for item in result["draft_plan"].schedule_items
        if item.source_id in {"task-plan", "task-study"}
    ]

    assert result["replan_constraints"].availability_overrides[0].day_offset == 0
    assert result["parsed_input"].availability_windows[0].end_time == time(10, 0)
    assert all(item.day_offset != 0 for item in task_items)


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
