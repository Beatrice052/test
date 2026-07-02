# MDC Requirement Intake Agent Phase 1 — Revised Alignment Plan

## 1. Revision objective

The overall Messaging SDLC architecture has been revised from a “central AI Case Manager controlling multiple agents” model to:

**Deterministic SDLC Workflow Orchestrator + Stage-level AI Agents + Local Remediation Loops + Human Approval Gates**

The existing Phase 1 Requirement Intake Agent remains valid, but its system boundary and terminal state must be adjusted.

Phase 1 should no longer treat `READY_FOR_CONTENT` as an unconditional result of requirement confirmation. It should produce a **review-ready Requirement Package**, submit it to the human Requirement Review Gate, and only allow Content handoff after an explicit approval event from the Workflow Orchestrator.

---

## 2. What remains unchanged

The following Phase 1 design and implementation should be retained:

- Code-first bounded Requirement Intake Agent
- Agent Runner and bounded Policy
- Composite Skills:
  - `initialize_intake`
  - `process_user_answer`
  - `prepare_next_turn`
  - `provide_field_help`
  - `finalize_requirement`
- Atomic Skills:
  - `historical_case_matching`
  - `requirement_prefill`
  - `answer_parsing`
  - `answer_validation`
  - `dependency_assessment`
  - `conflict_resolution`
  - `requirement_completion`
  - `next_question_planning`
  - `field_explanation`
  - `capability_advisor`
  - `ac_generation`
- Prompt ownership inside the corresponding Skill package
- Metadata and dependency rules as shared deterministic domain assets
- Reducer-only mutation inside the Requirement Intake domain
- Requirement and AC artifact versioning
- Skill trace, prompt version, validation and feature-flag migration

No new central AI Case Manager should be introduced.

---

## 3. Core adjustment

### Previous Phase 1 goal

The previous implementation effectively targeted:

`Requirement Confirmed → AC Generated → Content Handoff → READY_FOR_CONTENT`

### Revised Phase 1 goal

The Requirement Intake Agent goal should be:

> Convert a user’s business requirement into a complete, consistent and user-confirmed Requirement Artifact, generate a validated Draft AC Package, and submit both to the human Requirement Review Gate.

The Requirement Intake Agent should stop after emitting:

`REQUIREMENT_REVIEW_SUBMITTED`

It must not independently decide that the Case can enter the Content stage.

After human review:

- `APPROVED` → Workflow Orchestrator triggers Content handoff.
- `CHANGES_REQUIRED` → Workflow Orchestrator routes the Case back to Requirement Rework mode.
- `REJECTED` → Workflow Orchestrator closes or escalates the Case according to business policy.

---

## 4. Revised Phase 1 state model

Recommended local and global states:

```text
DRAFT
  ↓
INTAKE_IN_PROGRESS
  ↓
READY_TO_CONFIRM
  ↓
REQUIREMENT_CONFIRMED
  ↓
DRAFT_AC_GENERATED
  ↓
READY_FOR_REQUIREMENT_REVIEW
  ↓
REQUIREMENT_REVIEW_SUBMITTED
  ├── APPROVED
  │      ↓
  │   READY_FOR_CONTENT
  ├── CHANGES_REQUIRED
  │      ↓
  │   REQUIREMENT_REWORK
  │      ↓
  │   READY_FOR_REQUIREMENT_REVIEW
  └── REJECTED / ESCALATED
```

### Ownership rule

- Requirement Intake Agent and Intake Reducer own:
  - draft fields
  - question state
  - conflicts
  - completion state
  - Requirement Artifact creation
  - Draft AC creation

- SDLC Workflow Orchestrator owns:
  - `REQUIREMENT_REVIEW_SUBMITTED`
  - `REQUIREMENT_REVIEW_APPROVED`
  - `REQUIREMENT_REVIEW_CHANGES_REQUIRED`
  - transition to `READY_FOR_CONTENT`
  - creation of the Content-stage work item

The local Agent must emit events; it must not directly control the global SDLC stage.

---

## 5. Required changes to current Composite Skills

### 5.1 `finalize_requirement`

Keep the Composite Skill, but change its terminal responsibility.

Required SOP:

1. Run dependency assessment.
2. Run requirement completion.
3. Verify all applicable P0 fields are confirmed.
4. Verify no invalid fields remain.
5. Verify no unresolved conflicts remain.
6. Verify no dependency blockers remain.
7. Build the final Requirement summary.
8. Wait for explicit user confirmation.
9. Create an immutable Requirement Artifact Version.
10. Set local state to `REQUIREMENT_CONFIRMED`.
11. Emit `REQUIREMENT_CONFIRMED`.

It must not set `READY_FOR_CONTENT`.

### 5.2 Replace `generate_and_handoff`

The current `generate_and_handoff` Composite Skill should be split or re-scoped.

Recommended replacement:

