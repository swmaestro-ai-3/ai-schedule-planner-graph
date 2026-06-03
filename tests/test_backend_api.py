from __future__ import annotations

from datetime import date

from planner.llm_parser import LLMParserError


def failing_sidecar(_payload):
    raise LLMParserError("offline")


def test_create_plan_response_runs_real_planner_for_natural_language():
    from backend.api import create_plan_response

    draft = create_plan_response(
        {
            "mode": "natural",
            "text": "월요일부터 금요일까지 매일 15시에 운동 일정으로 1시간 넣어줘",
            "bufferRatio": 0,
        },
        reference_date=date(2026, 6, 3),
        sidecar=failing_sidecar,
    )

    workout_items = [item for item in draft["items"] if item["title"] == "운동"]
    assert [item["dayIndex"] for item in workout_items] == [0, 1, 2, 3, 4]
    assert all(item["start"] == "15:00" for item in workout_items)
    assert draft["backend"]["planInput"]["date"] == "2026-06-01"


def test_replan_response_applies_chat_snooze_to_existing_plan():
    from backend.api import create_plan_response, replan_response

    draft = create_plan_response(
        {
            "mode": "structured",
            "bufferRatio": 0,
            "fixedEvents": ["월 09:00 팀 미팅"],
            "tasks": ["기획서 작성 120분"],
        },
        reference_date=date(2026, 6, 1),
        sidecar=failing_sidecar,
    )
    before = next(item for item in draft["items"] if item["title"] == "기획서 작성")

    replanned = replan_response(
        {
            "draft": draft,
            "reason": "기획서 작성은 하루 뒤로 미뤄줘",
            "snoozeTaskId": before["id"],
            "snoozeDays": 1,
        },
        sidecar=failing_sidecar,
    )
    after = next(item for item in replanned["items"] if item["title"] == "기획서 작성")

    assert before["dayIndex"] == 0
    assert after["dayIndex"] == 1
    assert replanned["replanCount"] == 1
    assert "하루 뒤로" in replanned["lastFeedback"]


def test_replan_response_understands_korean_day_snooze_without_control_id():
    from backend.api import create_plan_response, replan_response

    draft = create_plan_response(
        {
            "mode": "structured",
            "bufferRatio": 0,
            "fixedEvents": ["월 09:00 팀 미팅"],
            "tasks": ["기획서 작성 120분"],
        },
        reference_date=date(2026, 6, 1),
        sidecar=failing_sidecar,
    )

    replanned = replan_response(
        {
            "draft": draft,
            "reason": "기획서 작성은 하루 뒤로 미뤄줘",
            "snoozeDays": 1,
        },
        sidecar=failing_sidecar,
    )
    after = next(item for item in replanned["items"] if item["title"] == "기획서 작성")

    assert after["dayIndex"] == 1
