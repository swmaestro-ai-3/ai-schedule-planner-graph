from __future__ import annotations

from datetime import date
from types import SimpleNamespace

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


def test_create_plan_response_can_answer_without_draft_from_agent_chat(monkeypatch):
    from backend.api import create_plan_response

    def fake_parse_sidecar(payload):
        assert payload["task"] == "parse_day_plan"
        assert payload["input"] == "어떤 식으로 말하면 돼?"
        return {
            "assistant_message": "예: 월요일 15시에 운동 1시간, 목요일까지 기획서 2시간처럼 말하면 됩니다."
        }

    result = create_plan_response(
        {
            "mode": "natural",
            "text": "어떤 식으로 말하면 돼?",
            "bufferRatio": 15,
        },
        reference_date=date(2026, 6, 1),
        sidecar=fake_parse_sidecar,
    )

    assert result == {
        "agentMessage": "예: 월요일 15시에 운동 1시간, 목요일까지 기획서 2시간처럼 말하면 됩니다."
    }


def test_create_plan_response_passes_agent_conversation_to_parse_llm():
    from backend.api import create_plan_response

    def fake_parse_sidecar(payload):
        assert payload["task"] == "parse_day_plan"
        assert payload["conversation"] == [
            {"role": "agent", "text": "요일, 시간, 소요 시간을 알려주면 됩니다."},
            {"role": "user", "text": "그럼 월요일 운동 1시간 넣어줘"},
        ]
        return {
            "assistant_message": "운동 일정을 월요일에 넣는 초안을 만들 수 있습니다."
        }

    result = create_plan_response(
        {
            "mode": "natural",
            "text": "그럼 월요일 운동 1시간 넣어줘",
            "bufferRatio": 15,
            "conversation": [
                {"role": "agent", "text": "요일, 시간, 소요 시간을 알려주면 됩니다."},
                {"role": "user", "text": "그럼 월요일 운동 1시간 넣어줘"},
            ],
        },
        reference_date=date(2026, 6, 1),
        sidecar=fake_parse_sidecar,
    )

    assert result["agentMessage"] == "운동 일정을 월요일에 넣는 초안을 만들 수 있습니다."


def test_create_plan_response_can_include_agent_message_with_draft():
    from backend.api import create_plan_response

    def fake_parse_sidecar(payload):
        assert payload["task"] == "parse_day_plan"
        return {
            "assistant_message": "운동 루틴은 고정 일정으로 두고 나머지 작업과 겹치지 않게 초안을 만들었습니다.",
            "day_plan": {
                "date": "2026-06-01",
                "day_start": "09:00",
                "day_end": "23:00",
                "fixed_events": [
                    {
                        "id": "event-workout",
                        "title": "운동",
                        "day_offset": 0,
                        "start_time": "15:00",
                        "end_time": "16:00",
                    }
                ],
                "tasks": [
                    {
                        "id": "task-report",
                        "title": "기획서 작성",
                        "estimated_minutes": 120,
                        "priority": 3,
                        "splittable": True,
                        "focus_type": "deep",
                    }
                ],
            },
        }

    result = create_plan_response(
        {
            "mode": "natural",
            "text": "월요일 15시에 운동 넣고 기획서도 2시간 배치해줘",
            "bufferRatio": 15,
        },
        reference_date=date(2026, 6, 1),
        sidecar=fake_parse_sidecar,
    )

    assert result["agentMessage"] == "운동 루틴은 고정 일정으로 두고 나머지 작업과 겹치지 않게 초안을 만들었습니다."
    assert any(item["title"] == "운동" for item in result["items"])
    assert any(item["title"] == "기획서 작성" for item in result["items"])


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


def test_replan_response_keeps_prior_chat_feedback_when_duration_changes():
    from backend.api import create_plan_response, replan_response

    draft = create_plan_response(
        {
            "mode": "structured",
            "bufferRatio": 0,
            "fixedEvents": ["월 09:00 팀 미팅"],
            "tasks": ["기획서 작성 120분", "코드 리뷰 90분", "개발 공부 120분"],
        },
        reference_date=date(2026, 6, 1),
        sidecar=failing_sidecar,
    )

    snoozed = replan_response(
        {
            "draft": draft,
            "reason": "기획서 작성 내일로 미뤄줘",
            "snoozeDays": 1,
        },
        sidecar=failing_sidecar,
    )
    after_snooze = next(item for item in snoozed["items"] if item["title"] == "기획서 작성")

    resized = replan_response(
        {
            "draft": snoozed,
            "reason": "기획서 작성 시간이 3배 정도 늘어야 할 거 같아",
            "snoozeDays": 1,
        },
        sidecar=failing_sidecar,
    )
    after_resize = next(item for item in resized["items"] if item["title"] == "기획서 작성")
    task_input = next(
        task
        for task in resized["backend"]["planInput"]["tasks"]
        if task["title"] == "기획서 작성"
    )

    assert after_snooze["dayIndex"] == 1
    assert after_snooze["durationMinutes"] == 120
    assert after_resize["dayIndex"] == 1
    assert after_resize["durationMinutes"] == 360
    assert task_input["estimated_minutes"] == 360
    assert "내일로" in resized["lastFeedback"]
    assert "3배" in resized["lastFeedback"]


