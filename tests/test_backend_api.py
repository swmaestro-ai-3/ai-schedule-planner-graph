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
