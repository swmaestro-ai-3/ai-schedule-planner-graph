# AI Schedule Planner Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 하루 고정 일정과 작업 목록을 입력받아 실행 가능한 하루 일정안을 생성하고, 승인 또는 거절에 따라 재계획할 수 있는 LangGraph 기반 Streamlit MVP를 만든다.

**Architecture:** LLM은 자연어 입력 구조화, 거절 사유 해석, 설명 생성에만 사용한다. 시간 계산, free block 생성, buffer 보호, 작업 정렬, 작업 배치, 검증은 순수 Python 규칙 기반 로직으로 구현하고 LangGraph node가 이 로직을 orchestration한다. LLM 호출 인증은 Python API key 직접 사용이 아니라 Node.js sidecar에서 npm `openai-oauth`를 사용하는 방향으로 분리한다.

**Tech Stack:** Python 3.11, Streamlit, LangGraph, Pydantic, pytest, Node.js 22, npm `openai-oauth`, in-memory checkpointer.

---

## 문서 목적

이 문서는 기획안 v2를 실제 개발 이슈로 쪼갠 실행 계획이다. 각 이슈는 독립적인 브랜치와 PR로 닫히며, 모든 이슈는 다음 사이클을 반복한다.

```text
Issue 생성
  -> Branch 생성
  -> Development
  -> Test
  -> Commit
  -> PR 생성
  -> Review / Merge
```

각 PR은 하나의 작은 기능 단위를 제공해야 한다. PR 하나가 너무 커져서 테스트 실패 원인을 좁히기 어려워지면 다음 이슈로 분리한다.

## 공통 개발 사이클

모든 Issue는 아래 순서로 진행한다.

- [ ] **Issue:** GitHub Issue를 생성하고 acceptance criteria를 명시한다.
- [ ] **Branch:** `codex/issue-NN-short-name` 형식의 브랜치를 만든다.
- [ ] **Development:** 해당 Issue의 파일만 생성 또는 수정한다.
- [ ] **Test:** 명시된 단위 테스트, graph flow 테스트, smoke test를 실행한다.
- [ ] **Commit:** 테스트가 통과한 상태에서 하나의 의미 있는 commit을 만든다.
- [ ] **PR:** GitHub PR을 만들고 테스트 결과와 변경 범위를 본문에 기록한다.

공통 명령 형식:

```bash
git switch -c codex/issue-NN-short-name
pytest -q
git status --short
git add <changed-files>
git commit -m "<type>: <summary>"
gh pr create --title "<title>" --body "<summary and test result>"
```

## 전체 파일 구조

최종 MVP는 다음 구조를 목표로 한다.

```text
ai_schedule_planner/
  app.py
  planner/
    __init__.py
    models.py
    state.py
    graph.py
    nodes.py
    scheduler.py
    ranking.py
    validators.py
    llm_parser.py
    prompts.py
    explanations.py
  llm_sidecar/
    openai_oauth_client.mjs
    README.md
  tests/
    conftest.py
    test_models.py
    test_validators.py
    test_time_blocks.py
    test_task_ranking.py
    test_scheduler.py
    test_plan_validation.py
    test_llm_parser.py
    test_graph_flow.py
  README.md
  requirements.txt
  package.json
  package-lock.json
  .env.example
```

파일별 책임:

| 파일 | 책임 |
| --- | --- |
| `app.py` | Streamlit UI, 입력 form, 결과 표시, 승인/거절 interaction |
| `planner/models.py` | Pydantic input/output model과 enum |
| `planner/state.py` | LangGraph에서 공유되는 `PlannerState` |
| `planner/scheduler.py` | 시간 offset, free block, buffer, 작업 배치 엔진 |
| `planner/ranking.py` | `task_score` 계산과 task-block matching score |
| `planner/validators.py` | 입력 검증과 최종 plan 검증 |
| `planner/llm_parser.py` | 자연어 입력을 `DayPlanInput`으로 구조화 |
| `planner/prompts.py` | LLM parser, rejection interpreter, explanation prompt |
| `planner/explanations.py` | 규칙 기반 설명과 LLM 설명 생성을 연결 |
| `llm_sidecar/openai_oauth_client.mjs` | npm `openai-oauth`를 사용하는 Node sidecar entrypoint |
| `llm_sidecar/README.md` | OAuth sidecar 실행 방식, 저장소, 라이선스 주의사항 |
| `planner/nodes.py` | LangGraph node 함수 |
| `planner/graph.py` | `StateGraph` 구성, conditional edge, interrupt, compile |
| `package.json` | Node OAuth sidecar dependency와 npm scripts |
| `package-lock.json` | `openai-oauth` dependency resolution 고정 |
| `tests/` | 순수 함수 단위 테스트와 graph flow 테스트 |

