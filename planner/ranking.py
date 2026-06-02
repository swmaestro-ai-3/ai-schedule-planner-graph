from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from planner.models import BlockType, FocusType, FreeBlock, Task


@dataclass(frozen=True)
class TaskCandidate:
    task: Task
    block: FreeBlock
    score: int
    chunk_count: int = 1


def _deadline_date(task: Task) -> date | None:
    if task.deadline is None:
        return None
    if isinstance(task.deadline, datetime):
        return task.deadline.date()
    return task.deadline


def calculate_deadline_score(task: Task, plan_date: date) -> int:
    deadline = _deadline_date(task)
    if deadline is None:
        return 0
    days_until = (deadline - plan_date).days
    if days_until <= 0:
        return 80
    if days_until == 1:
        return 50
    if days_until <= 3:
        return 30
    return 0


def calculate_focus_score(task: Task, block: FreeBlock) -> int:
    if task.focus_type == FocusType.ANY:
        return 0
    if task.focus_type == FocusType.DEEP and block.block_type == BlockType.DEEP_WORK:
        return 20
    if task.focus_type == FocusType.LIGHT and block.block_type == BlockType.LIGHT_WORK:
        return 20
    return 0


def calculate_fit_score(task: Task, block: FreeBlock) -> int:
    if task.estimated_minutes is None:
        return 0
    leftover = block.duration_minutes - task.estimated_minutes
    return 10 if 0 <= leftover <= 15 else 0


def calculate_split_penalty(chunk_count: int) -> int:
    return max(0, chunk_count - 1) * 5


def calculate_task_score(
    task: Task,
    block: FreeBlock,
    plan_date: date,
    chunk_count: int = 1,
) -> int:
    return (
        task.priority * 100
        + calculate_deadline_score(task, plan_date)
        + calculate_focus_score(task, block)
        + calculate_fit_score(task, block)
        - calculate_split_penalty(chunk_count)
    )


def rank_task_candidates(
    tasks: list[Task],
    blocks: list[FreeBlock],
    plan_date: date,
) -> list[TaskCandidate]:
    candidates: list[TaskCandidate] = []
    for task in tasks:
        if task.estimated_minutes is None:
            continue
        for block in blocks:
            if block.block_type == BlockType.BUFFER:
                continue
            if block.duration_minutes < min(task.estimated_minutes, task.min_chunk_minutes):
                continue
            score = calculate_task_score(task, block, plan_date)
            candidates.append(TaskCandidate(task=task, block=block, score=score))
    return sorted(
        candidates,
        key=lambda candidate: (
            candidate.score,
            candidate.block.duration_minutes,
            -candidate.task.estimated_minutes
            if candidate.task.estimated_minutes is not None
            else 0,
        ),
        reverse=True,
    )
