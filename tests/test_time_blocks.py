from planner.models import BlockType, FreeBlock, NormalizedFixedEvent
from planner.scheduler import (
    calculate_auto_buffer_minutes,
    calculate_buffer_target,
    classify_free_block,
    classify_free_blocks,
    compute_free_blocks,
)


def test_day_without_fixed_events_is_one_free_block():
    blocks = compute_free_blocks(0, 840, [])

    assert [(block.start_offset, block.end_offset) for block in blocks] == [(0, 840)]


def test_fixed_events_create_free_blocks_between_events():
    blocks = compute_free_blocks(
        0,
        840,
        [
            NormalizedFixedEvent(
                id="class-1",
                title="전공 수업",
                start_offset=60,
                end_offset=180,
            ),
            NormalizedFixedEvent(
                id="meeting-1",
                title="팀플 회의",
                start_offset=300,
                end_offset=360,
            ),
        ],
    )

    assert [(block.start_offset, block.end_offset) for block in blocks] == [
        (0, 60),
        (180, 300),
        (360, 840),
    ]


def test_classifies_blocks_by_duration():
    assert classify_free_block(FreeBlock(id="b1", start_offset=0, end_offset=20)) == BlockType.BUFFER
    assert classify_free_block(FreeBlock(id="b2", start_offset=0, end_offset=60)) == BlockType.LIGHT_WORK
    assert classify_free_block(FreeBlock(id="b3", start_offset=0, end_offset=120)) == BlockType.DEEP_WORK


def test_classify_free_blocks_preserves_offsets_and_sets_type():
    blocks = classify_free_blocks(
        [
            FreeBlock(id="b1", start_offset=0, end_offset=20),
            FreeBlock(id="b2", start_offset=20, end_offset=80),
        ]
    )

    assert blocks[0].block_type == BlockType.BUFFER
    assert blocks[1].block_type == BlockType.LIGHT_WORK


def test_calculates_target_and_auto_buffer_minutes():
    blocks = [
        FreeBlock(id="b1", start_offset=0, end_offset=20, block_type=BlockType.BUFFER),
        FreeBlock(id="b2", start_offset=20, end_offset=80, block_type=BlockType.LIGHT_WORK),
    ]

    assert calculate_buffer_target(total_free_minutes=420, buffer_ratio=0.1) == 42
    assert calculate_auto_buffer_minutes(blocks) == 20
