from __future__ import annotations

import math

from planner.models import (
    BlockType,
    FreeBlock,
    NormalizedFixedEvent,
)


def compute_free_blocks(
    day_start_offset: int,
    day_end_offset: int,
    normalized_events: list[NormalizedFixedEvent],
) -> list[FreeBlock]:
    blocks: list[FreeBlock] = []
    cursor = day_start_offset
    sorted_events = sorted(normalized_events, key=lambda event: event.start_offset)

    for event in sorted_events:
        if event.start_offset > cursor:
            blocks.append(
                FreeBlock(
                    id=f"free-{len(blocks) + 1}",
                    start_offset=cursor,
                    end_offset=event.start_offset,
                )
            )
        cursor = max(cursor, event.end_offset)

    if cursor < day_end_offset:
        blocks.append(
            FreeBlock(
                id=f"free-{len(blocks) + 1}",
                start_offset=cursor,
                end_offset=day_end_offset,
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