def test_replan_response_limits_monday_availability_from_chat_feedback():
    from backend.api import create_plan_response, replan_response

    draft = create_plan_response(
        {
            "mode": "structured",
            "bufferRatio": 0,
            "fixedEvents": ["월 09:00 팀 미팅"],
            "tasks": ["기획서 작성 120분", "코드 리뷰 90분", "개발 공부 120분"],
        },
        reference_date=date(2026, 6, 1),
        sidecar=failing_sidecar,
    )

    replanned = replan_response(
        {
            "draft": draft,
            "reason": "월요일 사용할 수 있는 시간이 1시간 밖에 없어. 일정을 옮겨줄래",
            "snoozeDays": 1,
        },
        sidecar=failing_sidecar,
    )
    monday_items = [item for item in replanned["items"] if item["dayIndex"] == 0]
    task_items = [item for item in replanned["items"] if item["type"] == "task"]

    assert [(item["start"], item["end"], item["title"]) for item in monday_items] == [
        ("09:00", "10:00", "팀 미팅")
    ]
    assert all(item["dayIndex"] != 0 for item in task_items)
    assert "월요일" in replanned["lastFeedback"]


def test_replan_response_can_add_new_task_from_ai_chat(monkeypatch):
    from backend import api
    from backend.api import create_plan_response, replan_response

    draft = create_plan_response(
        {
            "mode": "structured",
            "bufferRatio": 0,
            "fixedEvents": ["월 09:00 팀 미팅"],
            "tasks": ["기획서 작성 60분"],
        },
        reference_date=date(2026, 6, 1),
        sidecar=failing_sidecar,
    )

    monkeypatch.setattr(api, "check_openai_oauth_proxy", lambda: SimpleNamespace(connected=True))

    def fake_replan_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        assert payload["input"] == "프로젝트 회고도 1시간 추가해줘"
        return {
            "replan_constraints": {
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
                "notes": ["새 작업 추가"],
            }
        }

    monkeypatch.setattr("planner.nodes.call_llm_sidecar", fake_replan_sidecar)

    replanned = replan_response(
        {
            "draft": draft,
            "reason": "프로젝트 회고도 1시간 추가해줘",
            "snoozeDays": 1,
            "conversation": [
                {"role": "user", "text": "기획서 작성도 넣어줘"},
                {"role": "agent", "text": "초안을 준비했습니다."},
                {"role": "user", "text": "프로젝트 회고도 1시간 추가해줘"},
            ],
        }
    )

    assert any(item["title"] == "프로젝트 회고" for item in replanned["items"])
    assert any(
        task["id"] == "task-retro" and task["title"] == "프로젝트 회고"
        for task in replanned["backend"]["planInput"]["tasks"]
    )


def test_replan_response_can_add_and_remove_fixed_events_from_ai_chat(monkeypatch):
    from backend import api
    from backend.api import create_plan_response, replan_response

    draft = create_plan_response(
        {
            "mode": "structured",
            "bufferRatio": 0,
            "fixedEvents": ["월 09:00 팀 미팅"],
            "tasks": ["기획서 작성 60분"],
        },
        reference_date=date(2026, 6, 1),
        sidecar=failing_sidecar,
    )

    monkeypatch.setattr(api, "check_openai_oauth_proxy", lambda: SimpleNamespace(connected=True))

    def fake_replan_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        assert payload["input"] == "팀 미팅은 빼고 목요일 오후 3시에 병원 예약 추가해줘"
        return {
            "replan_constraints": {
                "excluded_fixed_event_ids": ["fixed-1"],
                "additional_fixed_events": [
                    {
                        "id": "event-hospital",
                        "title": "병원 예약",
                        "day_offset": 3,
                        "start_time": "15:00",
                        "end_time": "16:00",
                    }
                ],
                "notes": ["고정 일정 편집"],
            }
        }

    monkeypatch.setattr("planner.nodes.call_llm_sidecar", fake_replan_sidecar)

    replanned = replan_response(
        {
            "draft": draft,
            "reason": "팀 미팅은 빼고 목요일 오후 3시에 병원 예약 추가해줘",
            "snoozeDays": 1,
        }
    )

    assert all(item["title"] != "팀 미팅" for item in replanned["items"])
    assert any(
        item["title"] == "병원 예약"
        and item["type"] == "fixed"
        and item["dayIndex"] == 3
        and item["start"] == "15:00"
        for item in replanned["items"]
    )


