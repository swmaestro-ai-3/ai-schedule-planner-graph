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
buffer_ratio_delta는 여유 시간 증가 비율이다. 더 여유롭게 요청하면 0.1~0.3을 사용한다.
fixed_event_buffer_after는 고정 일정 직후 휴식 시간(분)이다. 회의/수업 직후 쉬고 싶다는 요청은 최소 15를 사용한다.
snoozed_task_days는 task id를 1~6일 뒤로 미루는 매핑이다. 내일로 미루기/스누즈 요청은 1을 사용한다.
preferred_windows는 task id를 HH:MM 시작 희망 시간 문자열로 매핑한다. "오후 4시로 수정" 같은 요청은 "16:00"을 사용한다.
"""
