from datetime import date, time

import pytest

from planner.llm_parser import (
    LLMParserError,
    build_day_plan_parse_payload,
    build_rejection_interpretation_payload,
    build_clarification_questions,
    call_llm_sidecar,
    interpret_rejection_reason,
    parse_natural_language_input,
)
from planner.models import DayPlanInput, DraftPlan, ScheduleItem, ScheduleItemType, ValidationIssue


def test_fake_sidecar_output_becomes_day_plan_input():
    def fake_sidecar(payload):
        assert payload["task"] == "parse_day_plan"
        assert "DayPlanInput" in payload["prompt"]
        assert payload["reference_date"] == "2026-06-02"
        assert payload["output_schema"]["required"] == ["day_plan"]
        return {
            "day_plan": {
                "date": "2026-06-03",
                "day_start": "09:00",
                "day_end": "23:00",
                "fixed_events": [],
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "알고리즘 과제",
                        "estimated_minutes": 120,
                        "priority": 5,
                        "splittable": True,
                        "focus_type": "deep",
                    }
                ],
            }
        }

    result = parse_natural_language_input(
        "내일 알고리즘 과제 2시간",
        sidecar=fake_sidecar,
        reference_date=date(2026, 6, 2),
    )

    assert isinstance(result, DayPlanInput)
    assert result.date == date(2026, 6, 3)
    assert result.day_start == time(9, 0)


def test_natural_language_parse_applies_defaults_for_short_task_input():
    def fake_sidecar(payload):
        assert payload["task"] == "parse_day_plan"
        return {
            "day_plan": {
                "date": "2026-06-03",
                "day_start": None,
                "day_end": None,
                "fixed_events": [],
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "알고리즘 과제",
                        "estimated_minutes": 120,
                        "priority": None,
                        "splittable": None,
                        "focus_type": None,
                    }
                ],
            }
        }

    result = parse_natural_language_input(
        "알고리즘 과제 2시간 배치해줘",
        sidecar=fake_sidecar,
        reference_date=date(2026, 6, 3),
    )

    assert result.day_start == time(9, 0)
    assert result.day_end == time(23, 0)
    assert len(result.availability_windows) == 7
    assert result.tasks[0].priority == 3
    assert result.tasks[0].splittable is True
    assert result.tasks[0].focus_type.value == "any"
    assert result.tasks[0].start_date == date(2026, 6, 3)
    assert result.tasks[0].end_date == date(2026, 6, 9)


def test_natural_language_parse_expands_weekday_recurring_fixed_events():
    def fake_sidecar(payload):
        assert payload["task"] == "parse_day_plan"
        return {
            "day_plan": {
                "date": "2026-06-03",
                "day_start": "09:00",
                "day_end": "23:00",
                "availability_windows": [],
                "fixed_events": [
                    {
                        "id": "bad-1",
                        "title": "운동",
                        "day_offset": 5,
                        "start_time": "15:00",
                        "end_time": "15:00",
                    }
                ],
                "tasks": [],
            }
        }

    result = parse_natural_language_input(
        "월요일부터 금요일까지 매일 15시에 운동 일정 만들어줘",
        sidecar=fake_sidecar,
        reference_date=date(2026, 6, 3),
    )

    assert result.date == date(2026, 6, 1)
    assert [event.day_offset for event in result.fixed_events] == [0, 1, 2, 3, 4]
    assert [event.title for event in result.fixed_events] == ["운동"] * 5
    assert all(event.start_time == time(15, 0) for event in result.fixed_events)
    assert all(event.end_time == time(16, 0) for event in result.fixed_events)


def test_natural_language_parse_expands_daily_late_routine_from_text():
    def fake_sidecar(payload):
        assert payload["task"] == "parse_day_plan"
        return {
            "day_plan": {
                "date": "2026-06-03",
                "day_start": "09:00",
                "day_end": "23:00",
                "availability_windows": [],
                "fixed_events": [],
                "tasks": [],
            }
        }

    result = parse_natural_language_input(
        "매일 오후 11시에 하루 회고 일정으로 1시간 정도 루틴으로 넣어줘",
        sidecar=fake_sidecar,
        reference_date=date(2026, 6, 3),
    )

    assert result.date == date(2026, 6, 1)
    assert result.day_end == time(23, 59)
    assert [event.day_offset for event in result.fixed_events] == list(range(7))
    assert [event.title for event in result.fixed_events] == ["하루 회고"] * 7
    assert all(event.start_time == time(23, 0) for event in result.fixed_events)
    assert all(event.end_time == time(23, 59) for event in result.fixed_events)