## Issue Backlog

### Issue 01: Project Scaffold and Test Harness

**목표:** Python 패키지, dependency, test harness, 기본 실행 구조를 만든다.

**Files:**

- Create: `requirements.txt`
- Create: `package.json`
- Create: `package-lock.json`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `app.py`
- Create: `planner/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_scaffold.py`
- Modify: `README.md`

**Acceptance Criteria:**

- `python -m compileall app.py planner`가 통과한다.
- `pytest -q`가 통과한다.
- README에 로컬 실행 명령과 테스트 명령이 있다.
- `.env.example`에 OAuth storage와 기본 model 설정 위치가 있다.
- `package.json`에 npm `openai-oauth` dependency가 있다.

**Cycle:**

- [ ] **Development**

```bash
gh issue create --title "Project scaffold and test harness" --body "Create the Python package, Streamlit entrypoint, dependency files, and initial pytest smoke test."
git switch -c codex/issue-01-project-scaffold
```

구현 내용:

- `requirements.txt`에 `streamlit`, `langgraph`, `langchain`, `pydantic`, `pytest`, `python-dotenv`를 추가한다.
- `package.json`에 `openai-oauth@1.0.2`를 추가하고 `package-lock.json`으로 고정한다.
- `.gitignore`에 `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `node_modules/`, `.openai-oauth/`를 추가한다.
- `app.py`는 Streamlit 제목과 placeholder 상태만 렌더링한다.
- `tests/test_scaffold.py`는 `planner` package import, `app.py` compile 가능 여부, `openai-oauth` dependency 선언을 검증한다.
- `README.md`에 `pip install -r requirements.txt`, `npm install`, `pytest -q`, `npm test`, `streamlit run app.py` 실행법을 기록한다.
- `openai-oauth`는 제3자 AGPL dependency이므로 README에 OAuth state를 git에 넣지 않는다는 주의 문구를 남긴다.

- [ ] **Test**

```bash
python -m compileall app.py planner
pytest -q
npm install --package-lock-only --ignore-scripts
npm test
```

Expected:

```text
3 passed
```

- [ ] **Commit**

```bash
git add README.md requirements.txt package.json package-lock.json .env.example .gitignore app.py planner/__init__.py tests/conftest.py tests/test_scaffold.py
git commit -m "chore: scaffold planner project"
```

- [ ] **PR**

```bash
gh pr create --title "Issue 01: Scaffold planner project" --body "Adds project skeleton, dependency files, README commands, and initial smoke test.\n\nTests: pytest -q"
```

### Issue 02: Domain Models and Planner State

**목표:** 기획안의 입력, 출력, 상태 모델을 Pydantic과 TypedDict로 고정한다.

**Files:**

- Create: `planner/models.py`
- Create: `planner/state.py`
- Create: `tests/test_models.py`

**Acceptance Criteria:**

- `DayPlanInput`, `FixedEvent`, `Task`, `FreeBlock`, `ScheduleItem`, `ValidationIssue`, `FinalPlanOutput` 모델이 존재한다.
- `Task.focus_type`은 `deep`, `light`, `any` 중 하나다.
- `FinalPlanOutput.approval_required` 기본값은 `true`다.
- `PlannerState`에 raw input, parsed input, validation result, draft plan, approval status, replan fields가 있다.

**Cycle:**

- [ ] **Development**

```bash
gh issue create --title "Define domain models and planner state" --body "Add Pydantic models and PlannerState for the LangGraph planner workflow."
git switch -c codex/issue-02-domain-models
```

구현 내용:

- `BlockType`: `deep_work`, `light_work`, `buffer`
- `FocusType`: `deep`, `light`, `any`
- `ScheduleItemType`: `fixed_event`, `task`, `buffer`, `free`
- `FeasibilityStatus`: `feasible`, `tight`, `overloaded`, `invalid_input`
- `UnassignedReasonCode`: `NO_AVAILABLE_BLOCK`, `INSUFFICIENT_TIME`, `MISSING_DURATION`, `DEADLINE_NOT_FEASIBLE`, `MIN_CHUNK_TOO_LARGE`, `BUFFER_PROTECTION`
- `PlannerState`: node 간 유지해야 하는 raw data만 저장하고 prompt용 문자열은 저장하지 않는다.

- [ ] **Test**

```bash
pytest -q tests/test_models.py
pytest -q
```

필수 테스트:

- valid `DayPlanInput` 생성
- invalid `focus_type` 거부
- `buffer_ratio` 기본값 `0.1`
- `min_task_block_minutes` 기본값 `30`
- `deep_work_threshold_minutes` 기본값 `90`
- `FinalPlanOutput.approval_required` 기본값 `true`

- [ ] **Commit**

```bash
git add planner/models.py planner/state.py tests/test_models.py
git commit -m "feat: define planner domain models"
```

- [ ] **PR**

```bash
gh pr create --title "Issue 02: Define planner domain models" --body "Adds Pydantic models and PlannerState used by scheduling logic and LangGraph nodes.\n\nTests: pytest -q"
```

### Issue 03: Input Validation and Time Normalization

**목표:** 잘못된 입력을 배치 전에 차단하고, 모든 시간을 분 단위 offset으로 변환한다.

**Files:**

- Create: `planner/validators.py`
- Modify: `planner/models.py`
- Create: `tests/test_validators.py`

**Acceptance Criteria:**

- 하루 종료 시간이 시작 시간보다 빠르면 `invalid_input` issue가 생성된다.
- 고정 일정이 하루 범위를 벗어나면 `invalid_input` issue가 생성된다.
- 고정 일정끼리 겹치면 작업 배치를 중단할 수 있는 blocking issue가 생성된다.
- duration이 없는 task는 `MISSING_DURATION`으로 표시된다.
- `date + time` 입력은 day start 기준 minute offset으로 변환된다.

**Cycle:**

- [ ] **Development**

```bash
gh issue create --title "Validate input and normalize time ranges" --body "Add deterministic validation and minute-offset normalization before scheduling."
git switch -c codex/issue-03-validation-normalization
```

구현 내용:

- `validate_day_plan_input(input: DayPlanInput) -> list[ValidationIssue]`
- `normalize_fixed_events(input: DayPlanInput) -> list[NormalizedFixedEvent]`
- `normalize_tasks(input: DayPlanInput) -> list[NormalizedTask]`
- 겹치는 고정 일정은 자동 병합하지 않고 blocking issue로 남긴다.
- 제목이 비어 있는 fixed event는 `"제목 없는 일정"`으로 표시 가능하도록 normalizer에서 fallback title을 제공한다.

- [ ] **Test**

```bash
pytest -q tests/test_validators.py
pytest -q
```

필수 테스트:

- `09:00~23:00` 하루에서 `10:00~12:00` 일정은 `60~180` offset으로 변환된다.
- `14:00~13:00` fixed event는 invalid다.
- `10:00~12:00`, `11:30~13:00` fixed event는 overlap blocking issue를 만든다.
- estimated duration이 없는 task는 `MISSING_DURATION`으로 분류된다.

- [ ] **Commit**

```bash
git add planner/models.py planner/validators.py tests/test_validators.py
git commit -m "feat: validate and normalize planner inputs"
```

- [ ] **PR**

```bash
gh pr create --title "Issue 03: Validate and normalize planner inputs" --body "Adds input validation, overlap detection, and minute-offset normalization.\n\nTests: pytest -q"
```

### Issue 04: Free Block and Buffer Engine

**목표:** 고정 일정을 제외한 free block을 계산하고 block type과 buffer 목표를 결정한다.

**Files:**

- Create: `planner/scheduler.py`
- Create: `tests/test_time_blocks.py`

**Acceptance Criteria:**

- 고정 일정이 없으면 하루 전체가 하나의 free block이다.
- 고정 일정 사이의 빈 구간이 정확히 계산된다.
- 30분 미만 block은 `buffer`로 분류된다.
- 30분 이상 90분 미만 block은 `light_work`로 분류된다.
- 90분 이상 block은 `deep_work`로 분류된다.
- 목표 buffer는 `total_free_minutes * buffer_ratio`다.

**Cycle:**

- [ ] **Development**

```bash
gh issue create --title "Compute free blocks and buffer targets" --body "Add deterministic free-block calculation, block classification, and buffer target calculation."
git switch -c codex/issue-04-free-blocks-buffer
```

구현 내용:

- `compute_free_blocks(day_start_offset, day_end_offset, normalized_events) -> list[FreeBlock]`
- `classify_free_block(block, min_task_block_minutes=30, deep_work_threshold_minutes=90) -> BlockType`
- `classify_free_blocks(blocks, input_config) -> list[FreeBlock]`
- `calculate_buffer_target(total_free_minutes: int, buffer_ratio: float) -> int`
- `calculate_auto_buffer_minutes(blocks) -> int`

- [ ] **Test**

```bash
pytest -q tests/test_time_blocks.py
pytest -q
```

필수 테스트:

- 하루 `09:00~23:00`, fixed event 없음 -> free block `0~840`
- fixed event `10:00~12:00`, `14:00~15:00` -> free blocks `0~60`, `180~300`, `360~840`
- 20분 block -> `buffer`
- 60분 block -> `light_work`
- 120분 block -> `deep_work`
- free time 420분, ratio 0.1 -> target buffer 42분

- [ ] **Commit**

```bash
git add planner/scheduler.py tests/test_time_blocks.py
git commit -m "feat: compute free blocks and buffer targets"
```

- [ ] **PR**

```bash
gh pr create --title "Issue 04: Compute free blocks and buffer targets" --body "Adds free-block calculation, block classification, and buffer target rules.\n\nTests: pytest -q"
```

### Issue 05: Task Ranking and Fit Scoring

**목표:** 중요도, 마감일, focus match, block fit, split penalty를 사용해 작업 우선순위를 결정한다.

**Files:**

- Create: `planner/ranking.py`
- Create: `tests/test_task_ranking.py`

**Acceptance Criteria:**

- `task_score = priority_score + deadline_score + focus_score + fit_score - split_penalty` 규칙이 구현된다.
- 오늘 마감 task는 deadline score `+80`을 받는다.
- 내일 마감 task는 deadline score `+50`을 받는다.
- 3일 이내 마감 task는 deadline score `+30`을 받는다.
- focus type과 block type이 맞으면 focus score `+20`을 받는다.
- 같은 조건에서는 split 수가 적은 후보가 우선된다.

**Cycle:**

- [ ] **Development**

```bash
gh issue create --title "Rank tasks and score block fit" --body "Implement deterministic task priority and task-block fit scoring."
git switch -c codex/issue-05-task-ranking
```

구현 내용:

- `calculate_deadline_score(task, plan_date) -> int`
- `calculate_focus_score(task, block) -> int`
- `calculate_fit_score(task, block) -> int`
- `calculate_split_penalty(chunk_count) -> int`
- `calculate_task_score(task, block, plan_date, chunk_count=1) -> int`
- `rank_task_candidates(tasks, blocks, plan_date) -> list[TaskCandidate]`

- [ ] **Test**

```bash
pytest -q tests/test_task_ranking.py
pytest -q
```

필수 테스트:

- priority 5는 priority score 500을 만든다.
- 오늘 마감 priority 3 task가 마감 없는 priority 3 task보다 높다.
- `focus_type=deep` task는 `deep_work` block에서 focus score를 받는다.
- 120분 task가 120분 block에 들어가면 fit score를 받는다.
- chunk 3개 후보는 chunk 1개 후보보다 split penalty가 크다.

- [ ] **Commit**

```bash
git add planner/ranking.py tests/test_task_ranking.py
git commit -m "feat: rank tasks by priority and fit"
```

- [ ] **PR**

```bash
gh pr create --title "Issue 05: Rank tasks by priority and fit" --body "Adds task score, deadline score, focus score, fit score, and split penalty logic.\n\nTests: pytest -q"
```

### Issue 06: Greedy Task Placement Engine

**목표:** ranked task를 free block에 배치하고, 배치할 수 없는 task에는 명확한 사유를 붙인다.

**Files:**

- Modify: `planner/scheduler.py`
- Modify: `planner/ranking.py`
- Create: `tests/test_scheduler.py`

**Acceptance Criteria:**

- deep task는 90분 이상 block에 우선 배치된다.
- light task는 30~90분 block에 우선 배치된다.
- splittable task는 `min_chunk_minutes` 이상 단위로 여러 block에 나뉜다.
- non-splittable task는 충분한 block이 없으면 미배치된다.
- buffer 보호 때문에 제외된 task는 `BUFFER_PROTECTION` reason을 받는다.
- 출력 schedule item은 시간순으로 정렬된다.

**Cycle:**

- [ ] **Development**

```bash
gh issue create --title "Place tasks with greedy scheduling" --body "Implement deterministic greedy task placement with splitting and unassigned reasons."
git switch -c codex/issue-06-task-placement
```

구현 내용:

- `place_tasks(input, classified_blocks, ranked_tasks) -> DraftPlan`
- block에 task를 배치한 뒤 남은 block을 다시 계산한다.
- 분할 task는 같은 `source_id`를 공유하고 title에 `(1/2)`, `(2/2)` suffix를 붙인다.
- 30분 미만 block에는 task를 배치하지 않는다.
- 목표 buffer가 부족하면 낮은 점수 task를 배치하지 않고 buffer를 보호한다.

- [ ] **Test**

```bash
pytest -q tests/test_scheduler.py
pytest -q
```

필수 테스트:

- 대학생 시나리오에서 오늘 마감 알고리즘 과제가 영어 단어 암기보다 먼저 배치된다.
- 120분 splittable task가 60분 block 2개에 나뉘어 배치된다.
- 90분 deep block이 없으면 non-splittable 120분 deep task는 미배치된다.
- 전체 작업 시간이 free time을 초과하면 낮은 priority task가 미배치된다.
- schedule item이 fixed event, task, buffer를 포함해 시간순으로 반환된다.

- [ ] **Commit**

```bash
git add planner/scheduler.py planner/ranking.py tests/test_scheduler.py
git commit -m "feat: place tasks with greedy scheduling"
```

- [ ] **PR**

```bash
gh pr create --title "Issue 06: Place tasks with greedy scheduling" --body "Adds greedy scheduling, task splitting, buffer protection, and unassigned task reasons.\n\nTests: pytest -q"
```

### Issue 07: Plan Validation and Explanation Output

**목표:** draft plan의 충돌, buffer 부족, 과도계획, deadline 문제를 검증하고 사용자에게 보여줄 경고와 설명을 만든다.

**Files:**

- Modify: `planner/validators.py`
- Create: `planner/explanations.py`
- Create: `tests/test_plan_validation.py`

**Acceptance Criteria:**

- fixed event와 task schedule item이 겹치지 않는지 검증한다.
- task schedule item끼리 겹치지 않는지 검증한다.
- 확보 buffer가 목표 buffer보다 부족하면 warning을 만든다.
- high priority 미배치 task가 있으면 feasibility status를 `tight` 또는 `overloaded`로 만든다.
- 각 schedule item에는 배치 이유가 있다.
- `FinalPlanOutput`은 schedule, warnings, unassigned tasks, buffer summary, feasibility status, explanation을 포함한다.

**Cycle:**

- [ ] **Development**

```bash
gh issue create --title "Validate draft plans and generate explanations" --body "Add plan-level validation, warning codes, feasibility status, and user-facing explanations."
git switch -c codex/issue-07-plan-validation-explanations
```

구현 내용:

- `validate_draft_plan(draft_plan, input_config) -> ValidationResult`
- `build_buffer_summary(blocks, schedule_items, target_buffer_minutes) -> BufferSummary`
- `determine_feasibility(validation_result, unassigned_tasks) -> FeasibilityStatus`
- `build_rule_based_explanation(final_plan) -> str`
- warning code는 UI에서 그대로 표시할 수 있는 안정적인 문자열로 관리한다.

- [ ] **Test**

```bash
pytest -q tests/test_plan_validation.py
pytest -q
```

필수 테스트:

- 겹치는 schedule item이 있으면 blocking validation issue가 생긴다.
- 목표 buffer 42분, 확보 buffer 25분이면 buffer 부족 warning이 생긴다.
- priority 5 task가 미배치되면 `feasibility_status`가 `tight` 이상으로 나빠진다.
- 모든 task schedule item은 `reason`을 가진다.

- [ ] **Commit**

```bash
git add planner/validators.py planner/explanations.py tests/test_plan_validation.py
git commit -m "feat: validate plans and explain results"
```

- [ ] **PR**

```bash
gh pr create --title "Issue 07: Validate plans and explain results" --body "Adds draft-plan validation, warnings, feasibility status, buffer summary, and user-facing explanations.\n\nTests: pytest -q"
```

### Issue 08: Node OAuth LLM Adapter and Structured Parser

**목표:** npm `openai-oauth` 기반 Node sidecar를 통해 자연어 입력과 거절 사유를 구조화하되, 계산 로직은 LLM에 맡기지 않는다.

**Files:**

- Create: `planner/prompts.py`
- Create: `planner/llm_parser.py`
- Create: `llm_sidecar/openai_oauth_client.mjs`
- Create: `llm_sidecar/README.md`
- Create: `tests/test_llm_parser.py`
- Create: `tests/test_llm_sidecar_contract.py`
- Modify: `package.json`
- Modify: `.env.example`

**Acceptance Criteria:**

- 자연어 입력을 `DayPlanInput` schema로 파싱하는 함수가 있다.
- Python parser는 LLM 호출 자체를 직접 수행하지 않고 Node sidecar contract를 호출한다.
- Node sidecar는 npm `openai-oauth` dependency를 사용한다.
- structured output validation 실패 시 재시도 횟수를 제한한다.
- 불완전 입력은 바로 배치하지 않고 clarification question을 만든다.
- 거절 사유는 `replan_constraints`로 변환된다.
- 테스트는 실제 OAuth login이나 외부 API를 호출하지 않고 fake sidecar 또는 monkeypatch로 검증한다.
- OAuth token/state 저장 위치는 `.openai-oauth/`이고 git에 포함되지 않는다.
- `openai-oauth`의 AGPL 라이선스와 제3자 dependency 리스크가 `llm_sidecar/README.md`에 명시된다.

**Cycle:**

- [ ] **Development**

```bash
gh issue create --title "Add Node OAuth LLM adapter and structured parser" --body "Add an npm openai-oauth sidecar contract, Python parser wrapper, prompts, and rejection interpreter without using LLM for time calculation."
git switch -c codex/issue-08-node-oauth-llm-adapter
```

구현 내용:

- `parse_natural_language_input(raw_text: str) -> DayPlanInput`
- `build_clarification_questions(errors: list[ValidationIssue]) -> list[str]`
- `interpret_rejection_reason(reason: str, current_state: PlannerState) -> ReplanConstraints`
- `call_llm_sidecar(payload: dict) -> dict`
- `llm_sidecar/openai_oauth_client.mjs`는 stdin JSON을 받아 stdout JSON으로 반환하는 contract를 제공한다.
- prompt에는 "시간 계산을 하지 말고 구조화만 수행한다"는 제한을 명시한다.
- OAuth state는 `OPENAI_OAUTH_STORAGE_DIR`를 사용하고 기본값은 `.openai-oauth`다.
- 기본 LLM model은 `OPENAI_OAUTH_MODEL`로 설정한다.
- API key 기반 `OPENAI_API_KEY`와 `ANTHROPIC_API_KEY`는 MVP 기본 경로에서 사용하지 않는다.

- [ ] **Test**

```bash
pytest -q tests/test_llm_parser.py
pytest -q tests/test_llm_sidecar_contract.py
npm test
pytest -q
```

필수 테스트:

- fake parser output이 valid `DayPlanInput`이면 그대로 반환된다.
- 필수 날짜가 없으면 clarification question이 생성된다.
- `"너무 빡빡해"`는 buffer ratio 증가 constraint로 변환된다.
- `"회의 직후에는 쉬고 싶어"`는 fixed event after-buffer constraint로 변환된다.
- validation 실패 재시도 한도를 넘으면 structured input 사용 요청 메시지를 반환한다.
- fake sidecar가 schema-valid JSON을 반환하면 Python wrapper가 `DayPlanInput`으로 변환한다.
- sidecar stdout이 invalid JSON이면 parser가 clarification path로 이동한다.
- `package.json`에 `openai-oauth` dependency가 유지된다.

- [ ] **Commit**

```bash
git add .env.example package.json package-lock.json planner/prompts.py planner/llm_parser.py llm_sidecar/openai_oauth_client.mjs llm_sidecar/README.md tests/test_llm_parser.py tests/test_llm_sidecar_contract.py
git commit -m "feat: add node oauth llm adapter"
```

- [ ] **PR**

```bash
gh pr create --title "Issue 08: Add Node OAuth LLM adapter" --body "Adds npm openai-oauth sidecar contract, natural-language parsing wrapper, clarification questions, and rejection interpretation with mocked tests.\n\nTests: pytest -q\nTests: npm test"
```

### Issue 09: LangGraph Workflow and Human-in-the-loop

**목표:** parse, validate, normalize, schedule, validate plan, explain, approve, replan 흐름을 LangGraph로 연결한다.

**Files:**

- Create: `planner/nodes.py`
- Create: `planner/graph.py`
- Create: `tests/test_graph_flow.py`
- Modify: `planner/state.py`

**Acceptance Criteria:**

- `parse_input_node`부터 `finalize_node`까지 node 함수가 있다.
- invalid input은 scheduling node로 넘어가지 않는다.
- missing info는 clarification route로 간다.
- 승인되면 `final_plan`을 만들고 종료한다.
- 거절되면 `interpret_rejection_node`를 거쳐 `rank_tasks_node` 이후 재계획한다.
- `replan_count >= 3`이면 자동 재계획을 중단한다.
- graph flow 테스트는 checkpointer와 thread id를 사용한다.

**Cycle:**

- [ ] **Development**

```bash
gh issue create --title "Build LangGraph workflow with approval loop" --body "Connect planner nodes with conditional routing, interrupt approval, and bounded replan loop."
git switch -c codex/issue-09-langgraph-workflow
```

구현 내용:

- `parse_input_node`
- `validate_input_node`
- `clarification_node`
- `normalize_time_node`
- `compute_free_blocks_node`
- `classify_blocks_node`
- `rank_tasks_node`
- `place_tasks_node`
- `validate_plan_node`
- `generate_explanation_node`
- `approval_node`
- `interpret_rejection_node`
- `finalize_node`
- `build_planner_graph(checkpointer=None)`

Graph route:

```text
START
  -> parse_input_node
  -> validate_input_node
      -> clarification_node when missing_info
      -> END when invalid_input
      -> normalize_time_node when valid
  -> compute_free_blocks_node
  -> classify_blocks_node
  -> rank_tasks_node
  -> place_tasks_node
  -> validate_plan_node
  -> generate_explanation_node
  -> approval_node
      -> finalize_node when approved
      -> interpret_rejection_node when rejected
  -> rank_tasks_node
