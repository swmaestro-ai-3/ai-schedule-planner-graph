from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, computed_field


class BlockType(str, Enum):
    DEEP_WORK = "deep_work"
    LIGHT_WORK = "light_work"
    BUFFER = "buffer"


class FocusType(str, Enum):
    DEEP = "deep"
    LIGHT = "light"
    ANY = "any"


class ScheduleItemType(str, Enum):
    FIXED_EVENT = "fixed_event"
    TASK = "task"
    BUFFER = "buffer"
    FREE = "free"


class FeasibilityStatus(str, Enum):
    FEASIBLE = "feasible"
    TIGHT = "tight"
    OVERLOADED = "overloaded"
    INVALID_INPUT = "invalid_input"


class UnassignedReasonCode(str, Enum):
    NO_AVAILABLE_BLOCK = "NO_AVAILABLE_BLOCK"
    INSUFFICIENT_TIME = "INSUFFICIENT_TIME"
    MISSING_DURATION = "MISSING_DURATION"
    DEADLINE_NOT_FEASIBLE = "DEADLINE_NOT_FEASIBLE"
    MIN_CHUNK_TOO_LARGE = "MIN_CHUNK_TOO_LARGE"
    BUFFER_PROTECTION = "BUFFER_PROTECTION"


class TimeRange(BaseModel):
    start_time: time
    end_time: time


class AvailabilityWindow(BaseModel):
    id: str
    day_offset: int = Field(default=0, ge=0, le=6)
    start_time: time
    end_time: time


class FixedEvent(BaseModel):
    id: str
    title: str
    day_offset: int = Field(default=0, ge=0, le=6)
    start_time: time
    end_time: time
    category: str | None = None
    is_movable: bool = False
    buffer_before_minutes: int = Field(default=0, ge=0)
    buffer_after_minutes: int = Field(default=0, ge=0)


class Task(BaseModel):
    id: str
    title: str
    estimated_minutes: int | None = Field(default=None, gt=0)
    priority: int = Field(default=3, ge=1, le=5)
    start_date: date | None = None
    end_date: date | None = None
    deadline: date | datetime | None = None
    splittable: bool
    min_chunk_minutes: int = Field(default=30, gt=0)
    focus_type: FocusType = FocusType.ANY
    preferred_window: list[TimeRange] = Field(default_factory=list)
    hard_deadline: bool = False


class DayPlanInput(BaseModel):
    date: date
    timezone: str = "Asia/Seoul"
    day_start: time
    day_end: time
    availability_windows: list[AvailabilityWindow] = Field(default_factory=list)
    fixed_events: list[FixedEvent]
    tasks: list[Task]
    buffer_ratio: float = Field(default=0.1, ge=0, le=1)
    min_task_block_minutes: int = Field(default=30, gt=0)
    deep_work_threshold_minutes: int = Field(default=90, gt=0)


class NormalizedFixedEvent(BaseModel):
    id: str
    title: str
    day_offset: int = 0
    start_offset: int
    end_offset: int
    category: str | None = None
    buffer_before_minutes: int = 0
    buffer_after_minutes: int = 0

    @computed_field
    @property
    def duration_minutes(self) -> int:
        return self.end_offset - self.start_offset


class NormalizedTask(Task):
    pass


class FreeBlock(BaseModel):
    id: str
    day_offset: int = 0
    start_offset: int
    end_offset: int
    block_type: BlockType | None = None

    @computed_field
    @property
    def duration_minutes(self) -> int:
        return self.end_offset - self.start_offset


class ScheduleItem(BaseModel):
    type: ScheduleItemType
    title: str
    start_offset: int
    end_offset: int
    day_offset: int = Field(default=0, ge=0, le=6)
    source_id: str | None = None
    block_type: BlockType | None = None
    reason: str = ""
    warning_codes: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def duration_minutes(self) -> int:
        return self.end_offset - self.start_offset


class ValidationIssue(BaseModel):
    code: str
    message: str
    blocking: bool = False
    source_id: str | None = None
    source_type: str | None = None


class BufferSummary(BaseModel):
    target_minutes: int = 0
    secured_minutes: int = 0

    @computed_field
    @property
    def shortage_minutes(self) -> int:
        return max(0, self.target_minutes - self.secured_minutes)


class UnassignedTask(BaseModel):
    task: Task
    reason_code: UnassignedReasonCode
    reason: str


class DraftPlan(BaseModel):
    schedule_items: list[ScheduleItem] = Field(default_factory=list)
    unassigned_tasks: list[UnassignedTask] = Field(default_factory=list)
    free_blocks: list[FreeBlock] = Field(default_factory=list)
    target_buffer_minutes: int = 0


class ValidationResult(BaseModel):
    issues: list[ValidationIssue] = Field(default_factory=list)
    buffer_summary: BufferSummary = Field(default_factory=BufferSummary)

    @computed_field
    @property
    def has_blocking_issues(self) -> bool:
        return any(issue.blocking for issue in self.issues)


class FinalPlanOutput(BaseModel):
    schedule_items: list[ScheduleItem] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
    unassigned_tasks: list[UnassignedTask] = Field(default_factory=list)
    buffer_summary: BufferSummary = Field(default_factory=BufferSummary)
    feasibility_status: FeasibilityStatus = FeasibilityStatus.FEASIBLE
    explanation: str = ""
    approval_required: bool = True


class ReplanConstraints(BaseModel):
    buffer_ratio_delta: float = 0.0
    excluded_task_ids: list[str] = Field(default_factory=list)
    excluded_fixed_event_ids: list[str] = Field(default_factory=list)
    additional_tasks: list[Task] = Field(default_factory=list)
    additional_fixed_events: list[FixedEvent] = Field(default_factory=list)
    task_updates: dict[str, dict[str, Any]] = Field(default_factory=dict)
    fixed_event_updates: dict[str, dict[str, Any]] = Field(default_factory=dict)
    availability_overrides: list[AvailabilityWindow] = Field(default_factory=list)
    task_day_offsets: dict[str, int] = Field(default_factory=dict)
    preferred_windows: dict[str, str] = Field(default_factory=dict)
    duration_multipliers: dict[str, float] = Field(default_factory=dict)
    fixed_event_buffer_after: int = 0
    snoozed_task_days: dict[str, int] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


JsonDict = dict[str, Any]