def test_natural_language_parse_expands_relative_daily_routine():
    def fake_sidecar(payload):
        assert payload["task"] == "parse_day_plan"
        return {
            "day_plan": {
                "date": "2026-06-03",
                "day_start": "09:00",
                "day_end": "23:00",
                "availability_windows": [],
                "fixed_events": [],
                "tasks": [],
            }
        }

    result = parse_natural_language_input(
        "내일부터 3일 동안 매일 오전 8시에 명상 30분 루틴 넣어줘",
        sidecar=fake_sidecar,
        reference_date=date(2026, 6, 3),
    )

    assert result.date == date(2026, 6, 1)
    assert result.day_start == time(8, 0)
    assert [event.day_offset for event in result.fixed_events] == [3, 4, 5]
    assert [event.title for event in result.fixed_events] == ["명상"] * 3
    assert all(event.start_time == time(8, 0) for event in result.fixed_events)
    assert all(event.end_time == time(8, 30) for event in result.fixed_events)


def test_natural_language_parse_expands_weekday_shorthand_routine():
    def fake_sidecar(payload):
        assert payload["task"] == "parse_day_plan"
        return {
            "day_plan": {
                "date": "2026-06-03",
                "day_start": "09:00",
                "day_end": "23:00",
                "availability_windows": [],
                "fixed_events": [],
                "tasks": [],
            }
        }

    result = parse_natural_language_input(
        "이번 주 화목 저녁 7시에 헬스 1시간 고정 일정 추가해줘",
        sidecar=fake_sidecar,
        reference_date=date(2026, 6, 3),
    )

    assert result.date == date(2026, 6, 1)
    assert [event.day_offset for event in result.fixed_events] == [1, 3]
    assert [event.title for event in result.fixed_events] == ["헬스", "헬스"]
    assert all(event.start_time == time(19, 0) for event in result.fixed_events)
    assert all(event.end_time == time(20, 0) for event in result.fixed_events)


def test_natural_language_parse_uses_rule_fallback_when_sidecar_fails():
    def failing_sidecar(payload):
        assert payload["task"] == "parse_day_plan"
        raise LLMParserError("sidecar timeout")

    result = parse_natural_language_input(
        "이번 주 화목 저녁 7시에 헬스 1시간 고정 일정 추가해줘",
        sidecar=failing_sidecar,
        reference_date=date(2026, 6, 3),
        max_retries=1,
    )

    assert result.date == date(2026, 6, 1)
    assert [event.day_offset for event in result.fixed_events] == [1, 3]
    assert [event.title for event in result.fixed_events] == ["헬스", "헬스"]


def test_natural_language_parse_clamps_llm_midnight_end_time():
    def fake_sidecar(payload):
        assert payload["task"] == "parse_day_plan"
        return {
            "day_plan": {
                "date": "2026-06-03",
                "day_start": "09:00",
                "day_end": "23:00",
                "availability_windows": [],
                "fixed_events": [
                    {
                        "id": "review-1",
                        "title": "하루 회고",
                        "day_offset": 0,
                        "start_time": "23:00",
                        "end_time": "24:00",
                    }
                ],
                "tasks": [],
            }
        }

    result = parse_natural_language_input(
        "매일 오후 11시에 하루 회고 일정으로 1시간 정도 루틴으로 넣어줘",
        sidecar=fake_sidecar,
        reference_date=date(2026, 6, 3),
    )

    assert result.fixed_events[0].start_time == time(23, 0)
    assert result.fixed_events[0].end_time == time(23, 59)
    assert result.day_end == time(23, 59)


def test_natural_language_parse_extracts_explicit_daily_availability():
    def fake_sidecar(payload):
        assert payload["task"] == "parse_day_plan"
        return {
            "day_plan": {
                "date": "2026-06-03",
                "day_start": "09:00",
                "day_end": "23:00",
                "availability_windows": [],
                "fixed_events": [],
                "tasks": [
                    {
                        "id": "report",
                        "title": "보고서 작성",
                        "estimated_minutes": 180,
                        "priority": 3,
                        "splittable": False,
                    }
                ],
            }
        }

    result = parse_natural_language_input(
        "보고서 작성 3시간 배치해줘. 매일 오후 2시부터 5시만 가능해",
        sidecar=fake_sidecar,
        reference_date=date(2026, 6, 3),
    )

    assert [window.day_offset for window in result.availability_windows] == list(range(7))
    assert all(window.start_time == time(14, 0) for window in result.availability_windows)
    assert all(window.end_time == time(17, 0) for window in result.availability_windows)


