# Requirement Intake Frontend Real API Integration Guide

This document is for Opencode/backend implementation. The current frontend is a real React + TypeScript + Vite app using a mock API client. The backend should implement the same contract so the frontend can switch from `mockClient` to `realClient` without UI rewrites.

## 1. Frontend Location

Project path:

```text
C:\Users\19704\Documents\Codex\2026-06-16\ai-c-users-19704-downloads-requirement\outputs\requirement-intake-frontend
```

Important frontend files:

```text
src/api/types.ts        TypeScript API contract
src/api/mockClient.ts   Current mock behavior
src/api/realClient.ts   Real backend HTTP client
src/api/client.ts       Switches mock vs real client
src/App.tsx             Product UI and workflow
```

## 2. How To Switch Frontend From Mock To Real API

Create this file in the frontend project root:

```text
.env.local
```

Content:

```text
VITE_API_CLIENT=real
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Then restart frontend:

```powershell
cd "C:\Users\19704\Documents\Codex\2026-06-16\ai-c-users-19704-downloads-requirement\outputs\requirement-intake-frontend"
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

The frontend will call `src/api/realClient.ts`.

## 3. Backend Must Implement These Endpoints

Base URL example:

```text
http://127.0.0.1:8000
```

Required endpoints:

```text
POST  /api/intake/{intake_id}/draft/build
POST  /api/intake/{intake_id}/assistant/parse-answer
POST  /api/intake/{intake_id}/assistant/apply-preview
PATCH /api/intake/{intake_id}/fields/{field_name}
POST  /api/intake/{intake_id}/validate
POST  /api/intake/{intake_id}/export-for-ac
```

The frontend sends and receives JSON. Add CORS for:

```text
http://127.0.0.1:5173
http://localhost:5173
```

## 4. Core Design Rule

The frontend is business-facing. Backend can maintain debug/internal dependency details, but the business UI must only receive user-facing state.

Do not send hidden backend dependency changes into `action_preview.user_facing_updates`.

Good Action Preview:

```text
Channel Setup: SMS -> Email
Message Purpose: Service reminder -> Service reminder
```

Do not show these in business Action Preview:

```text
SMS Sender ID -> Not Applicable
Email Sender Name -> Missing Required
SMS Router Path -> Hidden
```

Those can exist in backend debug logs or Streamlit debug view, but not in the frontend business preview.

## 5. Shared Types

The frontend expects this data model.

### Intake Mode

```ts
type IntakeMode = "CREATE_NEW" | "EDIT_REFERENCE" | "CONFIRM_DIRECTLY";
```

### Field Status

```ts
type FieldStatus =
  | "Confirmed"
  | "AI Prefilled"
  | "Reference Prefilled"
  | "Needs Confirmation"
  | "Missing Required"
  | "Optional"
  | "Not Applicable";
```

### Field Source

```ts
type FieldSource =
  | "From requirement"
  | "From reference"
  | "User confirmed"
  | "Default";
```

### Form Field

```ts
type FormField = {
  name: string;
  displayName: string;
  value: string;
  status: FieldStatus;
  source: FieldSource;
  help: string;
  required?: boolean;
  hidden?: boolean;
};
```

Important:

- `name` is the backend field key.
- `displayName` is shown to business users.
- `value` must be a string for now.
- `hidden: true` means the frontend hides the field unless user chooses "Show all fields".
- `Not Applicable` fields should usually be `hidden: true`.

### Form Module

```ts
type FormModule = {
  id: string;
  title: string;
  complete: number;
  total: number;
  fields: FormField[];
};
```

Current frontend expects these module ids:

```text
business
audience
channel
compliance
```

Recommended module titles:

```text
Business Context
Audience & Trigger
Channel & Content
Compliance & Launch
```

## 6. Assistant Cards

The backend should drive the right-side AI Assistant by returning structured `assistant_cards`.

Supported card types:

