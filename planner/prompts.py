PARSE_DAY_PLAN_PROMPT = """
사용자의 자연어 일정을 DayPlanInput JSON으로만 구조화한다.
응답은 JSON만 반환한다.
시간 계산, free block 계산, 작업 배치는 수행하지 않는다.
필수 필드가 없으면 추측하지 말고 누락 정보를 표시한다.
"""

INTERPRET_REJECTION_PROMPT = """
사용자의 거절 사유를 ReplanConstraints JSON으로만 변환한다.
응답은 JSON만 반환한다.
시간 계산과 일정 배치는 Python scheduler가 수행한다.
buffer_ratio_delta는 여유 시간 증가 비율이다. 더 여유롭게 요청하면 0.1~0.3을 사용한다.
fixed_event_buffer_after는 고정 일정 직후 휴식 시간(분)이다. 회의/수업 직후 쉬고 싶다는 요청은 최소 15를 사용한다.
snoozed_task_days는 task id를 1~6일 뒤로 미루는 매핑이다. 내일로 미루기/스누즈 요청은 1을 사용한다.
"""