def test_day_plan_parse_payload_includes_prompt_schema_and_context():
    payload = build_day_plan_parse_payload(
        "6월 3일 9시부터 23시까지 과제 계획해줘",
        reference_date=date(2026, 6, 2),
        timezone="Asia/Seoul",
    )

    assert payload["task"] == "parse_day_plan"
    assert payload["input"] == "6월 3일 9시부터 23시까지 과제 계획해줘"
    assert payload["reference_date"] == "2026-06-02"
    assert payload["timezone"] == "Asia/Seoul"
    assert "JSON만" in payload["prompt"]
    assert "fixed_events" in payload["output_schema"]["properties"]["day_plan"]["properties"]
    assert "tasks" in payload["output_schema"]["properties"]["day_plan"]["properties"]


def test_rejection_interpretation_payload_asks_for_replan_constraints():
    payload = build_rejection_interpretation_payload(
        "너무 빡빡하니 여유 시간을 늘려줘",
        current_state={
            "replan_count": 1,
            "draft_plan": DraftPlan(
                schedule_items=[
                    ScheduleItem(
                        type=ScheduleItemType.TASK,
                        title="기획서 작성",
                        source_id="report",
                        day_offset=3,
                        start_offset=300,
                        end_offset=420,
                    )
                ]
            ),
            "conversation": [
                {"role": "user", "text": "기획서 작성 내일로 미뤄줘"},
                {"role": "agent", "text": "초안을 준비했습니다."},
                {"role": "user", "text": "그거 오후로 바꿔줘"},
            ],
        },
    )

    assert payload["task"] == "interpret_rejection"
    assert payload["input"] == "너무 빡빡하니 여유 시간을 늘려줘"
    assert payload["conversation"] == [
        {"role": "user", "text": "기획서 작성 내일로 미뤄줘"},
        {"role": "agent", "text": "초안을 준비했습니다."},
        {"role": "user", "text": "그거 오후로 바꿔줘"},
    ]
    assert "ReplanConstraints" in payload["prompt"]
    assert "conversation은 최근 채팅 맥락" in payload["prompt"]
    assert payload["current_state"]["schedule_items"] == [
        {
            "type": "task",
            "title": "기획서 작성",
            "source_id": "report",
            "day_offset": 3,
            "start_offset": 300,
            "end_offset": 420,
        }
    ]
    assert "buffer_ratio_delta" in payload["output_schema"]["properties"]["replan_constraints"]["properties"]
    assert "snoozed_task_days" in payload["output_schema"]["properties"]["replan_constraints"]["properties"]
    assert "availability_overrides" in payload["output_schema"]["properties"]["replan_constraints"]["properties"]
    assert "task_day_offsets" in payload["output_schema"]["properties"]["replan_constraints"]["properties"]
    assert "duration_multipliers" in payload["output_schema"]["properties"]["replan_constraints"]["properties"]


def test_ai_rejection_interpreter_can_use_sidecar_response():
    def fake_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        return {
            "replan_constraints": {
                "buffer_ratio_delta": 0.2,
                "excluded_task_ids": ["task-low"],
                "preferred_windows": {},
                "fixed_event_buffer_after": 15,
                "notes": ["사용자가 여유와 회의 직후 buffer를 요청했습니다."],
            }
        }

    constraints = interpret_rejection_reason(
        "너무 빡빡하고 회의 직후에는 쉬고 싶어",
        sidecar=fake_sidecar,
    )

    assert constraints.buffer_ratio_delta == 0.2
    assert constraints.excluded_task_ids == ["task-low"]
    assert constraints.fixed_event_buffer_after == 15


def test_ai_rejection_interpreter_normalizes_tiny_after_event_buffer():
    def fake_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        return {
            "replan_constraints": {
                "buffer_ratio_delta": 0.2,
                "excluded_task_ids": [],
                "preferred_windows": {},
                "fixed_event_buffer_after": 1,
                "notes": ["회의 직후 휴식"],
            }
        }

    constraints = interpret_rejection_reason(
        "회의 직후에는 쉬고 싶어",
        sidecar=fake_sidecar,
    )

    assert constraints.fixed_event_buffer_after == 15


