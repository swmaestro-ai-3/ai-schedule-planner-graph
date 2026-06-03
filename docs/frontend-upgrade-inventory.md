# Frontend Upgrade Inventory

프론트엔드 고도화 전에 현재 MVP가 가진 백엔드 스택, 기능 표면, CTA 요소를 코드 기준으로 정리한 문서다.

## Backend Stack

### App Runtime

- `Streamlit`: 단일 Python 앱 런타임. `app.py`가 화면 렌더링, 세션 상태, graph 호출, sidebar 연동 UI를 함께 담당한다.
- `Python 3.11`: 로컬 실행과 테스트 기준 런타임.
- `python-dotenv`: `.env` 로컬 환경변수 로딩.
- `Pydantic v2`: 입력, 정규화 결과, 스케줄 결과, 검증 이슈, 재계획 제약의 타입 계약.
- `pytest`: Python 중심 테스트 러너. `npm test`도 내부적으로 `pytest -q`를 실행한다.

### Planning Engine

- `LangGraph`: `planner.graph.build_planner_graph()`가 일정 생성/검증/승인/재계획 workflow를 구성한다.
- `planner.nodes`: graph node 구현.
  - 자연어 입력 파싱
  - 재계획 제약 적용
  - 입력 검증
  - 시간 정규화
  - free block 계산
  - block 분류
  - task ranking
  - task/fixed event 배치
  - draft 검증
  - 설명 생성
  - 승인/재계획 routing
  - 최종 출력 생성
- `planner.scheduler`: free block 계산, block 분류, task 배치, snooze, preferred time 재배치.
- `planner.validators`: 입력/일정 충돌, buffer 부족, 미배치 작업, feasibility 상태 검증.
- `planner.ranking`: task 우선순위 score 계산.
- `planner.explanations`: rule-based 설명 생성.

### LLM Integration

- `npm openai-oauth`: 로컬 OAuth proxy. `package.json`의 `llm:proxy`가 실행한다.
- `llm_sidecar/openai_oauth_client.mjs`: Python planner와 `openai-oauth` proxy 사이의 Node sidecar.
- `planner.llm_parser`: 자연어 입력과 피드백을 LLM JSON으로 변환하고, 한국어 일정 표현을 deterministic normalizer로 보강한다.
  - 오전/오후/저녁/밤 시간 표현
  - 숫자/한국어 소요시간
  - 매일/평일/주말/요일 범위/요일 축약 반복
  - `내일부터 N일 동안` 같은 상대 기간
  - `24:00`을 앱 시간 모델의 `23:59`로 clamp
  - LLM timeout 시 fixed event/routine rule fallback
  - 제목 기반 snooze와 preferred time feedback 해석

### Calendar Integrations

- `planner.openai_oauth`: OpenAI OAuth auth file 탐색, proxy 상태 확인, login/proxy process 시작.
- `planner.google_calendar`: Google Calendar OAuth, 일정 import, task export helper.
- Google Calendar helper와 테스트는 남아 있지만, MVP 화면에서는 Google Calendar CTA를 호출하지 않는다.

## Current Product Flow

1. `사용자 입력`
   - 자연어 입력 탭 또는 구조화 입력 탭으로 일정 정보를 만든다.
   - 구조화 입력은 계획 기준, 가용 시간, 고정 일정, 작업 editor로 구성된다.
2. `AI 배치 제안`
   - graph 결과를 주간 로컬 캘린더와 table로 보여준다.
   - 판단 근거를 표시한다.
3. `사용자 검증 및 피드백`
   - validation panel, 승인 CTA, feedback textarea, snooze controls, 재배치 CTA를 제공한다.
4. `AI 재배치 / 확정`
   - 피드백 반영 결과, 재계획 횟수, 변경 요약을 표시한다.
   - 승인 시 최종 확정 상태를 표시한다.

## Feature Inventory

### Input Features

- 자연어 일정 입력
  - LLM parser와 rule fallback으로 `DayPlanInput`을 생성한다.
  - 반복 루틴, fixed event, task, availability 표현을 처리한다.
