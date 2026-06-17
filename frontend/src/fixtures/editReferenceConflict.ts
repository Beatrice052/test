import type { AssistantCard, BuildDraftResponse, FormModule, ValidationResult } from "../api/types";

export const editReferenceRequirement =
  "We have a new business scenario about investment shopping cart. When customers add investment products into the HASE mobile app cart and the products are close to expiry, the system should trigger a message. The message should be sent to the customer's mobile phone based on the customer's language preference.";

export const editReferenceInitialCards: AssistantCard[] = [
  {
    type: "summary",
    title: "Requirement understood",
    body: "I understood this as a WPB wealth product messaging use case. I detected department 124, likely LOB WPB, and historical channel usage led by SMS."
  },
  {
    type: "summary",
    title: "Reference recommendation",
    body: "I recommend using RDP 004 as the reference. You can use it as a base, confirm it directly, or start a new use case if it is not suitable."
  },
  {
    type: "question",
    question_id: "q_channel_conflict",
    title: "Questions",
    question: "Who is the target customer segment, is this a service reminder, and should the channel remain SMS, change to Email, change to Mobile Push, or use multiple channels?",
    question_type: "SINGLE_CHOICE",
    options: [
      { label: "Wealth customers - Email only", value: "Email" },
      { label: "Wealth customers - SMS", value: "SMS" },
      { label: "Use Mobile Push", value: "Mobile Push" },
      { label: "Service reminder", value: "Service reminder" }
    ],
    focus_fields: ["selected_delivery_channel"],
    why_asking: "The channel determines sender setup, opt-in, routing, and downstream content fields.",
    priority: "P0"
  }
];

export const editReferenceModulesBefore: Record<string, FormModule> = {
  business: {
    id: "business",
    title: "Business Context",
    complete: 8,
    total: 10,
    fields: [
      {
        name: "use_case_name",
        displayName: "Use Case Name",
        value: "Investment cart expiry reminder",
        status: "AI Prefilled",
        source: "From requirement",
        help: "Short business name used to identify this intake."
      },
      {
        name: "line_of_business",
        displayName: "Line of Business",
        value: "WPB",
        status: "AI Prefilled",
        source: "From requirement",
        help: "Business owner for the use case."
      },
      {
        name: "message_purpose",
        displayName: "Message Purpose",
        value: "Service reminder",
        status: "Reference Prefilled",
        source: "From reference",
        help: "Customer-facing purpose of the communication."
      },
      {
        name: "source_system",
        displayName: "Source System",
        value: "PEGA",
        status: "AI Prefilled",
        source: "From reference",
        help: "System of record for the historical use case."
      }
    ]
  },
  audience: {
    id: "audience",
    title: "Audience & Trigger",
    complete: 4,
    total: 8,
    fields: [
      {
        name: "target_audience",
        displayName: "Target Audience",
        value: "Customers with investment products in HASE mobile app cart close to expiry",
        status: "AI Prefilled",
        source: "From requirement",
        help: "Customers eligible to receive this message."
      },
      {
        name: "trigger_scenario",
        displayName: "Trigger Scenario",
        value: "Investment cart product close to expiry",
        status: "Needs Confirmation",
        source: "From reference",
        help: "Business event that starts the communication."
      }
    ]
  },
  channel: {
    id: "channel",
    title: "Channel & Content",
    complete: 5,
    total: 12,
    fields: [
      {
        name: "selected_delivery_channel",
        displayName: "Channel Setup",
        value: "SMS",
        status: "AI Prefilled",
        source: "From reference",
        help: "Confirmed customer delivery channel."
      },
      {
        name: "sms_sender_id",
        displayName: "SMS Sender ID",
        value: "HSBC",
        status: "Reference Prefilled",
        source: "From reference",
        help: "Sender ID used for SMS delivery."
      },
      {
        name: "email_sender_name",
        displayName: "Email Sender Name",
        value: "",
        status: "Not Applicable",
        source: "Default",
        help: "Required only when Email is selected.",
        hidden: true
      }
    ]
  },
  compliance: {
    id: "compliance",
    title: "Compliance & Launch",
    complete: 3,
    total: 9,
    fields: [
      {
        name: "consent_basis",
        displayName: "Consent Basis",
        value: "Service communication",
        status: "Needs Confirmation",
        source: "From reference",
        help: "Consent or servicing basis used for sending."
      },
      {
        name: "launch_window",
        displayName: "Launch Window",
        value: "TBD",
        status: "Missing Required",
        source: "Default",
        help: "Expected launch timing."
      }
    ]
  }
};

export const editReferenceModulesAfterEmail: Record<string, FormModule> = {
  ...editReferenceModulesBefore,
  channel: {
    ...editReferenceModulesBefore.channel,
    complete: 5,
    total: 12,
    fields: [
      {
        name: "selected_delivery_channel",
        displayName: "Channel Setup",
        value: "Email",
        status: "Confirmed",
        source: "User confirmed",
        help: "Confirmed customer delivery channel."
      },
      {
        name: "email_sender_name",
        displayName: "Email Sender Name",
        value: "",
        status: "Missing Required",
        source: "Default",
        help: "Required when Email is selected.",
        required: true
      },
      {
        name: "sms_sender_id",
        displayName: "SMS Sender ID",
        value: "",
        status: "Not Applicable",
        source: "Default",
        help: "Hidden because Email only is selected.",
        hidden: true
      }
    ]
  }
};

export const editReferenceValidation: ValidationResult = {
  ready_for_ac: false,
  blocking_issues: [
    {
      field_name: "email_sender_name",
      display_name: "Email Sender Name",
      message: "Email sender name is required when Email is selected."
    }
  ],
  warnings: []
};

export const editReferenceDraft: BuildDraftResponse = {
  intake_id: "INTAKE-001",
  mode: "EDIT_REFERENCE",
  requirement: editReferenceRequirement,
  extracted_signals: {
    lob: "WPB",
    channel: "SMS",
    trigger: "Investment product expiry",
    audience: "Investment cart customers"
  },
  selected_reference: {
    id: "M1004",
    name: "RDP 004",
    source_system: "PEGA",
    channel: "SMS",
    status: "Conflicts found"
  },
  modules: editReferenceModulesBefore,
  assistant_cards: editReferenceInitialCards,
  validation: editReferenceValidation
};
