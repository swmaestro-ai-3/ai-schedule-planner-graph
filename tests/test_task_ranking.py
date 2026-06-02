from datetime import date

from planner.models import BlockType, FocusType, FreeBlock, Task
from planner.ranking import (
    calculate_deadline_score,
    calculate_fit_score,
    calculate_focus_score,
    calculate_split_penalty,
    calculate_task_score,
    rank_task_candidates,
)


def test_priority_score_multiplies_priority_by_100():
    task = Task(
        id="task-1",
        title="알고리즘 과제",
        estimated_minutes=60,
        priority=5,
        splittable=True,
    )
    block = FreeBlock(id="b1", start_offset=0, end_offset=60, block_type=BlockType.LIGHT_WORK)

    assert calculate_task_score(task, block, date(2026, 6, 3)) >= 500


def test_today_deadline_scores_higher_than_no_deadline():
    today_task = Task(
        id="today",
        title="오늘 마감",
        estimated_minutes=60,
        priority=3,
        deadline=date(2026, 6, 3),
        splittable=True,
    )
    no_deadline_task = Task(
        id="none",
        title="마감 없음",
        estimated_minutes=60,
        priority=3,
        splittable=True,
    )

    assert calculate_deadline_score(today_task, date(2026, 6, 3)) == 80
    assert calculate_deadline_score(no_deadline_task, date(2026, 6, 3)) == 0


def test_focus_score_rewards_matching_block_type():
    task = Task(
        id="task-1",
        title="설계 문서 작성",
        estimated_minutes=120,
        priority=4,
        splittable=False,
        focus_type=FocusType.DEEP,
    )
    block = FreeBlock(id="b1", start_offset=0, end_offset=120, block_type=BlockType.DEEP_WORK)

    assert calculate_focus_score(task, block) == 20


def test_fit_score_rewards_task_that_fits_block():
    task = Task(
        id="task-1",
        title="리뷰",
        estimated_minutes=120,
        priority=3,
        splittable=True,
    )
    block = FreeBlock(id="b1", start_offset=0, end_offset=120, block_type=BlockType.DEEP_WORK)

    assert calculate_fit_score(task, block) == 10


def test_split_penalty_grows_with_chunk_count():
    assert calculate_split_penalty(3) > calculate_split_penalty(1)


def test_rank_task_candidates_prefers_higher_scoring_pair():
    deep_task = Task(
        id="deep",
        title="알고리즘 과제",
        estimated_minutes=120,
        priority=5,
        deadline=date(2026, 6, 3),
        splittable=True,
        focus_type=FocusType.DEEP,
    )
    light_task = Task(
        id="light",
        title="영어 단어 암기",
        estimated_minutes=30,
        priority=2,
        splittable=True,
        focus_type=FocusType.LIGHT,
    )
    blocks = [
        FreeBlock(id="b1", start_offset=0, end_offset=120, block_type=BlockType.DEEP_WORK),
        FreeBlock(id="b2", start_offset=120, end_offset=180, block_type=BlockType.LIGHT_WORK),
    ]

    candidates = rank_task_candidates([light_task, deep_task], blocks, date(2026, 6, 3))

    assert candidates[0].task.id == "deep"
    assert candidates[0].block.id == "b1"