```ts
type AssistantCard =
  | SummaryCard
  | FindingCard
  | QuestionCard
  | ActionPreviewCard
  | ValidationCard
  | FieldExplanationCard;
```

### Summary Card

```json
{
  "type": "summary",
  "title": "Requirement understood",
  "body": "I understood this as a WPB wealth product messaging use case."
}
```

### Finding Card

```json
{
  "type": "finding",
  "title": "I found one important difference",
  "body": "The requirement says Email only, while the reference use case uses SMS."
}
```

### Question Card

```json
{
  "type": "question",
  "question_id": "q_channel_conflict",
  "title": "Questions",
  "question": "Should the channel remain SMS, change to Email, change to Mobile Push, or use multiple channels?",
  "question_type": "SINGLE_CHOICE",
  "options": [
    { "label": "Wealth customers - Email only", "value": "Email" },
    { "label": "Wealth customers - SMS", "value": "SMS" },
    { "label": "Use Mobile Push", "value": "Mobile Push" },
    { "label": "Service reminder", "value": "Service reminder" }
  ],
  "focus_fields": ["selected_delivery_channel"],
  "why_asking": "The channel determines sender setup and downstream content fields.",
  "priority": "P0"
}
```

### Action Preview Card

```json
{
  "type": "action_preview",
  "title": "Action Preview",
  "action_preview": {
    "preview_id": "preview_001",
    "user_facing_updates": [
      {
        "field_name": "selected_delivery_channel",
        "display_name": "Channel Setup",
        "old_value": "SMS",
        "new_value": "Email",
        "reason": "User confirmed Email."
      }
    ],
    "follow_up_summary": "After applying this, I will ask only for the next user-facing required setup field."
  }
}
```

Critical:

- `parse-answer` should return Action Preview.
- The frontend must not apply updates until user clicks Confirm.
- `apply-preview` should apply the preview and return updated `modules`.

## 7. Endpoint Contracts

### 7.1 Build Draft

```http
POST /api/intake/{intake_id}/draft/build
```

Request:

```json
{
  "mode": "EDIT_REFERENCE",
  "requirement": "We have a new business scenario about investment shopping cart...",
  "selected_reference_use_case_id": "M1004"
}
```

Response:

```json
{
  "intake_id": "INTAKE-001",
  "mode": "EDIT_REFERENCE",
  "requirement": "We have a new business scenario about investment shopping cart...",
  "extracted_signals": {
    "lob": "WPB",
    "channel": "SMS",
    "trigger": "Investment product expiry",
    "audience": "Investment cart customers"
  },
  "selected_reference": {
    "id": "M1004",
    "name": "RDP 004",
    "source_system": "PEGA",
    "channel": "SMS",
    "status": "Conflicts found"
  },
  "modules": {
    "business": {
      "id": "business",
      "title": "Business Context",
      "complete": 8,
      "total": 10,
      "fields": [
        {
          "name": "use_case_name",
          "displayName": "Use Case Name",
          "value": "Investment cart expiry reminder",
          "status": "AI Prefilled",
          "source": "From requirement",
          "help": "Short business name used to identify this intake."
        }
      ]
    }
  },
  "assistant_cards": [],
  "validation": {
    "ready_for_ac": false,
    "blocking_issues": [],
    "warnings": []
  }
}
```

Backend should return all four modules in `modules`.

### 7.2 Parse Assistant Answer

```http
POST /api/intake/{intake_id}/assistant/parse-answer
```

Request:

```json
{
  "question_id": "q_channel_conflict",
  "answer": "Wealth customers - Email only"
}
```

Response:

```json
{
  "user_message": "Wealth customers - Email only",
  "assistant_cards": [
    {
      "type": "action_preview",
      "title": "Action Preview",
      "action_preview": {
        "preview_id": "preview_001",
        "user_facing_updates": [
          {
            "field_name": "selected_delivery_channel",
            "display_name": "Channel Setup",
            "old_value": "SMS",
            "new_value": "Email",
            "reason": "User confirmed Email."
          }
        ],
        "follow_up_summary": "After applying this, I will ask only for the next user-facing required setup field."
      }
    }
  ]
}
```

