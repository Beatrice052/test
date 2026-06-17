# Opencode Handoff: Requirement Intake Frontend + Guided Backend

This document is the implementation guide for connecting the new React frontend to the real internal backend.

## 1. Target Architecture

```text
React frontend
  -> FastAPI contract endpoints
      -> internal retrieval/statistics services
      -> guided-intake orchestration
      -> internal LLM gateway
      -> dependency rules
      -> validation service
      -> AC generation service
```

The current `backend/` is an MVP implementation of the middle orchestration layer. It is useful as a reference and local mock backend, but your internal backend should replace or integrate the parts that already exist internally.

Do not rebuild the business UI in Streamlit. Use `frontend/` as the user-facing intake app.

## 2. Frontend Responsibility

The React frontend owns:

- the business-facing layout;
- requirement entry;
- reference candidate display and reference/new-case choice;
- structured Assistant rendering through `assistant_cards`;
- form modules and editable fields;
- dropdown options for fields with controlled vocabularies;
- Action Preview confirmation;
- validation and AC export buttons once backend responses are ready.

The frontend does not own:

- retrieval ranking;
- common field statistics;
- LLM prompts;
- dependency rule decisions;
- final validation logic;
- AC generation content.

## 3. Backend Responsibility

The backend should return stable UI state after every user action.

Required responsibilities:

- analyze initial requirement;
- retrieve related use cases;
- compute department-level common field patterns;
- compute related-use-case field statistics;
- provide candidate reference use cases to the user;
- build a draft after the user chooses reference or create-new;
- prefill fields from requirement, reference, and statistics with source/confidence;
- plan the next active business question;
- parse user answers into scoped field updates;
- preview user-facing updates before applying;
- apply updates and dependency rules;
- hide internal dependent changes from Action Preview;
- validate the draft;
- export confirmed data for AC generation;
- generate AC or call the internal AC service.

## 4. Existing Internal Logic To Reuse

You mentioned the internal backend already has:

- department-level lookup after user provides a requirement;
- common field usage statistics under the detected department;
- requirement-related use case retrieval;
- statistics over fields used in related use cases;
- candidate related use cases shown to the user;
- validation;
- AC generation.

Keep these pieces. The main integration work is to map their outputs into the frontend contract in `frontend/src/api/types.ts`.

## 5. User Flow To Implement

### Step A: Initial requirement

User enters a free-text requirement in the assistant.

Frontend calls:

```text
POST /api/intake/{intake_id}/requirement/analyze
```

Backend should:

- extract high-confidence fields from the requirement using real LLM;
- detect department/LOB if possible;
- run department common-field statistics;
- retrieve related use cases;
- run field statistics over those related use cases;
- return candidate reference use cases and summary assistant cards.

The user must be allowed to choose:

- use one candidate as reference;
- confirm directly when no reference is needed;
- start a new use case.

### Step B: Draft build

Frontend calls:

```text
POST /api/intake/{intake_id}/draft/build
```

Request:

```json
{
  "mode": "EDIT_REFERENCE",
  "requirement": "user requirement text",
  "selected_reference_use_case_id": "M1004"
}
```

or:

```json
{
  "mode": "CREATE_NEW",
  "requirement": "user requirement text"
}
```

Backend should:

- build modules;
- prefill extracted fields;
- inherit reference fields only for `EDIT_REFERENCE`;
- mark field sources clearly;
- include field options when available;
- run dependency rules;
- ask the first active question through `assistant_cards`.

### Step C: Guided answering

Frontend calls:

```text
POST /api/intake/{intake_id}/assistant/parse-answer
```

Request:

```json
{
  "question_id": "q_delivery_mode_risk",
  "answer": "Batch is fine and this is not high risk. It only needs business hours."
}
```

Backend should pass these to LLM answer parsing:

- active question;
- `group_id`;
- `focus_fields`;
- parser scope from `question_group_config.json`;
- field metadata and allowed options;
- current draft values;
- user answer.

LLM should return structured updates only. Backend must still filter updates by parser scope before previewing.

### Step D: Action Preview

`parse-answer` should return only a preview. Do not mutate the draft yet.

Only direct business updates go into:

```text
action_preview.user_facing_updates
```

Do not show hidden dependency effects here. Store them internally, for example:

```text
InternalImpactPlan
```

### Step E: Apply Preview

Frontend calls:

```text
POST /api/intake/{intake_id}/assistant/apply-preview
```

Backend should:

- apply the stored preview;
- run dependency rules;
- update field statuses;
- return updated modules;
- return the next active question if needed.

### Step F: Manual field edit

Frontend calls:

```text
PATCH /api/intake/{intake_id}/fields/{field_name}
```

Backend should:

- update that field;
- rerun dependency rules;
- return all modules and any useful assistant card;
- continue guided planning.

### Step G: Validation and AC

Frontend currently has the contract endpoints:

```text
POST /api/intake/{intake_id}/validate
POST /api/intake/{intake_id}/export-for-ac
```

