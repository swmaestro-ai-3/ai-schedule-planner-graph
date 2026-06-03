# Frontend Architecture

프론트엔드를 Streamlit 화면에 묶지 않고 키우기 위한 1차 구조다. 기존 Python planner는 유지하고, 새 UI는 `frontend/` 워크스페이스에서 독립적으로 개발한다.

## Folder Layout

```text
frontend/
  src/
    app/                         # 앱 조립과 화면 상태
    features/
      planner/
        api/                     # 백엔드 HTTP 연결 어댑터
        components/              # 일정 플로우 화면과 캘린더
        data/                    # 단계 정의, mock draft
        lib/                     # UI 변환 helper, localStorage helper
        types/                   # 프론트엔드 계약 타입
    shared/
      components/                # 앱 셸 등 공용 UI
    styles/                      # 디자인 토큰과 전역 CSS
planner/                         # 기존 Python scheduling backend
backend/                         # planner graph HTTP API
llm_sidecar/                     # OpenAI OAuth sidecar
app.py                           # legacy Streamlit entry
```

## Screen Model

- `시작`: 활동 시간과 OpenAI 연결 상태만 다룬다.
- `입력`: 자연어/직접 입력 중 하나로 일정 요청을 만든다.
- `제안`: 주간 캘린더와 배치 기준만 보여준다.
- `수정`: 별도 화면이 아니라 우측 하단 채팅 에이전트에서 처리한다.
- `완료`: 확정 요약만 보여준다.

## Backend Boundary

- `frontend/src/features/planner/api/plannerApi.ts`가 `backend.server`의 `/api/plans`, `/api/replans`를 호출한다.
- 캘린더 draft는 `nextplan.calendarDraft` 키로 브라우저 `localStorage`에 저장한다.
- Python `planner/`의 graph, scheduler, validator 모델은 도메인 backend로 유지한다.

## Commands

```bash
npm install
npm run backend:dev
npm run frontend:dev
npm run frontend:build
npm run test:frontend
```
