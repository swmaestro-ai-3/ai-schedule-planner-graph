from __future__ import annotations

import math
from datetime import date, datetime, timedelta

from planner.models import (
    BlockType,
    DayPlanInput,
    DraftPlan,
    FreeBlock,
    NormalizedFixedEvent,
    ScheduleItem,
    ScheduleItemType,
    Task,
    UnassignedReasonCode,
    UnassignedTask,
)
from planner.ranking import calculate_task_score


def compute_free_blocks(
    day_start_offset: int,
    day_end_offset: int,
    normalized_events: list[NormalizedFixedEvent],
    availability_blocks: list[FreeBlock] | None = None,
) -> list[FreeBlock]:
    blocks: list[FreeBlock] = []
    availability_blocks = availability_blocks or [
        FreeBlock(
            id="free-window-1",
            day_offset=0,
            start_offset=day_start_offset,
            end_offset=day_end_offset,
        )
    ]
    sorted_windows = sorted(
        availability_blocks,
        key=lambda block: (block.day_offset, block.start_offset),
    )
    sorted_events = sorted(
        normalized_events,
        key=lambda event: (event.day_offset, event.start_offset),
    )

    for window in sorted_windows:
        cursor = window.start_offset
        events_for_day = (
            event for event in sorted_events if event.day_offset == window.day_offset
        )
        for event in events_for_day:
            reserved_start = max(
                window.start_offset,
                event.start_offset - event.buffer_before_minutes,
            )
            reserved_end = min(
                window.end_offset,
                event.end_offset + event.buffer_after_minutes,
            )
            if reserved_end <= cursor or reserved_start >= window.end_offset:
                continue
            if reserved_start > cursor:
                blocks.append(
                    FreeBlock(
                        id=f"free-{len(blocks) + 1}",
                        day_offset=window.day_offset,
                        start_offset=cursor,
                        end_offset=reserved_start,
                    )
                )
            cursor = max(cursor, reserved_end)

        if cursor < window.end_offset:
            blocks.append(
                FreeBlock(
                    id=f"free-{len(blocks) + 1}",
                    day_offset=window.day_offset,
                    start_offset=cursor,
                    end_offset=window.end_offset,
                )
            )

    return blocks


def classify_free_block(
    block: FreeBlock,
    min_task_block_minutes: int = 30,
    deep_work_threshold_minutes: int = 90,
) -> BlockType:
    if block.duration_minutes < min_task_block_minutes:
        return BlockType.BUFFER
    if block.duration_minutes < deep_work_threshold_minutes:
        return BlockType.LIGHT_WORK
    return BlockType.DEEP_WORK


def classify_free_blocks(
    blocks: list[FreeBlock],
    min_task_block_minutes: int = 30,
    deep_work_threshold_minutes: int = 90,
) -> list[FreeBlock]:
    return [
        block.model_copy(
            update={
                "block_type": classify_free_block(
                    block,
                    min_task_block_minutes=min_task_block_minutes,
                    deep_work_threshold_minutes=deep_work_threshold_minutes,
                )
            }
        )
        for block in blocks
    ]


def calculate_buffer_target(total_free_minutes: int, buffer_ratio: float) -> int:
    return math.ceil(total_free_minutes * buffer_ratio)


def calculate_auto_buffer_minutes(blocks: list[FreeBlock]) -> int:
    return sum(
        block.duration_minutes
        for block in blocks
        if block.block_type == BlockType.BUFFER
    )


def _remaining_free_minutes(blocks: list[FreeBlock]) -> int:
    return sum(block.duration_minutes for block in blocks)


def _task_minutes_by_day(draft_plan: DraftPlan) -> dict[int, int]:
    totals: dict[int, int] = {}
    for item in draft_plan.schedule_items:
        if item.type != ScheduleItemType.TASK:
            continue
        totals[item.day_offset] = totals.get(item.day_offset, 0) + item.duration_minutes
    return totals


def _task_sort_key(task: Task, plan_input: DayPlanInput) -> tuple[int, int, int]:
    deadline_score = 0
    if task.deadline is not None:
        deadline_date = (
            task.deadline.date() if hasattr(task.deadline, "date") else task.deadline
        )
        days_until = (deadline_date - plan_input.date).days
        deadline_score = 100 - max(0, days_until)
    return (1 if task.hard_deadline else 0, task.priority, deadline_score)