Your internal backend should connect these to the existing validation and AC generation modules.

Recommended next frontend work:

- add a validation result panel with blocking issues and warnings;
- add an AC generation preview panel after `ready_for_ac=true`;
- add a "Generate AC" or "Export for AC" action that calls the real AC backend;
- render generated AC text or structured AC sections returned by backend.

## 6. API Contract Summary

The frontend client is in:

```text
frontend/src/api/realClient.ts
frontend/src/api/types.ts
```

Required endpoints:

```text
POST  /api/intake/{intake_id}/requirement/analyze
POST  /api/intake/{intake_id}/draft/build
POST  /api/intake/{intake_id}/assistant/parse-answer
POST  /api/intake/{intake_id}/assistant/apply-preview
PATCH /api/intake/{intake_id}/fields/{field_name}
POST  /api/intake/{intake_id}/validate
POST  /api/intake/{intake_id}/export-for-ac
```

Add CORS for:

```text
http://127.0.0.1:5173
http://localhost:5173
```

## 7. Module And Field Shape

Return modules as:

```json
{
  "business": {
    "id": "business",
    "title": "Business Context",
    "complete": 2,
    "total": 5,
    "fields": []
  },
  "audience": {},
  "channel": {},
  "compliance": {}
}
```

Each field:

```json
{
  "name": "channel",
  "displayName": "Channel",
  "value": "SMS",
  "status": "AI Prefilled",
  "source": "From requirement",
  "help": "Delivery channel used for this message.",
  "required": true,
  "hidden": false,
  "options": [
    { "label": "SMS", "value": "SMS" },
    { "label": "Email", "value": "EMAIL" },
    { "label": "Mobile Push", "value": "PUSH" }
  ]
}
```

If a field has controlled values, always return `options`. This lets users manually select a value even when AI did not prefill correctly.

## 8. Question Group Rules

Use `backend/config/question_group_config.json` as the source of truth for:

- group boundaries;
- templates;
- hints;
- ask conditions;
- skip conditions;
- prerequisites;
- parser scope.

Rules:

- one active question equals one business decision;
- do not ask one field at a time unless that field is the full business decision;
- do not ask unrelated fields together;
- if one field in a group was already provided with high confidence, do not ask it again;
- if a field is low confidence, conflicts with reference, or is invalidated by an upstream change, it may be asked again;
- project and ownership fields should be asked near final review;
- generated fields such as `push_optin_flag` should not be asked directly.

## 9. Real LLM Integration

Current local backend defaults to `MockLLMClient`, which is deterministic but limited.

For production, connect real LLM at:

```text
backend/app/llm.py
```

Adapter methods:

```python
extract_requirement(requirement, metadata_context)
parse_answer(question, answer, draft_context)
word_question(question, metadata_context)
plan_next_question(draft_context, open_fields)
summarize_draft(draft_context)
```

The most important method for guided intake quality is `parse_answer`. It should receive:

- previous active question;
- user answer;
- current draft;
- focus fields;
- group id;
- field options;
- field descriptions;
- parser scope.

It should output:

```json
{
  "updates": {
    "channel": ["SMS"],
    "message_trigger_conditions": "customer starts wealth product planning"
  },
  "confidence": 0.92,
  "evidence": "short evidence from answer",
  "reason": "why these updates are safe"
}
```

Backend must filter the returned updates by parser scope before building Action Preview.

## 10. Internal Retrieval Integration

Replace MVP fixture retrieval with internal services:

```text
requirement text
  -> LLM extraction
  -> department detection
  -> department common field statistics
  -> related use case retrieval
  -> related use case field statistics
  -> candidate reference cards
```

Suggested response fields for `AnalyzeRequirementResponse`:

```json
{
  "intake_id": "INTAKE-001",
  "requirement": "...",
  "extracted_signals": {
    "lob": "WPB",
    "channel": "SMS",
    "trigger": "wealth product planning",
    "audience": "wealth customers"
  },
  "candidates": [
    {
      "id": "M1004",
      "name": "RDP 004",
      "project": "Investment reminder",
      "source_system": "PEGA",
      "lob": "WPB",
      "channel": "SMS",
      "similarity": "0.86",
      "badge": "Best match",
      "reason": "Similar wealth product trigger and channel."
    }
  ],
  "assistant_cards": []
}
```

## 11. AC And Validation Frontend Follow-up

Backend already exposes placeholders:

```text
validate
export-for-ac
```

Opencode should connect them to internal validation and AC generation.

Frontend follow-up work should add:

- validation drawer or section below the form;
- blocking issue click-to-field behavior;
- AC preview section;
- generated AC content rendering;
- final export/download action if needed.

## 12. Migration Notes

The old Streamlit UI can still show internal debug data:

- raw retrieval scores;
- hidden dependent field changes;
- dependency trace;
- LLM raw output;
- validation internals.

The React frontend should only show:

- business requirement;
- related use case choices;
- user-facing fields;
- assistant questions;
- clean Action Preview;
- validation readiness;
- AC preview/export when available.

