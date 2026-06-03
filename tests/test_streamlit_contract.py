from datetime import date, time
from pathlib import Path
from types import SimpleNamespace

from app import (
    availability_editor_column_labels,
    build_google_oauth_config,
    build_snooze_feedback_text,
    build_structured_input,
    calendar_week_dates,
    exportable_schedule_items,
    fixed_events_to_editor_rows,
    fixed_event_editor_column_labels,
    integration_button_labels,
    merge_fixed_event_rows,
    mvp_sidebar_integration_labels,
    schedule_change_summary,
    schedule_items_to_calendar_blocks,
    schedule_items_to_rows,
    schedule_items_to_week_calendar_blocks,
    should_show_openai_oauth_button,
    structured_input_editor_column_order,
    structured_input_action_labels,
    structured_input_summary_cards,
    structured_input_section_titles,
    task_editor_column_labels,
    validation_panel_rows,
    warning_summary_rows,
)
from planner.models import (
    BufferSummary,
    FinalPlanOutput,
    FixedEvent,
    ScheduleItem,
    ScheduleItemType,
    Task,
    UnassignedReasonCode,
    UnassignedTask,
    ValidationIssue,
)
from planner.openai_oauth import OpenAIOAuthStatus


def test_structured_input_adapter_builds_day_plan_input():
    plan_input = build_structured_input(
        plan_date=date(2026, 6, 3),
        day_start=time(9, 0),
        day_end=time(23, 0),
        buffer_ratio=0.1,
        availability_rows=[
            {
                "id": "available-1",
                "day_offset": 1,
                "start_time": time(13, 0),
                "end_time": time(16, 0),
            }
        ],
        fixed_event_rows=[
            {
                "id": "class-1",
                "title": "전공 수업",
                "start_time": time(10, 0),
                "end_time": time(12, 0),
                "category": "class",
            }
        ],
        task_rows=[
            {
                "id": "task-1",
                "title": "알고리즘 과제",
                "estimated_minutes": 120,
                "priority": 5,
                "start_date": date(2026, 6, 4),
                "end_date": date(2026, 6, 6),
                "splittable": True,
                "focus_type": "deep",
            }
        ],
    )

    assert plan_input.fixed_events[0].title == "전공 수업"
    assert plan_input.availability_windows[0].day_offset == 1
    assert plan_input.tasks[0].focus_type == "deep"
    assert plan_input.tasks[0].start_date == date(2026, 6, 4)
    assert plan_input.tasks[0].end_date == date(2026, 6, 6)


def test_structured_input_sections_are_user_facing():
    assert structured_input_section_titles() == [
        "계획 기준",
        "가용 시간",
        "고정 일정",
        "배치할 작업",
    ]


def test_structured_input_has_one_primary_action():
    assert structured_input_action_labels() == ["일정안 생성"]


def test_structured_editor_columns_use_user_facing_labels():
    assert fixed_event_editor_column_labels() == {
        "id": "ID",
        "title": "일정명",
        "start_time": "시작",
        "end_time": "종료",
        "category": "분류",
    }
    assert task_editor_column_labels() == {
        "id": "ID",
        "title": "작업명",
        "estimated_minutes": "소요(분)",
        "priority": "중요도",
        "start_date": "시작 날짜",
        "end_date": "종료 날짜",
        "splittable": "분할 가능",
        "focus_type": "집중도",
    }
    assert availability_editor_column_labels() == {
        "id": "ID",
        "day_offset": "요일",
        "start_time": "시작",
        "end_time": "종료",
    }


def test_structured_input_hides_technical_id_columns():
    assert structured_input_editor_column_order() == {
        "availability": ("day_offset", "start_time", "end_time"),
        "fixed_events": ("title", "start_time", "end_time", "category"),
        "tasks": (
            "title",
            "estimated_minutes",
            "priority",
            "start_date",
            "end_date",
            "focus_type",
            "splittable",
        ),
    }


