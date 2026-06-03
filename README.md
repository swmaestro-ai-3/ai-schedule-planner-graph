# NextPlan AI

LangGraph-based schedule planner backend with a standalone React frontend.

## Quick Start

Use this path on a new computer after cloning the repository.

```bash
git clone https://github.com/swmaestro-ai-3/ai-schedule-planner-graph.git
cd ai-schedule-planner-graph

python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

npm install
cp .env.example .env
npm run dev
```

Then open the frontend:

- Frontend: `http://127.0.0.1:5173`
- Backend API: `http://127.0.0.1:8010`

`npm run dev` starts both the Python backend and the Vite frontend. Stop both
with `Ctrl+C`.

## Requirements

- Python 3.11, available as `python3.11`
- Node.js 22 LTS or newer
- npm 10 or newer

macOS examples:

```bash
brew install python@3.11 node
python3.11 --version
node --version
npm --version
```

If your machine only exposes Python 3.11 as a different executable name, either
create a `python3.11` alias or run the backend manually with that executable.

## Environment

Copy `.env.example` once per machine:

```bash
cp .env.example .env
```

Default local values:

```bash
OPENAI_OAUTH_STORAGE_DIR=.openai-oauth
OPENAI_OAUTH_MODEL=gpt-5.1
OPENAI_OAUTH_BASE_URL=http://127.0.0.1:10531/v1
```

The frontend calls `http://127.0.0.1:8010` by default. If the backend runs on a
different host or port, set this before starting the frontend:

```bash
export VITE_PLANNER_API_URL=http://127.0.0.1:8010
```

## Run

Recommended local development command:

```bash
npm run dev
```

Manual two-terminal mode:

```bash
# Terminal 1
source .venv/bin/activate
npm run backend:dev

# Terminal 2
npm run frontend:dev
```

Optional OpenAI OAuth proxy for LLM-backed natural-language parsing:

```bash
npm run llm:proxy
```

The app can still run without the OAuth proxy. When the proxy is offline,
natural-language handling falls back to the local parser and scheduler logic.

## Test

```bash
npm run test:python
npm run test:frontend
npm test
```

Build the frontend:

```bash
npm run frontend:build
```

Legacy Streamlit entry:

```bash
streamlit run app.py
```

## MVP Flow

The frontend is organized around one-purpose screens:

- `시작`: activity bounds and OpenAI connection status.
- `입력`: natural-language or structured schedule input.
- `제안`: weekly local calendar and placement rationale.
- `완료`: confirmed schedule summary.

Schedule feedback, snooze, and modification requests happen through the
bottom-right chat agent. Calendar drafts are stored in the browser's
`localStorage`, so a browser refresh restores the current proposal on the same
computer.

Google Calendar helper code remains available for future integration, but the
MVP UI uses the local weekly calendar view instead of an external calendar connection.

## OpenAI OAuth

Natural-language parsing uses the npm `openai-oauth` proxy through the Node
sidecar. Treat local `auth.json` and `.openai-oauth/` contents as
password-equivalent credential material.

LLM integration uses the npm `openai-oauth` package, not a checked-in API key.
The OAuth package is a third-party AGPL-licensed dependency, so keep generated
OAuth state out of git.

First-time OAuth setup on a trusted local machine:

```bash
npm install
npx @openai/codex login
npm run llm:proxy
```

## Demo

See `docs/demo-scenarios.md` for the student and junior developer demo inputs.

## Product Docs

- `docs/frontend-upgrade-inventory.md`: backend stack, feature inventory, and CTA inventory for frontend upgrade planning.
- `docs/frontend-architecture.md`: frontend folder structure, screen model, and backend boundary.