Backend behavior:

- Parse the user's answer.
- Build a pending preview.
- Store preview by `preview_id`.
- Do not mutate confirmed draft yet.

### 7.3 Apply Preview

```http
POST /api/intake/{intake_id}/assistant/apply-preview
```

Request:

```json
{
  "preview_id": "preview_001"
}
```

Response:

```json
{
  "modules": {},
  "assistant_cards": [
    {
      "type": "summary",
      "title": "Channel updated",
      "body": "Email is now selected for this use case."
    },
    {
      "type": "question",
      "question_id": "q_email_sender_name",
      "title": "Confirm email sender",
      "question": "Which email sender name should be shown to the customer?",
      "question_type": "FREE_TEXT",
      "focus_fields": ["email_sender_name"],
      "why_asking": "Email sender name is required when Email is selected."
    }
  ],
  "validation": {
    "ready_for_ac": false,
    "blocking_issues": [
      {
        "field_name": "email_sender_name",
        "display_name": "Email Sender Name",
        "message": "Email sender name is required when Email is selected."
      }
    ],
    "warnings": []
  }
}
```

Backend behavior:

- Apply the stored preview to the draft.
- Re-run dependency rules.
- Return updated business-facing `modules`.
- Mark hidden dependent fields as `hidden: true`.
- Ask the next most important user-facing question.

Example after Email is selected:

```json
{
  "name": "email_sender_name",
  "displayName": "Email Sender Name",
  "value": "",
  "status": "Missing Required",
  "source": "Default",
  "help": "Required when Email is selected.",
  "required": true
}
```

Example hidden SMS field:

```json
{
  "name": "sms_sender_id",
  "displayName": "SMS Sender ID",
  "value": "",
  "status": "Not Applicable",
  "source": "Default",
  "help": "Hidden because Email only is selected.",
  "hidden": true
}
```

### 7.4 Manual Field Update

```http
PATCH /api/intake/{intake_id}/fields/{field_name}
```

Request:

```json
{
  "value": "HSBC Wealth",
  "updated_by": "USER"
}
```

Response:

```json
{
  "modules": {},
  "assistant_cards": [
    {
      "type": "summary",
      "title": "Sender captured",
      "body": "HSBC Wealth is now set as the email sender name."
    }
  ],
  "validation": {
    "ready_for_ac": false,
    "blocking_issues": [],
    "warnings": []
  }
}
```

Backend behavior:

- Update one field.
- Recalculate dependencies and validation.
- Return all modules, not just the changed field.
- Return assistant cards only when useful.

### 7.5 Validate

```http
POST /api/intake/{intake_id}/validate
```

Response:

```json
{
  "ready_for_ac": false,
  "blocking_issues": [
    {
      "field_name": "launch_window",
      "display_name": "Launch Window",
      "message": "Launch Window is required."
    }
  ],
  "warnings": []
}
```

Backend behavior:

- Validate only business-facing requirements.
- `Not Applicable` hidden fields should not be blockers.

### 7.6 Export For AC

```http
POST /api/intake/{intake_id}/export-for-ac
```

Response:

```json
{
  "ready_for_ac": true,
  "confirmed_use_case": {
    "use_case_name": "Investment cart expiry reminder",
    "line_of_business": "WPB",
    "selected_delivery_channel": "SMS"
  },
  "semantic_summary": "WPB investment cart expiry reminder sent by SMS to customers with investment products close to expiry."
}
```

Backend behavior:

- Only return `ready_for_ac: true` when blocking issues are resolved.
- `confirmed_use_case` should contain normalized field keys and values for AC generation.