```

- [ ] **Test**

```bash
pytest -q tests/test_graph_flow.py
pytest -q
```

필수 테스트:

- valid structured input은 draft plan까지 도달한다.
- overlapping fixed events는 invalid route로 종료된다.
- approval input `approved=true`는 final plan을 만든다.
- approval input `approved=false`는 rejection reason을 constraint로 바꾸고 replan count를 증가시킨다.
- replan count 3회 초과 시 자동 재계획 중단 메시지가 생성된다.

- [ ] **Commit**

```bash
git add planner/nodes.py planner/graph.py planner/state.py tests/test_graph_flow.py
git commit -m "feat: build langgraph planner workflow"
```

- [ ] **PR**

```bash
gh pr create --title "Issue 09: Build LangGraph planner workflow" --body "Adds planner graph nodes, conditional routing, approval loop, and replan limit tests.\n\nTests: pytest -q"
```

### Issue 10: Streamlit MVP UI and Demo Scenarios

**목표:** 사용자가 구조화 입력 또는 자연어 입력으로 일정안을 생성하고, 승인 또는 거절 후 재계획을 실행할 수 있는 로컬 데모를 만든다.

**Files:**

- Modify: `app.py`
- Modify: `README.md`
- Create: `docs/demo-scenarios.md`
- Create: `tests/test_streamlit_contract.py`

**Acceptance Criteria:**

- Streamlit 화면에는 자연어 입력 tab과 구조화 입력 tab이 있다.
- 구조화 입력은 날짜, 하루 시작/종료 시간, buffer ratio, fixed events, tasks를 받는다.
- 결과 영역은 시간순 일정표, 경고, 미배치 작업, buffer summary, explanation을 표시한다.
- 승인 버튼은 final plan 상태를 표시한다.
- 거절 사유 입력 후 재계획 결과를 표시한다.
- README만 보고 로컬 데모를 실행할 수 있다.
- `docs/demo-scenarios.md`에 대학생 시나리오와 주니어 개발자 시나리오가 있다.

**Cycle:**

- [ ] **Development**

```bash
gh issue create --title "Build Streamlit MVP UI and demo scenarios" --body "Add the local Streamlit demo UI, approval/rejection interaction, README updates, and demo scenarios."
git switch -c codex/issue-10-streamlit-demo
```

구현 내용:

- `app.py`에서 `st.tabs(["자연어 입력", "구조화 입력"])`로 입력 방식을 나눈다.
- fixed events와 tasks는 MVP에서 반복 입력 form 또는 editable table로 받는다.
- schedule table은 `start_time`, `end_time`, `type`, `title`, `reason`을 표시한다.
- warning 영역은 warning code와 사용자용 메시지를 함께 표시한다.
- approval 영역은 승인과 거절 사유 입력을 분리한다.
- `docs/demo-scenarios.md`에 기획안의 대학생, 주니어 개발자 입력 예시와 기대 결과를 문서화한다.

- [ ] **Test**

```bash
pytest -q tests/test_streamlit_contract.py
pytest -q
streamlit run app.py
```

필수 테스트:

- UI adapter가 valid structured input을 `DayPlanInput`으로 변환한다.
- schedule table row 생성 함수가 `ScheduleItem` 목록을 표시 가능한 dict 목록으로 변환한다.
- warning summary 생성 함수가 buffer 부족과 미배치 작업을 표시한다.
- 수동 smoke test로 Streamlit에서 대학생 시나리오를 입력하고 일정표가 표시되는지 확인한다.

- [ ] **Commit**

```bash
git add app.py README.md docs/demo-scenarios.md tests/test_streamlit_contract.py
git commit -m "feat: build streamlit planner demo"
```

- [ ] **PR**

```bash
gh pr create --title "Issue 10: Build Streamlit planner demo" --body "Adds the Streamlit MVP UI, approval/rejection interaction, README instructions, and demo scenarios.\n\nTests: pytest -q\nManual: streamlit run app.py"
```

## Cross-Issue Acceptance Matrix

| 기획 요구사항 | 담당 Issue |
| --- | --- |
| 하루 단위 개인 일정 생성 | Issue 02, 04, 06, 10 |
| 자연어 입력 구조화 | Issue 08 |
| npm `openai-oauth` 기반 LLM 인증 | Issue 01, 08 |
| 구조화 입력 form | Issue 10 |
| 고정 일정 제외 후 free block 계산 | Issue 03, 04 |
| deep/light/buffer block 분류 | Issue 04 |
| 중요도, 마감일, focus type 기반 정렬 | Issue 05 |
| splittable task 분할 배치 | Issue 06 |
| buffer ratio와 buffer 부족 경고 | Issue 04, 07 |
| 충돌, 과도계획, 미배치 검증 | Issue 07 |
| 사용자 승인 전 최종 확정 금지 | Issue 09, 10 |
| 거절 사유 기반 재계획 | Issue 08, 09, 10 |
| 재계획 루프 3회 제한 | Issue 09 |
| Streamlit 로컬 데모 | Issue 10 |
| LLM은 계산에 사용하지 않음 | Issue 08, 09 |

## PR Review Checklist

각 PR 리뷰에서 다음을 확인한다.

- 변경 범위가 해당 Issue acceptance criteria를 넘지 않는다.
- 계산 로직은 LLM 호출 없이 테스트 가능하다.
- 새 public function에는 단위 테스트가 있다.
- 테스트 이름은 동작을 설명한다.
- warning code와 unassigned reason code는 UI에 표시 가능한 안정적인 값이다.
- 실패 입력은 조용히 무시되지 않고 validation issue로 남는다.
- `pytest -q` 결과가 PR 본문에 기록되어 있다.

## Definition of Done

MVP 전체 완료 기준:

- `pytest -q`가 통과한다.
- `streamlit run app.py`로 로컬 데모가 실행된다.
- 대학생 시나리오와 주니어 개발자 시나리오가 Streamlit에서 재현된다.
- fixed event와 task schedule item이 겹치지 않는다.
- 30분 미만 free block은 task 배치 대상에서 제외된다.
- buffer 부족, 과도계획, 미배치 task가 사용자에게 표시된다.
- 승인 전에는 `final_plan`이 생성되지 않는다.
- 거절 사유 입력 후 최대 3회까지 재계획할 수 있다.
- README와 `docs/demo-scenarios.md`만 보고 실행과 시연이 가능하다.
