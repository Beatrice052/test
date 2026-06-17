# MDC Requirement Intake

This repository contains the new lightweight product frontend and guided-intake backend MVP for the Requirement Intake workflow.

Use this React frontend instead of the previous Streamlit UI for business users. Streamlit can remain as an internal backend/debug tool, but the user-facing intake experience should be driven by `frontend/`.

## Repository Layout

```text
frontend/   React + TypeScript + Vite business UI
backend/    FastAPI guided-intake MVP with mock LLM and OpenAI-compatible LLM adapter
docs/       Opencode handoff and real backend integration notes
legacy-single-page-prototype/  Older static prototype archived for reference only
```

## What This Code Does

The frontend provides the real intake workspace:

- starts from a user requirement;
- lets backend return related use case candidates;
- lets the user choose whether to use a reference case or create a new case;
- renders structured `assistant_cards`;
- renders business form modules and field dropdown options;
- shows Action Preview before applying assistant-parsed updates;
- hides dependent/internal changes from business UI;
- calls validation and AC export endpoints through the same API client.

The backend MVP provides the middle guided-fill logic:

- requirement extraction through an LLM adapter interface;
- candidate/reference draft building with mock fixtures;
- question group based active question planning;
- scoped answer parsing;
- dependency rule application;
- user-facing Action Preview plus hidden `InternalImpactPlan`;
- validation and AC export placeholder endpoints.

Your internal backend already owns richer business logic. Opencode should keep those mature parts and connect them to this frontend contract.

## Run Locally

Backend:

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

For real backend mode, create `frontend/.env.local`:

```text
VITE_API_CLIENT=real
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Open:

```text
http://127.0.0.1:5173
```

## Validation

```powershell
cd backend
python -m pytest -q
```

```powershell
cd frontend
npm run build
```

Current validation before this handoff:

- backend tests: `12 passed`
- frontend build: successful

## LLM Connection

The backend defaults to `MockLLMClient`, so local parsing is intentionally limited. For realistic extraction and answer parsing, connect your internal LLM.

If the internal gateway is OpenAI-compatible:

```powershell
$env:INTAKE_LLM_PROVIDER="openai_compatible"
$env:INTAKE_LLM_BASE_URL="https://your-internal-llm-gateway/v1"
$env:INTAKE_LLM_API_KEY="YOUR_INTERNAL_KEY"
$env:INTAKE_LLM_MODEL="your-model-name"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

If not OpenAI-compatible, implement another adapter with the same methods in `backend/app/llm.py`:

```python
extract_requirement(requirement, metadata_context)
parse_answer(question, answer, draft_context)
word_question(question, metadata_context)
plan_next_question(draft_context, open_fields)
summarize_draft(draft_context)
```

Keep LLM calls in the service layer, not in FastAPI routes.

## Opencode Handoff

Read this first:

```text
docs/opencode-handoff.md
```

It explains how to connect:

- internal department/common-field statistics;
- related use case retrieval and user reference selection;
- real LLM extraction/parsing/wording;
- internal validation;
- AC generation;
- the current React frontend contract.

## Important Product Rules

- Do not use Streamlit as the business frontend.
- `ActiveQuestionPlanner` owns the next active question.
- LLM may rewrite wording and parse answers, but must not freely regroup unrelated fields.
- One active question should represent one business decision.
- Action Preview shows only direct business updates.
- Hidden dependent changes stay in backend internal impact/debug structures.
- If a user already provided a field with high confidence, the same question group should not ask that field again unless it has low confidence, conflict, or became invalid after an upstream change.

