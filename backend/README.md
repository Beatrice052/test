# Requirement Intake Guided Backend MVP

FastAPI backend for Step 4 AI-guided requirement intake.

This MVP is designed to connect to the current React frontend. It is LLM-first:

- `config/use_case_metadata.json` as the field source of truth.
- `config/dependency_rules.json` as the dependency source of truth.
- `MockLLMClient` as the local deterministic replacement for a real LLM.
- `OpenAICompatibleLLMClient` as the real LLM adapter shape.
- in-memory sessions for MVP runtime state.

## What Is Implemented

- Metadata registry loading 33 fields.
- LLM-first requirement extraction.
- Question group based active question planning.
- LLM-first answer parsing.
- LLM-first assistant question wording.
- Guided session state.
- EDIT_REFERENCE and CREATE_NEW draft build.
- Dependency resolution for channel-driven fields.
- Hidden internal impact plan.
- Clean user-facing Action Preview.
- Apply preview.
- Manual field update.
- Validation.
- Export for AC domain payload.
- Frontend-compatible API routes.

## Run Backend

```powershell
cd "C:\Users\19704\Documents\Codex\2026-06-16\ai-c-users-19704-downloads-requirement\outputs\requirement-intake-backend"
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health check:

```text
http://127.0.0.1:8000/health
```

## Connect Frontend To This Backend

Create frontend `.env.local`:

```text
VITE_API_CLIENT=real
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Restart frontend:

```powershell
cd "C:\Users\19704\Documents\Codex\2026-06-16\ai-c-users-19704-downloads-requirement\outputs\requirement-intake-frontend"
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

## API Routes

Frontend-compatible:

```text
POST  /api/intake/{intake_id}/requirement/analyze
POST  /api/intake/{intake_id}/draft/build
POST  /api/intake/{intake_id}/assistant/parse-answer
POST  /api/intake/{intake_id}/assistant/apply-preview
PATCH /api/intake/{intake_id}/fields/{field_name}
POST  /api/intake/{intake_id}/validate
POST  /api/intake/{intake_id}/export-for-ac
```

Spec-style aliases:

```text
POST /api/intake/guided/create-new
POST /api/intake/guided/edit-reference
POST /api/intake/{intake_id}/guided/answer
POST /api/intake/{intake_id}/guided/apply-preview
POST /api/intake/{intake_id}/guided/validate
POST /api/intake/{intake_id}/guided/export-for-ac
```

## LLM Architecture

The backend calls the LLM from service-layer modules only. Routes do not contain LLM logic.

```text
RequirementExtractor.extract          -> extract_requirement(...)
QuestionWordingService._rewrite_wording -> word_question(...)
AnswerParser.parse                    -> parse_answer(...)
GuidedIntakeOrchestrator.export_for_ac -> summarize_draft(...)
```

Prompt templates live in:

```text
app/prompts.py
```

LLM structured output models and adapters live in:

```text
app/llm.py
```

Current adapters:

```text
MockLLMClient
OpenAICompatibleLLMClient
```

The deterministic mock is only for local testing. The production behavior should use a real LLM by setting environment variables before starting uvicorn:

```powershell
$env:INTAKE_LLM_PROVIDER="openai_compatible"
$env:INTAKE_LLM_BASE_URL="https://your-internal-llm-gateway/v1"
$env:INTAKE_LLM_API_KEY="YOUR_INTERNAL_KEY"
$env:INTAKE_LLM_MODEL="your-model-name"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The real LLM gateway must support an OpenAI-compatible chat completions endpoint:

```text
POST {INTAKE_LLM_BASE_URL}/chat/completions
```

Expected response shape:

```json
{
  "choices": [
    {
      "message": {
        "content": "{\"candidates\": []}"
      }
    }
  ]
}
```

If your internal LLM does not expose OpenAI-compatible chat completions, implement a new adapter with the same methods:

```python
extract_requirement(requirement, metadata_context)
parse_answer(question, answer, draft_context)
word_question(question, metadata_context)
plan_next_question(draft_context, open_fields)
summarize_draft(draft_context)
```

Do not move LLM calls into the route layer. Keep them inside services so API contracts stay stable.

`ActiveQuestionPlanner` should remain the owner of the next question. The LLM can rewrite wording and parse answers, but question grouping must come from `config/question_group_config.json`.

The dependency rule engine should stay deterministic. It applies hidden downstream changes such as channel-specific required fields after the LLM has produced user-facing updates. Hidden dependent changes are intentionally excluded from Action Preview.

## Tests

```powershell
python -m pytest -q
```