#### Composite capability: `generate_review_package`

SOP:

1. Load the confirmed Requirement Version.
2. Execute `ac_generation`.
3. Validate AC format.
4. Validate Channel × Language coverage.
5. Validate numbering and duplication.
6. Validate consistency with the confirmed Requirement.
7. Create Requirement Field → AC traceability.
8. Create an immutable Draft AC Artifact Version.
9. Build a Requirement Review Package.
10. Emit `REQUIREMENT_REVIEW_READY`.

Output:

```json
{
  "requirement_artifact_id": "REQ-...-V1",
  "draft_ac_artifact_id": "AC-...-V1",
  "review_package_id": "RRP-...-V1",
  "status": "READY_FOR_REQUIREMENT_REVIEW"
}
```

### 5.3 `content_handoff`

Keep `content_handoff` as an Atomic Skill or deterministic service, but change its trigger.

It may execute only when the Workflow Orchestrator supplies:

`REQUIREMENT_REVIEW_APPROVED`

It must not be called automatically after user confirmation.

Required preconditions:

- active Requirement Version exists;
- human Requirement Review status is `APPROVED`;
- active AC Version has passed validation;
- no unresolved Requirement Review issue exists;
- the approved Requirement and AC versions match the handoff package.

---

## 6. New integration capability: submit for human review

Add a deterministic Application Service or Composite Action:

`submit_requirement_for_review`

This does not require an LLM.

Responsibilities:

1. Validate the Requirement Review Package.
2. Freeze submitted Requirement and AC versions.
3. Create a review task.
4. Record reviewer group and due date.
5. Emit `REQUIREMENT_REVIEW_SUBMITTED`.
6. Set the global workflow state through the Workflow Orchestrator.
7. Prevent silent modification of the submitted version.

This capability should not be implemented as a new free-running Agent.

---

## 7. Review feedback and local remediation loop

A separate Review Resolution Agent is not required.

Use shared Review Feedback Processing Skills plus deterministic routing.

### Input event

```json
{
  "event_type": "REQUIREMENT_REVIEW_CHANGES_REQUIRED",
  "case_id": "CASE-001",
  "review_id": "REV-001",
  "reviewer_comment": "Fallback channel is not confirmed.",
  "reviewed_requirement_version": 1
}
```

### Processing

1. Parse the reviewer comment.
2. Classify the issue.
3. Map the issue to affected Requirement fields.
4. Calculate affected dependent fields and AC items.
5. Create structured review issues.
6. Open a new working Requirement Draft based on the reviewed version.
7. Start Requirement Intake Agent in `REWORK_MODE`.
8. Ask only the minimum necessary questions.
9. Create Requirement Version 2 after user confirmation.
10. Regenerate only affected AC items.
11. Resubmit for human review.

### Minimal issue contract

```json
{
  "issue_id": "ISSUE-001",
  "source": "REQUIREMENT_REVIEW",
  "category": "MISSING_CONFIGURATION",
  "affected_fields": ["fallback_channel"],
  "severity": "BLOCKER",
  "reviewer_comment": "Fallback channel is not confirmed.",
  "status": "OPEN",
  "requires_user_input": true
}
```

### Rework mode rule

The Agent must not restart all 33 fields.

Question priority in `REWORK_MODE`:

1. fields explicitly referenced by review issues;
2. dependent fields invalidated by those changes;
3. new conflicts introduced by the change;
4. remaining unconfirmed P0 fields;
5. optional fields.

---

## 8. Reducer boundary adjustment

The existing Reducer-only design remains correct, but the boundary must be clarified.

### Intake Reducer may update

- field values and statuses;
- active question state;
- local conflicts;
- completion state;
- working draft;
- Requirement Artifact references;
- Draft AC Artifact references;
- local state version.

### Intake Reducer must not update

- global SDLC stage after review submission;
- reviewer decision;
- Compliance state;
- Content stage state;
- UAT or Release state.

### Workflow Orchestrator owns

- stage transitions;
- approval gates;
- review task lifecycle;
- transition to Content;
- global Case status;
- cross-stage task creation.

The Requirement Intake Agent should emit domain events. The Workflow Orchestrator applies global transitions.

---

## 9. Required event contracts

Phase 1 should publish:

- `REQUIREMENT_INTAKE_STARTED`
- `REQUIREMENT_DRAFT_UPDATED`
- `REQUIREMENT_READY_TO_CONFIRM`
- `REQUIREMENT_CONFIRMED`
- `DRAFT_AC_GENERATED`
- `REQUIREMENT_REVIEW_READY`
- `REQUIREMENT_REVIEW_SUBMITTED`
- `REQUIREMENT_REWORK_COMPLETED`

Phase 1 should consume:

- `REQUIREMENT_REVIEW_APPROVED`
- `REQUIREMENT_REVIEW_CHANGES_REQUIRED`
- `REQUIREMENT_REVIEW_REJECTED`

