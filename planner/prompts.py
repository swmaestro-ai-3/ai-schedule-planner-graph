PARSE_DAY_PLAN_PROMPT = """
사용자의 자연어 일정을 DayPlanInput JSON으로만 구조화한다.
응답은 JSON만 반환한다.
시간 계산, free block 계산, 작업 배치는 수행하지 않는다.
날짜가 없으면 reference_date를 사용한다. 하루 시작/종료가 없으면 09:00~23:00을 사용한다.
가용시간이 없으면 기준일부터 7일 동안 매일 하루 시작~종료를 availability_windows로 넣는다.
task의 시작/종료 날짜가 없으면 기준일부터 7일 범위로 넣는다.
task의 priority가 없으면 3, splittable이 없으면 true, focus_type이 없으면 any를 사용한다.
작업명이나 소요 시간이 없으면 추측하지 말고 누락 정보를 표시한다.
availability_windows는 작업 배치가 가능한 주간 시간대다. 사용자가 가용시간을 말하면 day_offset(기준일 0~6), start_time, end_time으로 넣는다.
각 task에는 사용자가 말한 시작 가능 날짜(start_date)와 종료 날짜(end_date)를 넣는다.
"""

INTERPRET_REJECTION_PROMPT = """
사용자의 거절 사유를 ReplanConstraints JSON으로만 변환한다.
응답은 JSON만 반환한다.
시간 계산과 일정 배치는 Python scheduler가 수행한다.
input은 최신 사용자 요청이고 conversation은 최근 채팅 맥락이다. "그거", "아까", "방금 제안", "더 늦게"처럼 대명사나 생략이 있으면 conversation과 current_state의 task title/source_id/schedule_items를 함께 사용해 구체적인 task id와 제약으로 해석한다.
conversation은 참고 맥락일 뿐이며, 최신 input과 충돌하면 최신 input을 우선한다.
assistant_message는 사용자가 일정 변경이 아니라 설명/확인/질문을 요청할 때 사용하는 응답 문장이다. 이 경우 다른 변경 제약은 비워 둔다.
buffer_ratio_delta는 여유 시간 증가 비율이다. 더 여유롭게 요청하면 0.1~0.3을 사용한다.
fixed_event_buffer_after는 고정 일정 직후 휴식 시간(분)이다. 회의/수업 직후 쉬고 싶다는 요청은 최소 15를 사용한다.
excluded_fixed_event_ids는 취소/삭제/빼기 요청된 고정 일정 id 목록이다.
additional_fixed_events는 사용자가 채팅 중 새로 추가해달라고 한 고정 일정 리스트다. 날짜/요일과 시간이 명시된 약속, 수업, 회의, 운동 루틴은 fixed event로 추가한다.
fixed_event_updates는 기존 고정 일정 id별 수정 필드다. 제목, 요일(day_offset), 시작/종료 시간, 카테고리, buffer를 바꾸는 요청에 사용한다.
availability_overrides는 특정 요일의 작업 가능 시간을 교체하는 AvailabilityWindow 리스트다. "월요일 1시간밖에 없어"는 해당 day_offset의 start_time을 기존 day_start, end_time을 1시간 뒤로 둔다.
additional_tasks는 사용자가 채팅 중 새로 추가해달라고 한 작업 리스트다. 새 작업은 고유 id, title, estimated_minutes, priority, splittable, focus_type을 포함한다.
task_updates는 기존 작업 id별 수정 필드다. 제목, estimated_minutes, priority, 시작/종료 날짜, focus_type, splittable 같은 속성 수정에 사용한다.
task_day_offsets는 task id를 기준일 기준 day_offset(0~6)으로 매핑한다. "기획서 작성을 목요일로 옮겨줘" 같은 배치 이동 요청에 사용한다.
snoozed_task_days는 task id를 1~6일 뒤로 미루는 매핑이다. 내일로 미루기/스누즈 요청은 1을 사용한다.
preferred_windows는 task id를 HH:MM 시작 희망 시간 문자열로 매핑한다. "오후 4시로 수정" 같은 요청은 "16:00"을 사용한다.
duration_multipliers는 task id를 소요 시간 배수로 매핑한다. "기획서 작성 시간이 3배" 같은 요청은 {"해당 task id": 3.0}을 사용한다.
"""
