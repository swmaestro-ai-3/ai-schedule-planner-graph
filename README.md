# AI Schedule Planner Graph

LangGraph-based daily schedule planner MVP.

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

```bash
streamlit run app.py
```

## MVP Flow

The Streamlit MVP is organized around four roles:

- `사용자 입력`: enter fixed events and tasks through natural-language or structured tabs.
- `AI 배치 제안`: view the proposed schedule as both a table and local day calendar.
- `사용자 검증 및 피드백`: review warnings, unassigned tasks, and buffer status.
- `AI 재배치 / 확정`: apply user feedback or approve the final plan.

Google Calendar helper code remains available for future integration, but the
MVP UI uses the local calendar view instead of an external calendar connection.

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
