# Requirement Intake Frontend

Product-grade React + TypeScript + Vite frontend for the Requirement Intake workflow.

This project is contract-first and runs without a backend. The UI uses `mockClient` by default, and `realClient` implements the same `IntakeApiClient` interface for later backend integration.

## Golden paths

- `EDIT_REFERENCE conflict`: the requirement says Email only, while reference use case `RDP 004 / M1004` uses SMS.
- `CREATE_NEW basic`: no reference is inherited; the Assistant asks audience/trigger and channel before sender setup.

## Run locally

```bash
npm install
npm run dev
```

Open the Vite URL, usually:

```text
http://127.0.0.1:5173
```

## Build

```bash
npm run build
```

## Switch to real API

Create `.env.local`:

```text
VITE_API_CLIENT=real
VITE_API_BASE_URL=http://localhost:8000
```

Then run:

```bash
npm run dev
```

The real backend must implement the same contract used by `src/api/realClient.ts`:

- `POST /api/intake/{intake_id}/draft/build`
- `POST /api/intake/{intake_id}/assistant/parse-answer`
- `POST /api/intake/{intake_id}/assistant/apply-preview`
- `PATCH /api/intake/{intake_id}/fields/{field_name}`
- `POST /api/intake/{intake_id}/validate`
- `POST /api/intake/{intake_id}/export-for-ac`

## Important implementation notes

- The Assistant renders structured `assistant_cards`, not a generic chat transcript.
- Action Preview only shows `user_facing_updates`.
- Hidden dependent changes are kept out of the business UI.
- Low-level Not Applicable fields are hidden from the main form and summarized under `Hidden by current setup`.
- `mockClient` and `realClient` share the same `IntakeApiClient` TypeScript interface.

## Key files

- `src/api/types.ts`: API contract and shared UI types.
- `src/api/mockClient.ts`: mock API implementation.
- `src/api/realClient.ts`: real API implementation.
- `src/fixtures/editReferenceConflict.ts`: EDIT_REFERENCE golden path.
- `src/fixtures/createNewBasic.ts`: CREATE_NEW golden path.
- `src/components/assistant`: structured assistant card rendering.
- `src/components/form`: module and field workspace.
