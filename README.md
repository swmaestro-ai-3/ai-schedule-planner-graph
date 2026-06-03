# NextPlan AI

LangGraph-based schedule planner backend with a standalone React frontend.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
cp .env.example .env
```

LLM integration is planned through the npm `openai-oauth` package, not a checked-in API key. The OAuth package is a third-party AGPL-licensed dependency, so keep generated OAuth state out of git.

## Test

```bash
pytest -q
npm test
```

## Run

Primary frontend:

```bash
npm run backend:dev
npm run frontend:dev
```

The frontend calls `http://127.0.0.1:8010` by default. Set
`VITE_PLANNER_API_URL` when the planner API runs elsewhere.

Legacy Streamlit entry:

```bash
streamlit run app.py
```

## MVP Flow

The frontend is organized around one-purpose screens:

- `시작`: activity bounds and OpenAI connection status.
- `입력`: natural-language or structured schedule input.
- `제안`: weekly local calendar and placement rationale.
- `수정`: validation, feedback, and snooze controls.
- `완료`: confirmed schedule summary.

Google Calendar helper code remains available for future integration, but the
MVP UI uses the local weekly calendar view instead of an external calendar connection.

## OpenAI OAuth

The sidebar exposes one OpenAI control:

- `OpenAI OAuth 연동` checks the local proxy, starts `npx @openai/codex login`
  when no local `auth.json` is available, or starts `npm run llm:proxy` when
  credentials already exist.

Natural-language parsing uses the npm `openai-oauth` proxy through the Node
sidecar. Treat local `auth.json` and `.openai-oauth/` contents as
password-equivalent credential material.

## Demo

See `docs/demo-scenarios.md` for the student and junior developer demo inputs.

## Product Docs

- `docs/frontend-upgrade-inventory.md`: backend stack, feature inventory, and CTA inventory for frontend upgrade planning.
- `docs/frontend-architecture.md`: frontend folder structure, screen model, and backend boundary.
