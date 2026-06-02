from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from planner.models import DayPlanInput, ReplanConstraints, ValidationIssue


class LLMParserError(RuntimeError):
    pass


SidecarCallable = Callable[[dict[str, Any]], dict[str, Any]]


def call_llm_sidecar(
    payload: dict[str, Any],
    command: list[str] | None = None,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    sidecar_command = command or ["node", "llm_sidecar/openai_oauth_client.mjs"]
    completed = subprocess.run(
        sidecar_command,
        cwd=root,
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=True,
    )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise LLMParserError("Sidecar returned invalid JSON") from exc


def parse_natural_language_input(
    raw_text: str,
    sidecar: SidecarCallable = call_llm_sidecar,
    max_retries: int = 2,
) -> DayPlanInput:
    last_error: Exception | None = None
    for _ in range(max_retries):
        try:
            response = sidecar(
                {
                    "task": "parse_day_plan",
                    "input": raw_text,
                }
            )
            return DayPlanInput.model_validate(response.get("day_plan", response))
        except (ValidationError, LLMParserError, json.JSONDecodeError) as exc:
            last_error = exc
    raise LLMParserError("Structured input is required") from last_error


def build_clarification_questions(errors: list[ValidationIssue]) -> list[str]:
    questions: list[str] = []
    for error in errors:
        if error.code in {"MISSING_DATE", "date"}:
            questions.append("계획할 날짜를 알려주세요.")
        elif error.code in {"MISSING_DAY_START", "day_start"}:
            questions.append("하루 시작 시간을 알려주세요.")
        elif error.code in {"MISSING_DAY_END", "day_end"}:
            questions.append("하루 종료 시간을 알려주세요.")
        elif error.code == "MISSING_DURATION":
            questions.append("작업의 예상 소요 시간을 알려주세요.")
        else:
            questions.append(error.message)
    return questions


def interpret_rejection_reason(
    reason: str,
    current_state: dict[str, Any] | None = None,
) -> ReplanConstraints:
    constraints = ReplanConstraints(notes=[reason])
    if "빡빡" in reason or "여유" in reason:
        constraints.buffer_ratio_delta = 0.1
    if "회의 직후" in reason or "직후에는 쉬" in reason:
        constraints.fixed_event_buffer_after = 15
    if "오늘 안 해도" in reason:
        constraints.notes.append("사용자가 일부 작업 제외를 요청했습니다.")
    return constraints