- 구조화 입력
  - 계획 날짜, 하루 시작/종료, buffer ratio 설정.
  - 7일 availability window 설정.
  - fixed event editor.
  - task editor: 소요시간, 중요도, 시작/종료 날짜, 집중도, 분할 가능 여부.
- OpenAI OAuth 상태 표시
  - proxy 연결 상태와 모델 일부를 sidebar에 표시한다.
  - 연결 안 된 경우에만 연동 CTA를 노출한다.

### Scheduling Features

- fixed event를 기준으로 free block 계산.
- availability window 안에서만 task 배치.
- task 시작/종료 날짜 범위와 deadline 고려.
- priority, hard deadline, focus type, block type 기반 ranking.
- splittable task 분할 배치.
- non-splittable task 단일 block 배치.
- buffer ratio 기반 buffer 보호.
- 남는 ordinary free time은 일정 item으로 렌더링하지 않음.
- fixed event, task, explicit buffer만 calendar block으로 표시.

### Validation Features

- 하루 시작/종료 범위 검증.
- availability range 검증.
- fixed event range/out-of-day/overlap/duplicate 검증.
- task duration 누락 검증.
- task start/end date range 검증.
- schedule item overlap 검증.
- buffer shortage 계산.
- feasibility 상태 산출.
- 사용자 검증용 row 변환.

### Feedback And Replan Features

- 승인 시 final plan 생성.
- feedback textarea로 rejection reason 입력.
- snooze select/number input으로 machine-readable snooze feedback 생성.
- LLM 또는 rule fallback으로 `ReplanConstraints` 생성.
- buffer ratio 증가.
- fixed event 직후 buffer 추가.
- excluded task 제거.
- snoozed task 1-6일 이동.
- preferred time feedback 반영.
- 재계획 횟수 표시.
- 이전/현재 task 시간 변경 요약.
- 자동 재계획 3회 제한.

### Local Calendar Features

- 현재 plan date가 포함된 월요일-일요일 주간 view.
- 하루 시간축 기반 vertical timeline.
- block top/height를 start offset/duration으로 계산.
- fixed event, task, buffer를 색상으로 구분.
- table row에는 날짜, 시간, 유형, 제목, 이유를 표시.

### Future Integration Features

- Google Calendar OAuth helper.
- Google Calendar fixed event import.
- task schedule item export.
- 현재 MVP sidebar에서는 Google Calendar CTA 비활성/미노출 정책.

## CTA Inventory

### Primary CTAs

| CTA | Surface | Current Trigger | Backend/State Effect | Current Notes |
| --- | --- | --- | --- | --- |
| `자연어 입력 구조화` | `사용자 입력 > 자연어 입력` | `st.button` | `parse_natural_language_input()` 후 `run_planner()` 실행, `plan_input`/`planner_state` 저장 | 자연어 기반 핵심 entry CTA. 실패 시 `st.error`만 표시한다. |
| `일정안 생성` | `사용자 입력 > 구조화 입력` | primary `st.button`, key `structured_generate` | `build_structured_input()` 후 `run_planner()` 실행 | 구조화 입력의 primary CTA. 입력 editor보다 위에 있어 빠른 실행은 좋지만 editor 변경 후 다시 올려야 할 수 있다. |
| `승인` | `사용자 검증 및 피드백` | `st.button` | `run_planner(plan_input, approval_status="approved")` 실행, final plan 생성 | 현재 최종 확정 이후 별도 export CTA는 없다. |
| `피드백 반영해 재배치` | `사용자 검증 및 피드백` | `st.button` | rejection reason + snooze feedback으로 graph 재실행, previous/current items 저장 | feedback이 없으면 작동하지 않는다. loading/progress affordance는 약하다. |
| `OpenAI OAuth 연동` | Sidebar `연동 > OpenAI OAuth` | `st.sidebar.button` | auth file이 없으면 `npx @openai/codex login`, 있으면 `npm run llm:proxy` 시작 | proxy 연결 상태면 버튼을 숨긴다. |