def test_structured_input_summary_cards_are_scan_friendly():
    cards = structured_input_summary_cards(
        plan_date=date(2026, 6, 3),
        day_start=time(9, 0),
        day_end=time(23, 0),
        buffer_ratio=0.1,
        availability_rows=[{"day_offset": 0}, {"day_offset": 2}],
        fixed_event_rows=[{"title": "전공 수업"}],
        task_rows=[{"title": "알고리즘 과제"}, {"title": "영어 단어 암기"}],
    )

    assert cards == [
        {"label": "날짜", "value": "2026/06/03"},
        {"label": "운영 시간", "value": "09:00-23:00"},
        {"label": "가용", "value": "2개"},
        {"label": "여유", "value": "10%"},
        {"label": "입력", "value": "고정 1개 / 작업 2개"},
    ]


def test_build_snooze_feedback_text_is_machine_readable():
    assert build_snooze_feedback_text(
        task_id="algorithm",
        task_title="알고리즘 과제",
        days=2,
    ) == "snooze task_id=algorithm days=2 title=알고리즘 과제"


def test_schedule_items_to_rows_formats_offsets():
    rows = schedule_items_to_rows(
        [
            ScheduleItem(
                type=ScheduleItemType.TASK,
                title="알고리즘 과제",
                start_offset=180,
                end_offset=300,
                reason="오늘 마감입니다.",
            )
        ],
        day_start=time(9, 0),
    )

    assert rows == [
        {
            "time": "12:00~14:00",
            "type": "task",
            "title": "알고리즘 과제",
            "reason": "오늘 마감입니다.",
        }
    ]


def test_warning_summary_rows_includes_warnings_and_unassigned_tasks():
    task = Task(
        id="low",
        title="낮은 우선순위 작업",
        estimated_minutes=60,
        priority=1,
        splittable=False,
    )
    rows = warning_summary_rows(
        warnings=[
            ValidationIssue(
                code="BUFFER_SHORTAGE",
                message="Buffer가 부족합니다.",
            )
        ],
        unassigned_tasks=[
            UnassignedTask(
                task=task,
                reason_code=UnassignedReasonCode.NO_AVAILABLE_BLOCK,
                reason="들어갈 block이 없습니다.",
            )
        ],
    )

    assert rows == [
        {"code": "BUFFER_SHORTAGE", "message": "Buffer가 부족합니다."},
        {"code": "NO_AVAILABLE_BLOCK", "message": "낮은 우선순위 작업: 들어갈 block이 없습니다."},
    ]


def test_fixed_events_to_editor_rows_maps_google_calendar_events():
    rows = fixed_events_to_editor_rows(
        [
            FixedEvent(
                id="gcal-event-1",
                title="회의",
                start_time=time(10, 0),
                end_time=time(11, 0),
                category="google_calendar",
            )
        ]
    )

    assert rows == [
        {
            "id": "gcal-event-1",
            "title": "회의",
            "start_time": time(10, 0),
            "end_time": time(11, 0),
            "category": "google_calendar",
        }
    ]


def test_merge_fixed_event_rows_dedupes_by_id():
    rows = merge_fixed_event_rows(
        [
            {
                "id": "class-1",
                "title": "전공 수업",
                "start_time": time(10, 0),
                "end_time": time(12, 0),
                "category": "class",
            }
        ],
        [
            FixedEvent(
                id="class-1",
                title="중복",
                start_time=time(10, 0),
                end_time=time(12, 0),
            ),
            FixedEvent(
                id="gcal-event-1",
                title="회의",
                start_time=time(14, 0),
                end_time=time(15, 0),
            ),
        ],
    )

    assert [row["id"] for row in rows] == ["class-1", "gcal-event-1"]


def test_exportable_schedule_items_requires_approved_final_plan():
    item = ScheduleItem(
        type=ScheduleItemType.TASK,
        title="알고리즘 과제",
        start_offset=180,
        end_offset=300,
    )

    assert exportable_schedule_items({}) == []
    assert exportable_schedule_items({"draft_plan": object()}) == []
    assert exportable_schedule_items(
        {"final_plan": FinalPlanOutput(schedule_items=[item])}
    ) == [item]


