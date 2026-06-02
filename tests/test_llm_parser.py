from datetime import date, time

import pytest

from planner.llm_parser import (
    LLMParserError,
    build_clarification_questions,
    interpret_rejection_reason,
    parse_natural_language_input,
)
from planner.models import DayPlanInput, ValidationIssue


def test_fake_sidecar_output_becomes_day_plan_input():
    def fake_sidecar(payload):
        assert payload["task"] == "parse_day_plan"
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

    result = parse_natural_language_input("내일 알고리즘 과제 2시간", sidecar=fake_sidecar)

    assert isinstance(result, DayPlanInput)
    assert result.date == date(2026, 6, 3)
    assert result.day_start == time(9, 0)


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
