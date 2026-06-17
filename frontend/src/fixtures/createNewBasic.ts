import type { AssistantCard, BuildDraftResponse, FormModule, ValidationResult } from "../api/types";

export const createNewRequirement =
  "Create a new use case to notify wealth customers when their products will mature soon.";

export const createNewCards: AssistantCard[] = [
  {
    type: "summary",
    title: "New use case started",
    body: "I will create a new use case from your requirement instead of inheriting historical fields."
  },
  {
    type: "question",
    question_id: "q_audience_trigger",
    title: "Confirm audience and trigger",
    question:
      "I identified the audience as wealth customers with products maturing soon. Are there any additional eligibility or exclusion rules?",
    question_type: "FREE_TEXT",
    focus_fields: ["customer_eligibility", "customer_exclusion"]
  },
  {
    type: "question",
    question_id: "q_channel_new",
    title: "Confirm delivery channel",
    question: "Which channel should be used for this message?",
    question_type: "SINGLE_CHOICE",
    options: [
      { label: "SMS", value: "SMS" },
      { label: "Email", value: "Email" },
      { label: "Mobile Push", value: "Mobile Push" },
      { label: "SMS + Email", value: "SMS + Email" }
    ],
    focus_fields: ["selected_delivery_channel"],
    why_asking: "Channel must be confirmed before sender setup and routing fields are asked."
  }
];

export const createNewModules: Record<string, FormModule> = {
  business: {
    id: "business",
    title: "Business Context",
    complete: 5,
    total: 10,
    fields: [
      {
        name: "line_of_business",
        displayName: "Line of Business",
        value: "WPB",
        status: "AI Prefilled",
        source: "From requirement",
        help: "Detected from the requirement text."
      },
      {
        name: "message_purpose",
        displayName: "Message Purpose",
        value: "Product maturity reminder",
        status: "AI Prefilled",
        source: "From requirement",
        help: "Business purpose inferred from the requested communication."
      }
    ]
  },
  audience: {
    id: "audience",
    title: "Audience & Trigger",
    complete: 3,
    total: 8,
    fields: [
      {
        name: "target_audience",
        displayName: "Target Audience",
        value: "Wealth customers with products maturing soon",
        status: "AI Prefilled",
        source: "From requirement",
        help: "Initial audience extracted from the requirement."
      },
      {
        name: "customer_eligibility",
        displayName: "Eligibility Rules",
        value: "",
        status: "Missing Required",
        source: "Default",
        help: "Additional inclusion criteria for the target audience."
      },
      {
        name: "customer_exclusion",
        displayName: "Exclusion Rules",
        value: "",
        status: "Optional",
        source: "Default",
        help: "Customers that should not receive the message."
      }
    ]
  },
  channel: {
    id: "channel",
    title: "Channel & Content",
    complete: 2,
    total: 12,
    fields: [
      {
        name: "selected_delivery_channel",
        displayName: "Channel Setup",
        value: "",
        status: "Missing Required",
        source: "Default",
        help: "Choose the delivery channel before sender setup is requested."
      },
      {
        name: "sms_sender_id",
        displayName: "SMS Sender ID",
        value: "",
        status: "Not Applicable",
        source: "Default",
        help: "Hidden until SMS is selected.",
        hidden: true
      },
      {
        name: "email_sender_name",
        displayName: "Email Sender Name",
        value: "",
        status: "Not Applicable",
        source: "Default",
        help: "Hidden until Email is selected.",
        hidden: true
      }
    ]
  },
  compliance: {
    id: "compliance",
    title: "Compliance & Launch",
    complete: 2,
    total: 9,
    fields: [
      {
        name: "consent_basis",
        displayName: "Consent Basis",
        value: "Service communication",
        status: "AI Prefilled",
        source: "From requirement",
        help: "Initial compliance basis for this reminder."
      },
      {
        name: "launch_window",
        displayName: "Launch Window",
        value: "",
        status: "Missing Required",
        source: "Default",
        help: "Expected launch timing."
      }
    ]
  }
};

export const createNewValidation: ValidationResult = {
  ready_for_ac: false,
  blocking_issues: [
    {
      field_name: "selected_delivery_channel",
      display_name: "Channel Setup",
      message: "Channel must be confirmed before sender setup and routing fields are asked."
    }
  ],
  warnings: []
};

export const createNewDraft: BuildDraftResponse = {
  intake_id: "INTAKE-002",
  mode: "CREATE_NEW",
  requirement: createNewRequirement,
  extracted_signals: {
    lob: "WPB",
    trigger: "Product maturity",
    audience: "Wealth customers with maturing products"
  },
  modules: createNewModules,
  assistant_cards: createNewCards,
  validation: createNewValidation
};