def test_build_google_oauth_config_resolves_relative_token_file(tmp_path):
    config = build_google_oauth_config(
        env={
            "GOOGLE_OAUTH_CLIENT_ID": "client-id",
            "GOOGLE_OAUTH_CLIENT_SECRET": "secret",
            "GOOGLE_OAUTH_REDIRECT_URI": "http://localhost:8501",
            "GOOGLE_TOKEN_FILE": "tokens/google.json",
        },
        cwd=tmp_path,
    )

    assert config is not None
    assert config.client_id == "client-id"
    assert config.token_file == tmp_path / "tokens" / "google.json"
    assert build_google_oauth_config(env={}, cwd=Path("/tmp")) is None


def test_integration_button_labels_are_one_per_provider():
    assert integration_button_labels() == [
        "Google Calendar 연동",
        "OpenAI OAuth 연동",
    ]


def test_openai_oauth_button_hides_when_proxy_is_connected():
    assert (
        should_show_openai_oauth_button(
            OpenAIOAuthStatus(
                connected=True,
                message="connected",
                models=["gpt-5"],
            )
        )
        is False
    )
    assert (
        should_show_openai_oauth_button(
            OpenAIOAuthStatus(
                connected=False,
                message="not connected",
            )
        )
        is True
    )


def test_schedule_items_to_calendar_blocks_maps_position_and_size():
    blocks = schedule_items_to_calendar_blocks(
        [
            ScheduleItem(
                type=ScheduleItemType.FIXED_EVENT,
                title="전공 수업",
                start_offset=60,
                end_offset=180,
            ),
            ScheduleItem(
                type=ScheduleItemType.TASK,
                title="알고리즘 과제",
                start_offset=180,
                end_offset=300,
                reason="오늘 마감입니다.",
            ),
        ],
        day_start=time(9, 0),
        day_end=time(23, 0),
    )

    assert blocks[0] == {
        "top": 60,
        "height": 120,
        "time": "10:00~12:00",
        "type": "fixed_event",
        "title": "전공 수업",
        "reason": "",
    }
    assert blocks[1]["top"] == 180
    assert blocks[1]["height"] == 120
    assert blocks[1]["type"] == "task"


def test_schedule_items_to_week_calendar_blocks_keeps_day_offsets():
    blocks = schedule_items_to_week_calendar_blocks(
        [
            ScheduleItem(
                type=ScheduleItemType.TASK,
                title="알고리즘 과제",
                start_offset=0,
                end_offset=120,
                day_offset=1,
                reason="사용자 요청으로 스누즈했습니다.",
            )
        ],
        plan_date=date(2026, 6, 3),
        day_start=time(9, 0),
        day_end=time(23, 0),
    )

    assert blocks == [
        {
            "day_offset": 3,
            "date": "2026/06/04",
            "weekday": "Thu",
            "top": 0,
            "height": 120,
            "time": "09:00~11:00",
            "type": "task",
            "title": "알고리즘 과제",
            "reason": "사용자 요청으로 스누즈했습니다.",
        }
    ]


def test_week_calendar_blocks_treat_legacy_items_as_today():
    blocks = schedule_items_to_week_calendar_blocks(
        [
            SimpleNamespace(
                type=ScheduleItemType.TASK,
                title="레거시 작업",
                start_offset=60,
                end_offset=120,
                reason="기존 세션 데이터",
            )
        ],
        plan_date=date(2026, 6, 3),
        day_start=time(9, 0),
        day_end=time(23, 0),
    )

    assert blocks[0]["day_offset"] == 2
    assert blocks[0]["date"] == "2026/06/03"


def test_calendar_week_dates_are_monday_to_sunday_for_plan_date_week():
    assert [
        item.strftime("%Y/%m/%d")
        for item in calendar_week_dates(date(2026, 6, 3))
    ] == [
        "2026/06/01",
        "2026/06/02",
        "2026/06/03",
        "2026/06/04",
        "2026/06/05",
        "2026/06/06",
        "2026/06/07",
    ]


def test_week_calendar_blocks_skip_items_outside_current_monday_sunday_week():
    blocks = schedule_items_to_week_calendar_blocks(
        [
            ScheduleItem(
                type=ScheduleItemType.TASK,
                title="다음 주 작업",
                start_offset=0,
                end_offset=60,
                day_offset=6,
            )
        ],
        plan_date=date(2026, 6, 3),
        day_start=time(9, 0),
        day_end=time(23, 0),
    )

    assert blocks == []