def test_rejection_reason_with_machine_readable_snooze_sets_task_day():
    constraints = interpret_rejection_reason(
        "snooze task_id=algorithm days=2 title=알고리즘 과제",
    )

    assert constraints.snoozed_task_days == {"algorithm": 2}


def test_machine_readable_snooze_overrides_sidecar_omission():
    def fake_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        return {
            "replan_constraints": {
                "buffer_ratio_delta": 0,
                "excluded_task_ids": [],
                "preferred_windows": {},
                "fixed_event_buffer_after": 0,
                "snoozed_task_days": {},
                "notes": ["모델이 스누즈를 누락했습니다."],
            }
        }

    constraints = interpret_rejection_reason(
        "snooze task_id=algorithm days=2 title=알고리즘 과제",
        sidecar=fake_sidecar,
    )

    assert constraints.snoozed_task_days == {"algorithm": 2}


def test_ai_rejection_interpreter_clamps_snooze_days_to_week():
    def fake_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        return {
            "replan_constraints": {
                "buffer_ratio_delta": 0,
                "excluded_task_ids": [],
                "preferred_windows": {},
                "fixed_event_buffer_after": 0,
                "snoozed_task_days": {"algorithm": 9},
                "notes": ["다음 주로 미루기"],
            }
        }

    constraints = interpret_rejection_reason(
        "알고리즘 과제를 다음 주로 미뤄줘",
        sidecar=fake_sidecar,
    )

    assert constraints.snoozed_task_days == {"algorithm": 6}


def test_rejection_reason_snoozes_task_by_title_from_state():
    plan_input = DayPlanInput(
        date=date(2026, 6, 3),
        day_start=time(9, 0),
        day_end=time(18, 0),
        fixed_events=[],
        tasks=[
            {
                "id": "report",
                "title": "보고서 작성",
                "estimated_minutes": 60,
                "splittable": False,
            }
        ],
    )

    constraints = interpret_rejection_reason(
        "보고서 작성은 내일로 미뤄줘",
        current_state={"parsed_input": plan_input},
    )

    assert constraints.snoozed_task_days == {"report": 1}


def test_rejection_reason_extracts_preferred_task_time_by_title():
    plan_input = DayPlanInput(
        date=date(2026, 6, 3),
        day_start=time(9, 0),
        day_end=time(18, 0),
        fixed_events=[],
        tasks=[
            {
                "id": "report",
                "title": "보고서 작성",
                "estimated_minutes": 60,
                "splittable": False,
            }
        ],
    )

    constraints = interpret_rejection_reason(
        "보고서 작성은 오후 4시로 수정해줘",
        current_state={"parsed_input": plan_input},
    )

    assert constraints.preferred_windows == {"report": "16:00"}


def test_rejection_reason_extracts_task_day_and_time_move_by_title():
    plan_input = DayPlanInput(
        date=date(2026, 6, 1),
        day_start=time(9, 0),
        day_end=time(18, 0),
        fixed_events=[],
        tasks=[
            {
                "id": "report",
                "title": "기획서 작성",
                "estimated_minutes": 120,
                "splittable": False,
            }
        ],
    )

    constraints = interpret_rejection_reason(
        "기획서 작성을 목요일 오후 2시로 옮겨줘",
        current_state={"parsed_input": plan_input},
    )

    assert constraints.task_day_offsets == {"report": 3}
    assert constraints.preferred_windows == {"report": "14:00"}


def test_rejection_reason_extracts_task_duration_multiplier_by_title():
    plan_input = DayPlanInput(
        date=date(2026, 6, 3),
        day_start=time(9, 0),
        day_end=time(18, 0),
        fixed_events=[],
        tasks=[
            {
                "id": "report",
                "title": "기획서 작성",
                "estimated_minutes": 120,
                "splittable": False,
            }
        ],
    )

    constraints = interpret_rejection_reason(
        "기획서 작성 시간이 3배 정도 늘어야 할 거 같아",
        current_state={"parsed_input": plan_input},
    )

    assert constraints.duration_multipliers == {"report": 3.0}