### Secondary Or Hidden CTAs

| CTA | Surface | Current Trigger | Backend/State Effect | Current Notes |
| --- | --- | --- | --- | --- |
| `Google Calendar 연동` | Future sidebar control | `render_google_calendar_controls()` 내부 button | OAuth login, event import, task export | MVP sidebar에서 호출하지 않는다. future integration용 code/test만 유지한다. |
| `Google 로그인 페이지 열기` | Future sidebar markdown link | OAuth auth URL markdown | Google OAuth 인증 페이지 이동 | Google Calendar UI가 활성화될 때만 사용된다. |
| `Deploy` | Streamlit chrome | Streamlit built-in | 앱 내부 backend와 무관 | 제품 CTA가 아니라 Streamlit shell control이다. |
| `Main menu` | Streamlit chrome | Streamlit built-in | 앱 내부 backend와 무관 | 제품 CTA가 아니라 Streamlit shell control이다. |

### Interactive Controls That Behave Like CTA Inputs

| Control | Surface | Role | Backend/State Effect |
| --- | --- | --- | --- |
| `자연어 일정 입력` | 자연어 탭 | Raw planning intent input | `parse_natural_language_input()` payload source |
| `날짜` | 구조화 입력 | plan 기준일 | `DayPlanInput.date` |
| `하루 시작` / `하루 종료` | 구조화 입력 | planning day bounds | offset 계산과 validation 기준 |
| `여유 비율` | 구조화 입력 | buffer target | `DayPlanInput.buffer_ratio` |
| Availability editor | 구조화 입력 | 작업 배치 가능 시간 | `availability_windows` |
| Fixed event editor | 구조화 입력 | 고정 일정 | `fixed_events` |
| Task editor | 구조화 입력 | AI가 배치할 작업 | `tasks` |
| `피드백` | 검증/피드백 | natural-language rejection reason | `interpret_rejection_reason()` source |
| `스누즈할 작업` | 검증/피드백 | task id selection | machine-readable snooze text 생성 |
| `스누즈 일수` | 검증/피드백 | snooze duration | 1-6일 clamp |

## Frontend Upgrade Implications

### CTA Hierarchy

- Primary flow CTA는 `자연어 입력 구조화`, `일정안 생성`, `승인`, `피드백 반영해 재배치` 네 개다.
- OAuth CTA는 prerequisite CTA라서 product flow와 시각 계층을 분리하는 편이 낫다.
- Google Calendar CTA는 MVP에서 숨긴 상태를 유지하되, future integration 영역으로 명시해야 한다.

### State Visibility Gaps

- 자연어 파싱 중과 재배치 중의 progress state가 약하다.
- `피드백 반영해 재배치`는 feedback이 비어 있으면 아무 반응이 없어 보일 수 있다.
- 승인 이후 final plan의 다음 행동이 없다.
- OpenAI OAuth CTA는 process 시작 후 실제 연결 완료까지의 상태 전이가 충분히 드러나지 않는다.

### Information Architecture Gaps

- 입력, 제안, 검증, 재배치가 한 페이지에 세로로 이어져 있어 사용자가 현재 단계와 다음 행동을 한눈에 파악하기 어렵다.
- 자연어 입력과 구조화 입력은 같은 목적이지만 UI 밀도와 affordance가 다르다.
- validation panel은 기능적이지만 사용자가 “어떤 피드백을 주면 개선되는지”까지 연결해 주지는 않는다.
- calendar와 table이 둘 다 결과이지만 우선순위와 용도가 명확히 분리되어 있지 않다.

### Suggested Frontend Documentation Next Step

다음 문서는 이 인벤토리를 기반으로 `docs/frontend-upgrade-plan.md`에 작성하면 된다.

- 목표 사용자와 핵심 작업 정의.
- 화면 정보구조 재설계.
- CTA hierarchy와 button states.
- 자연어 입력 성공/실패/부분 성공 UX.
- AI 제안/검증/재배치의 state machine.
- 캘린더와 table의 역할 분리.
- OAuth 상태와 product flow의 분리.