## 8. Required Golden Path Behaviors

### Golden Path A: EDIT_REFERENCE

Initial scenario:

```text
Requirement: investment shopping cart product close to expiry
Reference: RDP 004 / M1004
Reference channel: SMS
Mode: EDIT_REFERENCE
```

Build draft should:

- prefill fields from requirement and reference;
- show RDP 004 as selected reference;
- return assistant cards:
  - welcome/understood summary;
  - reference recommendation;
  - question about target segment / purpose / channel.

When user chooses Email:

- `parse-answer` returns Action Preview.
- Action Preview only shows user-facing changes.
- `apply-preview` changes `selected_delivery_channel` to Email.
- `apply-preview` exposes `email_sender_name` as Missing Required.
- `sms_sender_id` becomes hidden / Not Applicable.
- Assistant asks email sender name.

When user chooses SMS:

- `parse-answer` returns Action Preview.
- `apply-preview` keeps SMS confirmed.
- Assistant asks next missing user-facing field, such as launch window.

### Golden Path B: CREATE_NEW

Initial scenario:

```text
No selected reference
Mode: CREATE_NEW
```

Build draft should:

- not inherit historical field values;
- prefill only values extracted from requirement;
- ask audience/trigger and channel first;
- not ask sender setup before channel is selected.

After channel is selected:

- `parse-answer` returns Action Preview.
- `apply-preview` confirms channel.
- backend then exposes only relevant sender setup fields.

## 9. Streamlit Migration Guidance

The old Streamlit app can remain as backend/debug tooling. Do not copy Streamlit debug output directly into the frontend contract.

Recommended split:

```text
Streamlit:
- metadata inspection
- dependency resolver debug
- raw planner output
- hidden field dependency changes
- backend troubleshooting

React frontend:
- business-facing requirement intake
- reference selection
- user-facing form fields
- structured Assistant cards
- clean Action Preview
- validation and AC export readiness
```

Backend can reuse Streamlit logic internally, but must translate it into the frontend contract.

## 10. Backend Implementation Checklist

1. Create API routes listed in section 3.
2. Add CORS for Vite dev server.
3. Implement draft storage by `intake_id`.
4. Implement `build-draft` to return modules and initial assistant cards.
5. Implement `parse-answer` to create pending preview only.
6. Implement `apply-preview` to mutate draft and recalculate dependencies.
7. Implement `PATCH fields` for manual edits.
8. Implement validation that ignores hidden Not Applicable fields.
9. Implement export for AC.
10. Run frontend with `VITE_API_CLIENT=real`.

## 11. Suggested FastAPI Skeleton

```py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/intake/{intake_id}/draft/build")
def build_draft(intake_id: str, body: dict):
    return {}

@app.post("/api/intake/{intake_id}/assistant/parse-answer")
def parse_answer(intake_id: str, body: dict):
    return {}

@app.post("/api/intake/{intake_id}/assistant/apply-preview")
def apply_preview(intake_id: str, body: dict):
    return {}

@app.patch("/api/intake/{intake_id}/fields/{field_name}")
def update_field(intake_id: str, field_name: str, body: dict):
    return {}

@app.post("/api/intake/{intake_id}/validate")
def validate(intake_id: str):
    return {}

@app.post("/api/intake/{intake_id}/export-for-ac")
def export_for_ac(intake_id: str):
    return {}
```

## 12. Acceptance Criteria For Real Backend Connection

The connection is successful when:

- frontend starts with `VITE_API_CLIENT=real`;
- page loads without mock data;
- `build-draft` returns the same UI shape as mock;
- Assistant quick reply calls real `parse-answer`;
- Action Preview appears from real backend;
- Confirm and apply calls real `apply-preview`;
- form table updates from real backend modules;
- hidden dependent changes do not appear in Action Preview;
- Validate calls real backend;
- Export for AC only enables when backend returns `ready_for_ac: true`.