def _as_date(value: date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def _task_day_bounds(task: Task, plan_input: DayPlanInput) -> tuple[int, int]:
    start_date = task.start_date or plan_input.date
    end_date = task.end_date or _as_date(task.deadline) or plan_input.date + timedelta(days=6)
    return (
        max(0, (start_date - plan_input.date).days),
        min(6, (end_date - plan_input.date).days),
    )


def _block_matches_task_date_range(
    block: FreeBlock,
    task: Task,
    plan_input: DayPlanInput,
) -> bool:
    start_day, end_day = _task_day_bounds(task, plan_input)
    return start_day <= block.day_offset <= end_day


def _append_unassigned(
    draft_plan: DraftPlan,
    task: Task,
    reason_code: UnassignedReasonCode,
) -> None:
    reasons = {
        UnassignedReasonCode.NO_AVAILABLE_BLOCK: "들어갈 수 있는 free block이 없습니다.",
        UnassignedReasonCode.INSUFFICIENT_TIME: "총 작업 시간이 가용 시간을 초과합니다.",
        UnassignedReasonCode.MISSING_DURATION: "예상 소요 시간이 없습니다.",
        UnassignedReasonCode.MIN_CHUNK_TOO_LARGE: "분할 최소 단위보다 작은 block만 존재합니다.",
        UnassignedReasonCode.BUFFER_PROTECTION: "buffer 확보를 위해 배치하지 않았습니다.",
        UnassignedReasonCode.DEADLINE_NOT_FEASIBLE: "마감 전 배치할 수 없습니다.",
    }
    draft_plan.unassigned_tasks.append(
        UnassignedTask(
            task=task,
            reason_code=reason_code,
            reason=reasons[reason_code],
        )
    )


def _make_task_item(
    task: Task,
    start_offset: int,
    end_offset: int,
    block_type: BlockType | None,
    title: str | None = None,
    day_offset: int = 0,
) -> ScheduleItem:
    return ScheduleItem(
        type=ScheduleItemType.TASK,
        title=title or task.title,
        start_offset=start_offset,
        end_offset=end_offset,
        day_offset=day_offset,
        source_id=task.id,
        block_type=block_type,
        reason=_placement_reason(task, block_type),
    )


def _make_snoozed_task_item(task: Task, day_offset: int) -> ScheduleItem:
    assert task.estimated_minutes is not None
    return ScheduleItem(
        type=ScheduleItemType.TASK,
        title=task.title,
        start_offset=0,
        end_offset=task.estimated_minutes,
        day_offset=max(1, min(day_offset, 6)),
        source_id=task.id,
        block_type=BlockType.DEEP_WORK
        if task.estimated_minutes >= 90
        else BlockType.LIGHT_WORK,
        reason=f"사용자 피드백으로 {max(1, min(day_offset, 6))}일 뒤로 스누즈했습니다.",
    )


def _placement_reason(task: Task, block_type: BlockType | None) -> str:
    if task.deadline is not None:
        return "마감일과 우선순위를 고려해 배치했습니다."
    if block_type == BlockType.DEEP_WORK:
        return "긴 집중 블록에 적합합니다."
    if block_type == BlockType.LIGHT_WORK:
        return "짧은 작업 블록에 적합합니다."
    return "가용 시간에 맞춰 배치했습니다."


def _consume_block(block: FreeBlock, minutes: int) -> tuple[FreeBlock | None, int, int]:
    start = block.start_offset
    end = start + minutes
    remaining = block.end_offset - end
    if remaining <= 0:
        return None, start, end
    block_type = block.block_type
    if remaining < 30:
        block_type = BlockType.BUFFER
    return (
        FreeBlock(
            id=block.id,
            day_offset=block.day_offset,
            start_offset=end,
            end_offset=block.end_offset,
            block_type=block_type,
        ),
        start,
        end,
    )


def _find_best_block(
    task: Task,
    blocks: list[FreeBlock],
    plan_input: DayPlanInput,
    day_task_minutes: dict[int, int],
) -> FreeBlock | None:
    candidates = [
        block
        for block in blocks
        if block.block_type != BlockType.BUFFER
        and task.estimated_minutes is not None
        and block.duration_minutes >= task.estimated_minutes
        and _block_matches_task_date_range(block, task, plan_input)
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda block: (
            -day_task_minutes.get(block.day_offset, 0),
            calculate_task_score(task, block, plan_input.date),
            -block.day_offset,
            -block.start_offset,
        ),
    )


def _add_remaining_blocks_as_buffers(
    draft_plan: DraftPlan,
    blocks: list[FreeBlock],
) -> None:
    for block in blocks:
        if block.duration_minutes <= 0:
            continue
        draft_plan.schedule_items.append(
            ScheduleItem(
                type=ScheduleItemType.BUFFER
                if block.block_type == BlockType.BUFFER
                else ScheduleItemType.FREE,
                title="Buffer" if block.block_type == BlockType.BUFFER else "Free",
                start_offset=block.start_offset,
                end_offset=block.end_offset,
                day_offset=block.day_offset,
                block_type=block.block_type,
                reason="계획 여유 시간입니다.",
            )
        )


def place_tasks(
    plan_input: DayPlanInput,
    classified_blocks: list[FreeBlock],
    ranked_tasks: list[Task] | None = None,
    normalized_events: list[NormalizedFixedEvent] | None = None,
    snoozed_task_days: dict[str, int] | None = None,
) -> DraftPlan:
    blocks = [block.model_copy() for block in classified_blocks]
    total_free_minutes = _remaining_free_minutes(blocks)
    target_buffer_minutes = calculate_buffer_target(
        total_free_minutes, plan_input.buffer_ratio
    )
    draft_plan = DraftPlan(
        free_blocks=blocks,
        target_buffer_minutes=target_buffer_minutes,
    )

    for event in normalized_events or []:
        draft_plan.schedule_items.append(
            ScheduleItem(
                type=ScheduleItemType.FIXED_EVENT,
                title=event.title,
                start_offset=event.start_offset,
                end_offset=event.end_offset,
                source_id=event.id,
                reason="고정 일정입니다.",
            )
        )

    tasks = ranked_tasks or sorted(
        plan_input.tasks,
        key=lambda task: _task_sort_key(task, plan_input),
        reverse=True,
    )
    snoozed_task_days = snoozed_task_days or {}

    for task in tasks:
        if task.estimated_minutes is None:
            _append_unassigned(draft_plan, task, UnassignedReasonCode.MISSING_DURATION)
            continue
        if task.id in snoozed_task_days:
            draft_plan.schedule_items.append(
                _make_snoozed_task_item(task, snoozed_task_days[task.id])
            )
            continue
        if task.splittable:
            _place_splittable_task(draft_plan, task, blocks, plan_input)
        else:
            _place_non_splittable_task(draft_plan, task, blocks, plan_input)

    _add_remaining_blocks_as_buffers(draft_plan, blocks)
    draft_plan.schedule_items = sorted(
        draft_plan.schedule_items,
        key=lambda item: (item.day_offset, item.start_offset, item.end_offset, item.type.value),
    )
    draft_plan.free_blocks = blocks
    return draft_plan


def _place_non_splittable_task(
    draft_plan: DraftPlan,
    task: Task,
    blocks: list[FreeBlock],
    plan_input: DayPlanInput,
) -> None:
    block = _find_best_block(task, blocks, plan_input, _task_minutes_by_day(draft_plan))
    if block is None:
        _append_unassigned(draft_plan, task, UnassignedReasonCode.NO_AVAILABLE_BLOCK)
        return

    remaining_after = _remaining_free_minutes(blocks) - task.estimated_minutes
    if remaining_after < draft_plan.target_buffer_minutes:
        _append_unassigned(draft_plan, task, UnassignedReasonCode.BUFFER_PROTECTION)
        return

    index = blocks.index(block)
    new_block, start, end = _consume_block(block, task.estimated_minutes)
    if new_block is None:
        blocks.pop(index)
    else:
        blocks[index] = new_block
    draft_plan.schedule_items.append(
        _make_task_item(
            task,
            start,
            end,
            block.block_type,
            day_offset=block.day_offset,
        )
    )


def _place_splittable_task(
    draft_plan: DraftPlan,
    task: Task,
    blocks: list[FreeBlock],
    plan_input: DayPlanInput,
) -> None:
    assert task.estimated_minutes is not None
    remaining_minutes = task.estimated_minutes
    planned_chunks: list[tuple[int, int, int, BlockType | None]] = []
    local_blocks = [block.model_copy() for block in blocks]

    while remaining_minutes > 0:
        day_task_minutes = _task_minutes_by_day(draft_plan)
        for day_offset, start, end, _block_type in planned_chunks:
            day_task_minutes[day_offset] = (
                day_task_minutes.get(day_offset, 0) + end - start
            )
        usable_blocks = [
            block
            for block in local_blocks
            if block.block_type != BlockType.BUFFER
            and block.duration_minutes >= min(task.min_chunk_minutes, remaining_minutes)
            and _block_matches_task_date_range(block, task, plan_input)
        ]
        if not usable_blocks:
            reason = (
                UnassignedReasonCode.MIN_CHUNK_TOO_LARGE
                if _remaining_free_minutes(local_blocks) >= remaining_minutes
                else UnassignedReasonCode.INSUFFICIENT_TIME
            )
            _append_unassigned(draft_plan, task, reason)
            return

        block = max(
            usable_blocks,
            key=lambda candidate: (
                -day_task_minutes.get(candidate.day_offset, 0),
                calculate_task_score(task, candidate, plan_input.date),
                -candidate.day_offset,
                -candidate.start_offset,
            ),
        )
        chunk_minutes = min(block.duration_minutes, remaining_minutes)
        index = local_blocks.index(block)
        new_block, start, end = _consume_block(block, chunk_minutes)
        if new_block is None:
            local_blocks.pop(index)
        else:
            local_blocks[index] = new_block
        planned_chunks.append((block.day_offset, start, end, block.block_type))
        remaining_minutes -= chunk_minutes

    if _remaining_free_minutes(local_blocks) < draft_plan.target_buffer_minutes:
        _append_unassigned(draft_plan, task, UnassignedReasonCode.BUFFER_PROTECTION)
        return

    blocks[:] = local_blocks
    chunk_count = len(planned_chunks)
    for index, (day_offset, start, end, block_type) in enumerate(planned_chunks, start=1):
        title = task.title if chunk_count == 1 else f"{task.title} ({index}/{chunk_count})"
        draft_plan.schedule_items.append(
            _make_task_item(
                task,
                start,
                end,
                block_type,
                title=title,
                day_offset=day_offset,
            )
        )
