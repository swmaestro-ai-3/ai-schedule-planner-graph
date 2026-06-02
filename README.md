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