def test_validation_panel_rows_summarizes_user_review_inputs():
    task = Task(
        id="low",
        title="낮은 우선순위 작업",
        estimated_minutes=60,
        priority=1,
        splittable=False,
    )
    rows = validation_panel_rows(
        {
            "warnings": [
                ValidationIssue(
                    code="BUFFER_SHORTAGE",
                    message="Buffer가 부족합니다.",
                )
            ],
            "unassigned_tasks": [
                UnassignedTask(
                    task=task,
                    reason_code=UnassignedReasonCode.NO_AVAILABLE_BLOCK,
                    reason="들어갈 block이 없습니다.",
                )
            ],
            "validation_result": type(
                "ValidationResultStub",
                (),
                {"buffer_summary": BufferSummary(target_minutes=42, secured_minutes=25)},
            )(),
        }
    )

    assert rows == [
        {"check": "buffer", "status": "부족", "detail": "목표 42분 / 확보 25분"},
        {"check": "warning", "status": "확인 필요", "detail": "Buffer가 부족합니다."},
        {
            "check": "unassigned",
            "status": "미배치",
            "detail": "낮은 우선순위 작업: 들어갈 block이 없습니다.",
        },
    ]


def test_schedule_change_summary_reports_moved_tasks():
    previous = [
        ScheduleItem(
            type=ScheduleItemType.TASK,
            title="알고리즘 과제",
            source_id="task-1",
            start_offset=60,
            end_offset=180,
        )
    ]
    current = [
        ScheduleItem(
            type=ScheduleItemType.TASK,
            title="알고리즘 과제",
            source_id="task-1",
            start_offset=180,
            end_offset=300,
        )
    ]

    assert schedule_change_summary(previous, current, day_start=time(9, 0)) == [
        {
            "task": "알고리즘 과제",
            "before": "10:00~12:00",
            "after": "12:00~14:00",
        }
    ]


def test_schedule_change_summary_reports_snoozed_tasks_with_dates():
    previous = [
        ScheduleItem(
            type=ScheduleItemType.TASK,
            title="알고리즘 과제",
            source_id="task-1",
            start_offset=180,
            end_offset=300,
        )
    ]
    current = [
        ScheduleItem(
            type=ScheduleItemType.TASK,
            title="알고리즘 과제",
            source_id="task-1",
            start_offset=0,
            end_offset=120,
            day_offset=1,
        )
    ]

    assert schedule_change_summary(
        previous,
        current,
        day_start=time(9, 0),
        plan_date=date(2026, 6, 3),
    ) == [
        {
            "task": "알고리즘 과제",
            "before": "2026/06/03 12:00~14:00",
            "after": "2026/06/04 09:00~11:00",
        }
    ]


def test_schedule_change_summary_reports_day_only_moves():
    previous = [
        ScheduleItem(
            type=ScheduleItemType.TASK,
            title="알고리즘 과제",
            source_id="task-1",
            start_offset=0,
            end_offset=120,
        )
    ]
    current = [
        ScheduleItem(
            type=ScheduleItemType.TASK,
            title="알고리즘 과제",
            source_id="task-1",
            start_offset=0,
            end_offset=120,
            day_offset=1,
        )
    ]

    assert schedule_change_summary(
        previous,
        current,
        day_start=time(9, 0),
        plan_date=date(2026, 6, 3),
    ) == [
        {
            "task": "알고리즘 과제",
            "before": "2026/06/03 09:00~11:00",
            "after": "2026/06/04 09:00~11:00",
        }
    ]


def test_mvp_sidebar_excludes_google_calendar_label():
    assert mvp_sidebar_integration_labels(
        openai_status=OpenAIOAuthStatus(connected=False, message="not connected")
    ) == ["OpenAI OAuth 연동"]
    assert mvp_sidebar_integration_labels(
        openai_status=OpenAIOAuthStatus(connected=True, message="connected")
    ) == []