The Workflow Orchestrator should publish:

- `CONTENT_STAGE_READY`

Only after approval should the Content handoff package be created or activated.

---

## 10. API adjustments

Recommended APIs:

```text
POST /api/intake/{case_id}/confirm
POST /api/intake/{case_id}/ac/generate
POST /api/intake/{case_id}/review-package
POST /api/intake/{case_id}/review/submit
POST /api/intake/{case_id}/review-feedback
POST /api/intake/{case_id}/content/handoff
```

### Guard rules

`/content/handoff` must return a business error unless:

```text
requirement_review_status == APPROVED
```

`/review/submit` must fail unless:

- Requirement Version exists;
- AC Version exists and is valid;
- review package schema is valid;
- no blocking local issue remains.

---

## 11. Updated test strategy

### Existing tests to retain

- Agent Runner and Policy tests
- Atomic and Composite Skill tests
- Prompt ownership tests
- Reducer-only mutation tests
- Requirement completion tests
- AC validation tests
- Feature flag tests

### Tests to change

The existing Phase 1 E2E must no longer end directly at `READY_FOR_CONTENT`.

New E2E A — Requirement submission:

```text
Create Requirement
→ Historical Matching
→ Prefill
→ Guided Questions
→ Field Help
→ Complete P0 Fields
→ Final Confirm
→ Requirement Version
→ Generate Draft AC
→ Validate AC
→ Build Review Package
→ Submit for Human Review
→ REQUIREMENT_REVIEW_SUBMITTED
```

New E2E B — Approved path:

```text
REQUIREMENT_REVIEW_APPROVED
→ Workflow Orchestrator
→ Content Handoff
→ CONTENT_STAGE_READY
```

New E2E C — Rework path:

```text
REQUIREMENT_REVIEW_CHANGES_REQUIRED
→ Structured Issue
→ Requirement Rework Mode
→ Targeted Questions
→ Requirement Version 2
→ Affected AC Regeneration
→ Resubmit for Review
```

### Mandatory acceptance gates

- Requirement Intake Agent cannot bypass the review gate.
- `READY_FOR_CONTENT` cannot be reached without approval.
- Review feedback does not restart all fields.
- Submitted Requirement Version is immutable.
- A rework creates a new Requirement Version.
- Old AC items affected by changes are invalidated.
- Unaffected fields and AC items remain stable.
- Global stage transitions are performed only by the Workflow Orchestrator.

---

## 12. Current implementation migration plan

### Step 1 — Audit current terminal state

Inspect:

- `finalize_requirement`
- `generate_and_handoff`
- `content_handoff`
- API endpoint routing
- reducer state transitions
- current E2E assertions

Identify every place that directly sets:

- `READY_FOR_CONTENT`
- active Content handoff
- Content-stage status

### Step 2 — Re-scope current capabilities

- Keep `finalize_requirement`.
- Replace or rename `generate_and_handoff` to `generate_review_package`.
- Guard `content_handoff` behind review approval.
- Add `submit_requirement_for_review`.

### Step 3 — Add workflow events

Implement the event contracts and idempotency keys.

### Step 4 — Add review rework entry point

Implement `REWORK_MODE` and targeted question planning.

### Step 5 — Update tests

Replace the direct Confirm → Handoff E2E with submission, approval and rework paths.

### Step 6 — Update documentation

Update:

- Phase 1 technical design
- Phase 1 implementation status
- state machine
- call graph
- endpoint routing audit
- Skill audit
- E2E acceptance document

---

## 13. Revised Phase 1 definition of done

Phase 1 is complete when:

1. Requirement Intake Agent produces a complete and confirmed Requirement Artifact.
2. Draft AC is generated and validated.
3. A review package is created and submitted to the human Requirement Review Gate.
4. The Agent cannot move the Case to Content without approval.
5. Approval triggers Content handoff through the Workflow Orchestrator.
6. Changes Required creates structured issues and opens targeted Requirement rework.
7. Rework creates a new Requirement Version and invalidates only affected AC items.
8. All local state changes pass through the Intake Reducer.
9. All global stage transitions pass through the Workflow Orchestrator.
10. Prompt ownership, Skill trace and Feature Flag behavior remain valid.
11. E2E tests cover submission, approval and rework paths.
12. Resume remains explicitly deferred and is not a Phase 1 blocker.

---

## 14. Final architecture conclusion

The Phase 1 Requirement Intake Agent does not need to be rebuilt.

The necessary adjustment is to change its role from:

**“Complete Requirement and directly hand off to Content”**

to:

**“Complete Requirement, generate a validated review package, and participate in a human-governed local remediation loop.”**

The global SDLC flow must be controlled by the deterministic Workflow Orchestrator, not by the Requirement Intake Agent and not by a central AI Case Manager.
