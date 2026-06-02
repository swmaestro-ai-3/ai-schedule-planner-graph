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

## Integrations

### Google Calendar

Create a Google OAuth web client and set these values in `.env`:

```bash
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8501
GOOGLE_TOKEN_FILE=.google-calendar-token.json
```

The app uses `https://www.googleapis.com/auth/calendar.events` so it can import
timed events and export approved planner tasks. The generated token file is
ignored by git.

### OpenAI OAuth

The sidebar exposes one OpenAI control:

- `OpenAI OAuth 연동` checks the local proxy, starts `npx @openai/codex login`
  when no local `auth.json` is available, or starts `npm run llm:proxy` when
  credentials already exist.

Natural-language parsing uses the npm `openai-oauth` proxy through the Node
sidecar. Treat local `auth.json` and `.openai-oauth/` contents as
password-equivalent credential material.

## Demo

See `docs/demo-scenarios.md` for the student and junior developer demo inputs.