def test_replan_response_can_update_existing_items_from_ai_chat(monkeypatch):
    from backend import api
    from backend.api import create_plan_response, replan_response

    draft = create_plan_response(
        {
            "mode": "structured",
            "bufferRatio": 0,
            "fixedEvents": ["월 09:00 팀 미팅"],
            "tasks": ["기획서 작성 60분"],
        },
        reference_date=date(2026, 6, 1),
        sidecar=failing_sidecar,
    )

    monkeypatch.setattr(api, "check_openai_oauth_proxy", lambda: SimpleNamespace(connected=True))

    def fake_replan_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        assert payload["input"] == "팀 미팅은 10시로 옮기고 기획서는 90분으로 바꿔줘"
        return {
            "replan_constraints": {
                "fixed_event_updates": {
                    "fixed-1": {
                        "start_time": "10:00",
                        "end_time": "11:00",
                    }
                },
                "task_updates": {
                    "task-1": {
                        "estimated_minutes": 90,
                    }
                },
                "notes": ["기존 항목 수정"],
            }
        }

    monkeypatch.setattr("planner.nodes.call_llm_sidecar", fake_replan_sidecar)

    replanned = replan_response(
        {
            "draft": draft,
            "reason": "팀 미팅은 10시로 옮기고 기획서는 90분으로 바꿔줘",
            "snoozeDays": 1,
        }
    )

    meeting = next(item for item in replanned["items"] if item["title"] == "팀 미팅")
    task = next(item for item in replanned["items"] if item["title"] == "기획서 작성")

    assert meeting["start"] == "10:00"
    assert meeting["end"] == "11:00"
    assert task["durationMinutes"] == 90


def test_replan_response_moves_fixed_event_when_chat_created_schedule(monkeypatch):
    from backend import api
    from backend.api import create_plan_response, replan_response

    draft = create_plan_response(
        {
            "mode": "natural",
            "text": "월요일 10시에 기획서 작성 1시간 넣어줘",
            "bufferRatio": 0,
        },
        reference_date=date(2026, 6, 8),
        sidecar=failing_sidecar,
    )

    monkeypatch.setattr(api, "check_openai_oauth_proxy", lambda: SimpleNamespace(connected=True))

    def fake_replan_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        return {
            "replan_constraints": {
                "notes": ["모델이 고정 일정 이동 제약을 누락했습니다."],
            }
        }

    monkeypatch.setattr("planner.nodes.call_llm_sidecar", fake_replan_sidecar)

    replanned = replan_response(
        {
            "draft": draft,
            "reason": "기획서 작성을 화요일 오후 2시로 옮겨줘",
            "snoozeDays": 1,
        }
    )

    moved = next(item for item in replanned["items"] if item["title"] == "기획서 작성")
    assert moved["type"] == "fixed"
    assert moved["dayIndex"] == 1
    assert moved["start"] == "14:00"
    assert moved["end"] == "15:00"


def test_replan_response_adds_fixed_event_from_chat_feedback(monkeypatch):
    from backend import api
    from backend.api import create_plan_response, replan_response

    draft = create_plan_response(
        {
            "mode": "natural",
            "text": "월요일부터 금요일까지 매일 15시에 운동 1시간 넣어줘",
            "bufferRatio": 15,
        },
        reference_date=date(2026, 6, 8),
        sidecar=failing_sidecar,
    )

    monkeypatch.setattr(api, "check_openai_oauth_proxy", lambda: SimpleNamespace(connected=True))

    def fake_replan_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        return {
            "replan_constraints": {
                "notes": ["모델이 새 고정 일정 추가 제약을 누락했습니다."],
            }
        }

    monkeypatch.setattr("planner.nodes.call_llm_sidecar", fake_replan_sidecar)

    replanned = replan_response(
        {
            "draft": draft,
            "reason": "금요일 저녁에 회고 넣어줘",
            "snoozeDays": 1,
        }
    )

    added = [item for item in replanned["items"] if item["title"] == "회고"]
    assert added == [
        {
            "id": "fixed-4-회고",
            "type": "fixed",
            "title": "회고",
            "dayIndex": 4,
            "start": "19:00",
            "end": "20:00",
            "durationMinutes": 60,
            "note": "고정 일정입니다.",
            "priority": None,
        }
    ]


