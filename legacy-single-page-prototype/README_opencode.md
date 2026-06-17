# Requirement Intake Frontend V5 - Product Prototype Aligned Assistant

## Why V5

The product team prototype shows a right-side Copilot conversation flow:

1. Welcome
2. User says requirement
3. Assistant understands the requirement
4. Assistant recommends a reference use case
5. Assistant asks key questions
6. User answers in natural language
7. Assistant shows Action Preview
8. User confirms updates
9. Assistant explains fields when asked

V5 implements this flow more faithfully than V4 while keeping our cleaner ToB layout and four-module form.

## What changed

- Removed Guidance / Chat split.
- Right panel is now one continuous guided conversation.
- Added Bot/User bubble layout similar to product's prototype.
- Added question block with quick replies.
- Added natural-language user answer simulation.
- Added Action Preview that can be confirmed and applied to the form.
- Added Field Explanation block with module jump.
- User can type a reply, then the frontend creates a mock action preview.
- The Confirm button applies updates to the form and AC preview.

## Files

```text
requirement_intake_frontend_v5/
  index.html
  styles.css
  app.js
  README_opencode.md
```

## Backend integration

Replace the mock parsing in `buildPreviewFromUserText()` with a backend call:

```http
POST /api/intake/{intake_id}/assistant/parse-user-message
```

Suggested request:

```json
{
  "message": "The target customers are customers holding wealth products that will mature soon. Send email only.",
  "current_draft_use_case": {},
  "selected_reference": {}
}
```

Suggested response:

```json
{
  "action_preview": {
    "updates": [
      {
        "field": "target_customer_segment",
        "label": "Target Customer Segment",
        "old_value": "",
        "value": "Customers holding wealth products that will mature soon",
        "reason": "Extracted from user reply"
      },
      {
        "field": "channel_setup",
        "label": "Channel Setup",
        "old_value": "SMS",
        "value": "Email",
        "reason": "User said send email only"
      }
    ]
  }
}
```

Apply preview endpoint:

```http
POST /api/intake/{intake_id}/assistant/apply-actions
```

## Assistant copy strategy

The Assistant should be concise and procedural:

- "I understood..."
- "I recommend..."
- "Please answer..."
- "I will apply..."
- "This field means..."

Avoid:
- Too many separate modes/tabs
- Long explanations
- Technical field names in user-facing text
- Raw JSON
