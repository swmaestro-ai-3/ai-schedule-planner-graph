from datetime import date, time

from planner.models import (
    BlockType,
    DayPlanInput,
    FixedEvent,
    FocusType,
    FreeBlock,
    NormalizedFixedEvent,
    ScheduleItemType,
    Task,
    UnassignedReasonCode,
)
from planner.scheduler import place_tasks


def make_plan(tasks, *, buffer_ratio=0.0):
    return DayPlanInput(
        date=date(2026, 6, 3),
        day_start=time(9, 0),
        day_end=time(23, 0),
        fixed_events=[],
        tasks=tasks,
        buffer_ratio=buffer_ratio,
    )


def test_university_scenario_places_today_deadline_before_vocab():
    algorithm = Task(
        id="algorithm",
        title="알고리즘 과제",
        estimated_minutes=120,
        priority=5,
        deadline=date(2026, 6, 3),
        splittable=True,
        focus_type=FocusType.DEEP,
    )
    vocab = Task(
        id="vocab",
        title="영어 단어 암기",
        estimated_minutes=30,
        priority=2,
        splittable=True,
        focus_type=FocusType.LIGHT,
    )

    draft = place_tasks(
        make_plan([vocab, algorithm]),
        [
            FreeBlock(id="b1", start_offset=180, end_offset=360, block_type=BlockType.DEEP_WORK),
            FreeBlock(id="b2", start_offset=360, end_offset=420, block_type=BlockType.LIGHT_WORK),
        ],
    )

    task_items = [item for item in draft.schedule_items if item.type == ScheduleItemType.TASK]
    assert task_items[0].source_id == "algorithm"
    assert task_items[1].source_id == "vocab"


def test_splittable_task_can_use_two_blocks():
    task = Task(
        id="essay",
        title="과제 작성",
        estimated_minutes=120,
        priority=4,
        splittable=True,
        min_chunk_minutes=45,
        focus_type=FocusType.DEEP,
    )

    draft = place_tasks(
        make_plan([task]),
        [
            FreeBlock(id="b1", start_offset=0, end_offset=60, block_type=BlockType.LIGHT_WORK),
            FreeBlock(id="b2", start_offset=120, end_offset=180, block_type=BlockType.LIGHT_WORK),
        ],
    )

    task_items = [item for item in draft.schedule_items if item.type == ScheduleItemType.TASK]
    assert [item.title for item in task_items] == ["과제 작성 (1/2)", "과제 작성 (2/2)"]
    assert [item.duration_minutes for item in task_items] == [60, 60]


def test_non_splittable_deep_task_without_large_block_is_unassigned():
    task = Task(
        id="deep-task",
        title="핵심 설계",
        estimated_minutes=120,
        priority=5,
        splittable=False,
        focus_type=FocusType.DEEP,
    )

    draft = place_tasks(
        make_plan([task]),
        [FreeBlock(id="b1", start_offset=0, end_offset=80, block_type=BlockType.LIGHT_WORK)],
    )

    assert draft.unassigned_tasks[0].task.id == "deep-task"
    assert draft.unassigned_tasks[0].reason_code == UnassignedReasonCode.NO_AVAILABLE_BLOCK


def test_lower_priority_task_is_unassigned_when_time_is_insufficient():
    high = Task(
        id="high",
        title="중요 작업",
        estimated_minutes=60,
        priority=5,
        splittable=False,
    )
    low = Task(
        id="low",
        title="낮은 우선순위 작업",
        estimated_minutes=60,
        priority=1,
        splittable=False,
    )

    draft = place_tasks(
        make_plan([low, high]),
        [FreeBlock(id="b1", start_offset=0, end_offset=60, block_type=BlockType.LIGHT_WORK)],
    )

    assert [item.source_id for item in draft.schedule_items if item.type == ScheduleItemType.TASK] == ["high"]
    assert draft.unassigned_tasks[0].task.id == "low"


def test_buffer_protection_can_leave_low_priority_task_unassigned():
    task = Task(
        id="low",
        title="낮은 우선순위 작업",
        estimated_minutes=60,
        priority=1,
        splittable=False,
    )

    draft = place_tasks(
        make_plan([task], buffer_ratio=0.5),
        [FreeBlock(id="b1", start_offset=0, end_offset=60, block_type=BlockType.LIGHT_WORK)],
    )

    assert draft.unassigned_tasks[0].reason_code == UnassignedReasonCode.BUFFER_PROTECTION


def test_schedule_contains_fixed_task_and_buffer_items_in_order():
    task = Task(
        id="review",
        title="코드 리뷰",
        estimated_minutes=30,
        priority=3,
        splittable=False,
        focus_type=FocusType.LIGHT,
    )
    fixed_event = NormalizedFixedEvent(
        id="meeting",
        title="회의",
        start_offset=60,
        end_offset=120,
    )

    draft = place_tasks(
        make_plan([task]),
        [
            FreeBlock(id="b1", start_offset=0, end_offset=30, block_type=BlockType.LIGHT_WORK),
            FreeBlock(id="b2", start_offset=30, end_offset=45, block_type=BlockType.BUFFER),
        ],
        normalized_events=[fixed_event],
    )

    item_types = [item.type for item in draft.schedule_items]
    assert item_types == [
        ScheduleItemType.TASK,
        ScheduleItemType.BUFFER,
        ScheduleItemType.FIXED_EVENT,
    ]