def test_rejection_reason_extracts_day_availability_limit():
    plan_input = DayPlanInput(
        date=date(2026, 6, 1),
        day_start=time(9, 0),
        day_end=time(18, 0),
        fixed_events=[],
        tasks=[
            {
                "id": "report",
                "title": "기획서 작성",
                "estimated_minutes": 120,
                "splittable": False,
            }
        ],
    )

    constraints = interpret_rejection_reason(
        "월요일 사용할 수 있는 시간이 1시간 밖에 없어. 일정을 옮겨줄래",
        current_state={"parsed_input": plan_input},
    )

    assert [window.model_dump() for window in constraints.availability_overrides] == [
        {
            "id": "override-available-0",
            "day_offset": 0,
            "start_time": time(9, 0),
            "end_time": time(10, 0),
        }
    ]


def test_ai_rejection_interpreter_can_return_availability_override():
    plan_input = DayPlanInput(
        date=date(2026, 6, 1),
        day_start=time(9, 0),
        day_end=time(18, 0),
        fixed_events=[],
        tasks=[],
    )

    def fake_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        return {
            "replan_constraints": {
                "buffer_ratio_delta": 0,
                "excluded_task_ids": [],
                "availability_overrides": [
                    {
                        "id": "llm-available-0",
                        "day_offset": 0,
                        "start_time": "09:00",
                        "end_time": "10:00",
                    }
                ],
                "preferred_windows": {},
                "duration_multipliers": {},
                "fixed_event_buffer_after": 0,
                "snoozed_task_days": {},
                "notes": ["월요일 가용 시간이 1시간입니다."],
            }
        }

    constraints = interpret_rejection_reason(
        "월요일 일정 좀 줄여줘",
        current_state={"parsed_input": plan_input},
        sidecar=fake_sidecar,
    )

    assert constraints.availability_overrides[0].day_offset == 0
    assert constraints.availability_overrides[0].end_time == time(10, 0)


def test_machine_readable_duration_multiplier_overrides_sidecar_omission():
    plan_input = DayPlanInput(
        date=date(2026, 6, 3),
        day_start=time(9, 0),
        day_end=time(18, 0),
        fixed_events=[],
        tasks=[
            {
                "id": "report",
                "title": "기획서 작성",
                "estimated_minutes": 120,
                "splittable": False,
            }
        ],
    )

    def fake_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        return {
            "replan_constraints": {
                "buffer_ratio_delta": 0,
                "excluded_task_ids": [],
                "preferred_windows": {},
                "duration_multipliers": {},
                "fixed_event_buffer_after": 0,
                "snoozed_task_days": {},
                "notes": ["모델이 시간 배수 변경을 누락했습니다."],
            }
        }

    constraints = interpret_rejection_reason(
        "기획서 작성 시간이 세 배 정도 늘어야 해",
        current_state={"parsed_input": plan_input},
        sidecar=fake_sidecar,
    )

    assert constraints.duration_multipliers == {"report": 3.0}


def test_missing_date_validation_error_creates_clarification_question():
    questions = build_clarification_questions(
        [
            ValidationIssue(
                code="MISSING_DATE",
                message="날짜가 없습니다.",
                blocking=False,
            )
        ]
    )

    assert questions == ["계획할 날짜를 알려주세요."]


def test_rejection_reason_too_tight_increases_buffer_ratio():
    constraints = interpret_rejection_reason("너무 빡빡해")

    assert constraints.buffer_ratio_delta == 0.1


def test_rejection_reason_after_meeting_adds_buffer_after():
    constraints = interpret_rejection_reason("회의 직후에는 쉬고 싶어")

    assert constraints.fixed_event_buffer_after == 15


def test_invalid_sidecar_output_retries_then_errors():
    calls = {"count": 0}

    def invalid_sidecar(payload):
        calls["count"] += 1
        return {"day_plan": {"date": "2026-06-03"}}

    with pytest.raises(LLMParserError):
        parse_natural_language_input(
            "불완전 입력",
            sidecar=invalid_sidecar,
            max_retries=2,
        )

    assert calls["count"] == 2


def test_call_llm_sidecar_wraps_process_errors(monkeypatch):
    class FailedProcess(Exception):
        pass

    def fake_run(*args, **kwargs):
        raise FailedProcess("proxy unavailable")

    monkeypatch.setattr("subprocess.run", fake_run)

    try:
        call_llm_sidecar({"task": "parse_day_plan"})
    except LLMParserError as exc:
        assert "proxy unavailable" in str(exc)
    else:
        raise AssertionError("expected LLMParserError")
