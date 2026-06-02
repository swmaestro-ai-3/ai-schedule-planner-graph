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
"""