def test_replan_response_expands_day_end_for_late_daily_chat_event(monkeypatch):
    from backend import api
    from backend.api import create_plan_response, replan_response

    draft = create_plan_response(
        {
            "mode": "natural",
            "text": "월요일부터 금요일까지 매일 15시에 운동 1시간 넣어줘",
            "bufferRatio": 15,
        },
        reference_date=date(2026, 6, 8),
        sidecar=failing_sidecar,
    )

    monkeypatch.setattr(api, "check_openai_oauth_proxy", lambda: SimpleNamespace(connected=True))

    def fake_replan_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        return {
            "replan_constraints": {
                "notes": ["모델이 늦은 반복 일정 추가 제약을 누락했습니다."],
            }
        }

    monkeypatch.setattr("planner.nodes.call_llm_sidecar", fake_replan_sidecar)

    replanned = replan_response(
        {
            "draft": draft,
            "reason": "매일 저녁 11시에 하루 회고 1시간 넣어줘",
            "snoozeDays": 1,
        }
    )

    reflection_items = [item for item in replanned["items"] if item["title"] == "하루 회고"]
    assert len(reflection_items) == 7
    assert all(item["start"] == "23:00" for item in reflection_items)
    assert all(item["end"] == "23:59" for item in reflection_items)
    assert replanned["backend"]["planInput"]["day_end"] == "23:59:00"


def test_replan_response_can_include_agent_message_with_draft(monkeypatch):
    from backend import api
    from backend.api import create_plan_response, replan_response

    draft = create_plan_response(
        {
            "mode": "structured",
            "bufferRatio": 0,
            "fixedEvents": ["월 09:00 팀 미팅"],
            "tasks": ["기획서 작성 60분"],
        },
        reference_date=date(2026, 6, 1),
        sidecar=failing_sidecar,
    )

    monkeypatch.setattr(api, "check_openai_oauth_proxy", lambda: SimpleNamespace(connected=True))

    def fake_replan_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        return {
            "replan_constraints": {
                "task_updates": {
                    "task-1": {
                        "estimated_minutes": 90,
                    }
                },
                "assistant_message": "기획서 작성 시간을 90분으로 늘리고 고정 일정 뒤에 배치했습니다.",
                "notes": ["기존 항목 수정 설명"],
            }
        }

    monkeypatch.setattr("planner.nodes.call_llm_sidecar", fake_replan_sidecar)

    replanned = replan_response(
        {
            "draft": draft,
            "reason": "기획서 작성 시간을 늘려줘",
            "snoozeDays": 1,
        }
    )

    assert replanned["agentMessage"] == "기획서 작성 시간을 90분으로 늘리고 고정 일정 뒤에 배치했습니다."
    assert next(item for item in replanned["items"] if item["title"] == "기획서 작성")[
        "durationMinutes"
    ] == 90


def test_replan_response_can_answer_without_new_draft(monkeypatch):
    from backend import api
    from backend.api import create_plan_response, replan_response

    draft = create_plan_response(
        {
            "mode": "structured",
            "bufferRatio": 0,
            "fixedEvents": ["월 09:00 팀 미팅"],
            "tasks": ["기획서 작성 60분"],
        },
        reference_date=date(2026, 6, 1),
        sidecar=failing_sidecar,
    )

    monkeypatch.setattr(api, "check_openai_oauth_proxy", lambda: SimpleNamespace(connected=True))

    def fake_replan_sidecar(payload):
        assert payload["task"] == "interpret_rejection"
        assert payload["input"] == "고정 일정을 침범했어?"
        assert payload["current_state"]["schedule_items"] == [
            {
                "type": "fixed",
                "title": "팀 미팅",
                "source_id": "fixed-1",
                "day_offset": 0,
                "start_time": "09:00",
                "end_time": "10:00",
                "start_offset": 0,
                "end_offset": 60,
            },
            {
                "type": "task",
                "title": "기획서 작성",
                "source_id": "task-1",
                "day_offset": 0,
                "start_time": "10:00",
                "end_time": "11:00",
                "start_offset": 60,
                "end_offset": 120,
            },
        ]
        return {
            "replan_constraints": {
                "assistant_message": "아니요. 현재 작업은 팀 미팅 시간과 겹치지 않습니다.",
                "notes": ["사용자가 현재 배치 상태를 질문했습니다."],
            }
        }

    monkeypatch.setattr("planner.nodes.call_llm_sidecar", fake_replan_sidecar)

    result = replan_response(
        {
            "draft": {**draft, "replanCount": 3},
            "reason": "고정 일정을 침범했어?",
            "snoozeDays": 1,
        }
    )

    assert result == {
        "agentMessage": "아니요. 현재 작업은 팀 미팅 시간과 겹치지 않습니다.",
    }


def test_natural_plan_requires_openai_oauth_when_no_test_sidecar(monkeypatch):
    from backend import api
    from backend.api import OAuthRequiredError, create_plan_response

    monkeypatch.setattr(api, "check_openai_oauth_proxy", lambda: SimpleNamespace(connected=False))
    monkeypatch.setattr(
        api,
        "call_llm_sidecar",
        lambda _payload, timeout_seconds=8: (_ for _ in ()).throw(
            AssertionError("sidecar should not be called without OAuth")
        ),
    )

    try:
        create_plan_response(
            {
                "mode": "natural",
                "text": "매일 23시에 회고 1시간 넣어줘",
                "bufferRatio": 15,
            },
            reference_date=date(2026, 6, 1),
        )
    except OAuthRequiredError as exc:
        assert "OpenAI OAuth 로그인이 필요합니다" in str(exc)
    else:
        raise AssertionError("expected OAuthRequiredError")


def test_replan_requires_openai_oauth_when_no_test_sidecar(monkeypatch):
    from backend import api
    from backend.api import OAuthRequiredError, create_plan_response, replan_response

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
    monkeypatch.setattr(api, "check_openai_oauth_proxy", lambda: SimpleNamespace(connected=False))

    try:
        replan_response({"draft": draft, "reason": "기획서 하루 뒤로", "snoozeDays": 1})
    except OAuthRequiredError as exc:
        assert "OpenAI OAuth 로그인이 필요합니다" in str(exc)
    else:
        raise AssertionError("expected OAuthRequiredError")


def test_openai_status_response_reports_proxy_and_auth_file(monkeypatch, tmp_path):
    from backend import api
    from backend.api import openai_status_response

    auth_file = tmp_path / "auth.json"
    monkeypatch.setattr(
        api,
        "check_openai_oauth_proxy",
        lambda: SimpleNamespace(
            connected=True,
            message="openai-oauth proxy is reachable.",
            models=["gpt-5.1"],
        ),
    )
    monkeypatch.setattr(api, "find_existing_auth_file", lambda: auth_file)

    assert openai_status_response() == {
        "connected": True,
        "message": "openai-oauth proxy is reachable.",
        "models": ["gpt-5.1"],
        "authFileExists": True,
    }


def test_openai_connect_response_returns_already_connected(monkeypatch):
    from backend import api
    from backend.api import openai_connect_response

    monkeypatch.setattr(
        api,
        "check_openai_oauth_proxy",
        lambda: SimpleNamespace(connected=True, message="ok", models=["gpt-5.1"]),
    )

    result = openai_connect_response()

    assert result["connected"] is True
    assert result["action"] == "already_connected"
    assert result["models"] == ["gpt-5.1"]


def test_openai_connect_response_starts_login_when_auth_is_missing(monkeypatch):
    from backend import api
    from backend.api import openai_connect_response

    calls = []
    monkeypatch.setattr(
        api,
        "check_openai_oauth_proxy",
        lambda: SimpleNamespace(connected=False, message="offline", models=[]),
    )
    monkeypatch.setattr(api, "find_existing_auth_file", lambda: None)
    monkeypatch.setattr(
        api,
        "start_codex_login",
        lambda cwd: calls.append(cwd) or SimpleNamespace(pid=1234),
    )

    result = openai_connect_response()

    assert result["connected"] is False
    assert result["action"] == "login_started"
    assert result["pid"] == 1234
    assert calls == [api.PROJECT_ROOT]


def test_openai_connect_response_starts_proxy_when_auth_exists(monkeypatch, tmp_path):
    from backend import api
    from backend.api import openai_connect_response

    calls = []
    monkeypatch.setattr(
        api,
        "check_openai_oauth_proxy",
        lambda: SimpleNamespace(connected=False, message="offline", models=[]),
    )
    monkeypatch.setattr(api, "find_existing_auth_file", lambda: tmp_path / "auth.json")
    monkeypatch.setattr(
        api,
        "start_openai_oauth_proxy",
        lambda cwd: calls.append(cwd) or SimpleNamespace(pid=5678),
    )

    result = openai_connect_response()

    assert result["connected"] is False
    assert result["action"] == "proxy_started"
    assert result["pid"] == 5678
    assert calls == [api.PROJECT_ROOT]
