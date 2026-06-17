import type {
  ApplyPreviewResponse,
  AnalyzeRequirementResponse,
  BuildDraftRequest,
  BuildDraftResponse,
  ExportForAcResponse,
  IntakeApiClient,
  ParseAnswerResponse,
  UpdateFieldResponse,
  ValidationResult
} from "./types";
import {
  editReferenceDraft,
  editReferenceModulesAfterEmail,
  editReferenceValidation
} from "../fixtures/editReferenceConflict";
import { createNewDraft, createNewModules, createNewValidation } from "../fixtures/createNewBasic";

const wait = (ms = 260) => new Promise((resolve) => window.setTimeout(resolve, ms));
const clone = <T>(value: T): T => structuredClone(value);

let modulesByIntake: Record<string, BuildDraftResponse["modules"]> = {};
let validationByIntake: Record<string, ValidationResult> = {};
let pendingChannelByIntake: Record<string, string> = {};

function validateModules(modules: BuildDraftResponse["modules"]): ValidationResult {
  const allFields = Object.values(modules).flatMap((module) => module.fields);
  const blocking_issues = allFields
    .filter((field) => field.status === "Missing Required" && !field.hidden)
    .map((field) => ({
      field_name: field.name,
      display_name: field.displayName,
      message:
        field.name === "email_sender_name"
          ? "Email sender name is required when Email is selected."
          : `${field.displayName} is required.`
    }));

  return {
    ready_for_ac: blocking_issues.length === 0,
    blocking_issues,
    warnings: []
  };
}

function updateFieldInModules(
  modules: BuildDraftResponse["modules"],
  fieldName: string,
  value: string
): BuildDraftResponse["modules"] {
  const next = clone(modules);
  for (const module of Object.values(next)) {
    const field = module.fields.find((item) => item.name === fieldName);
    if (field) {
      field.value = value;
      field.status = value.trim() ? "Confirmed" : field.required ? "Missing Required" : "Optional";
      field.source = "User confirmed";
    }
    const visibleFields = module.fields.filter((item) => !item.hidden && item.status !== "Not Applicable");
    module.complete = visibleFields.filter((item) =>
      ["Confirmed", "AI Prefilled", "Reference Prefilled", "Optional"].includes(item.status)
    ).length;
    module.total = module.fields.filter((item) => !item.hidden).length + Math.max(module.total - module.fields.length, 0);
  }
  return next;
}

export const mockClient: IntakeApiClient = {
  async analyzeRequirement(intakeId: string, requirement: string): Promise<AnalyzeRequirementResponse> {
    await wait();
    return {
      intake_id: intakeId,
      requirement,
      extracted_signals: {
        lob: "WPB",
        channel: requirement.toLowerCase().includes("email") ? "EMAIL" : "SMS",
        trigger: "Investment product expiry",
        audience: "Investment cart customers"
      },
      candidates: [
        {
          id: "M1004",
          name: "RDP 004",
          project: "Investment cart expiry reminder",
          source_system: "PEGA",
          lob: "WPB",
          channel: "SMS",
          similarity: "0.86",
          badge: "Best match",
          reason: "Same LOB and similar investment product expiry trigger. Historical channel is SMS, so channel needs confirmation."
        },
        {
          id: "M2031",
          name: "RDP 031",
          project: "Wealth product maturity reminder",
          source_system: "PEGA",
          lob: "WPB",
          channel: "EMAIL",
          similarity: "0.72",
          badge: "Possible match",
          reason: "Related wealth product lifecycle reminder, but less aligned with HASE mobile app cart behavior."
        }
      ],
      assistant_cards: [
        {
          type: "summary",
          title: "Requirement understood",
          body: "I extracted initial business signals and found related historical use cases."
        },
        {
          type: "question",
          question_id: "q_reference_choice",
          title: "Choose how to continue",
          question: "Would you like to use one of the historical use cases as a reference, or create a brand-new use case?",
          question_type: "SINGLE_CHOICE",
          options: [
            { label: "Use RDP 004 as reference", value: "M1004" },
            { label: "Create a new use case", value: "CREATE_NEW" }
          ],
          focus_fields: ["reference_selection"],
          why_asking: "The selected path determines whether historical values are inherited.",
          priority: "P0"
        }
      ]
    };
  },

  async buildDraft(intakeId: string, request: BuildDraftRequest): Promise<BuildDraftResponse> {
    await wait();
    const base = request.mode === "CREATE_NEW" ? createNewDraft : editReferenceDraft;
    const response = clone({
      ...base,
      intake_id: intakeId,
      mode: request.mode,
      requirement: request.requirement
    });
    modulesByIntake[intakeId] = response.modules;
    validationByIntake[intakeId] = response.validation;
    return response;
  },

  async parseAnswer(intakeId: string, questionId: string, answer: string): Promise<ParseAnswerResponse> {
    await wait();
    const normalized = answer.toLowerCase();

    if (questionId === "q_channel_conflict") {
      const selectedChannel = normalized.includes("email")
        ? "Email"
        : normalized.includes("push")
          ? "Mobile Push"
          : "SMS";
      pendingChannelByIntake[intakeId] = selectedChannel;
      return {
        user_message: answer,
        assistant_cards: [
          {
            type: "action_preview",
            title: "Action Preview",
            action_preview: {
              preview_id: "preview_001",
              user_facing_updates: [
                {
                  field_name: "selected_delivery_channel",
                  display_name: "Channel Setup",
                  old_value: "SMS",
                  new_value: selectedChannel,
                  reason: `User confirmed ${selectedChannel}.`
                },
                {
                  field_name: "message_purpose",
                  display_name: "Message Purpose",
                  old_value: "Service reminder",
                  new_value: normalized.includes("marketing") ? "Marketing message" : "Service reminder",
                  reason: "User response confirmed the message purpose."
                }
              ],
              follow_up_summary: "After applying this, I will ask only for the next user-facing required setup field."
            }
          }
        ]
      };
    }

    if (questionId === "q_channel_new") {
      const selectedChannel = answer.includes("SMS + Email")
        ? "SMS + Email"
        : answer.includes("Mobile Push")
          ? "Mobile Push"
          : answer.includes("SMS")
            ? "SMS"
            : "Email";
      pendingChannelByIntake[intakeId] = selectedChannel;
      return {
        user_message: answer,
        assistant_cards: [
          {
            type: "action_preview",
            title: "Action Preview",
            action_preview: {
              preview_id: "preview_new_channel",
              user_facing_updates: [
                {
                  field_name: "selected_delivery_channel",
                  display_name: "Channel Setup",
                  old_value: "Not selected",
                  new_value: selectedChannel,
                  reason: "User selected the delivery channel."
                }
              ],
              follow_up_summary: "After applying this, sender setup questions will be unlocked."
            }
          }
        ]
      };
    }

    return {
      user_message: answer,
      assistant_cards: [
        {
          type: "summary",
          title: "Answer captured",
          body: "I captured your response and updated the draft where it is user-facing."
        }
      ]
    };
  },

  async applyPreview(intakeId: string, previewId: string): Promise<ApplyPreviewResponse> {
    await wait();

    if (previewId === "preview_001") {
      const selectedChannel = pendingChannelByIntake[intakeId] ?? "SMS";
      const baseModules = selectedChannel === "Email"
        ? clone(editReferenceModulesAfterEmail)
        : updateFieldInModules(modulesByIntake[intakeId] ?? editReferenceDraft.modules, "selected_delivery_channel", selectedChannel);
      const modules = updateFieldInModules(baseModules, "message_purpose", "Service reminder");
      const validation = validateModules(modules);
      modulesByIntake[intakeId] = modules;
      validationByIntake[intakeId] = validation;
      return {
        modules,
        validation,
        assistant_cards:
          selectedChannel === "Email"
            ? [
                {
                  type: "summary",
                  title: "Channel updated",
                  body: "Email is now selected for this use case."
                },
                {
                  type: "question",
                  question_id: "q_email_sender_name",
                  title: "Confirm email sender",
                  question: "Which email sender name should be shown to the customer?",
                  question_type: "FREE_TEXT",
                  focus_fields: ["email_sender_name"],
                  why_asking: "Email sender name is required when Email is selected."
                }
              ]
            : [
                {
                  type: "summary",
                  title: "Channel updated",
                  body: `${selectedChannel} is now selected for this use case.`
                },
                {
                  type: "question",
                  question_id: "q_launch_window",
                  title: "Confirm launch window",
                  question: "When should this reminder flow go live?",
                  question_type: "FREE_TEXT",
                  focus_fields: ["launch_window"],
                  why_asking: "Launch timing is required before AC generation."
                }
              ]
      };
    }

    if (previewId === "preview_new_channel") {
      const selectedChannel = pendingChannelByIntake[intakeId] ?? "Email";
      const modules = updateFieldInModules(createNewModules, "selected_delivery_channel", selectedChannel);
      modules.channel.fields = modules.channel.fields.map((field) =>
        field.name === "email_sender_name" && selectedChannel.includes("Email")
          ? { ...field, hidden: false, status: "Missing Required", required: true, help: "Required when Email is selected." }
          : field.name === "sms_sender_id" && selectedChannel.includes("SMS")
            ? { ...field, hidden: false, status: "Missing Required", required: true, help: "Required when SMS is selected." }
          : field
      );
      const validation = validateModules(modules);
      modulesByIntake[intakeId] = modules;
      validationByIntake[intakeId] = validation;
      return {
        modules,
        validation,
        assistant_cards: [
          {
            type: "summary",
            title: "Channel selected",
            body: "Email is now selected. I will collect email sender setup next."
          },
          {
            type: "question",
            question_id: "q_email_sender_name",
            title: "Confirm email sender",
            question: "Which email sender name should be shown to the customer?",
            question_type: "FREE_TEXT",
            focus_fields: ["email_sender_name"],
            why_asking: "Email sender name is required when Email is selected."
          }
        ]
      };
    }

    return {
      modules: modulesByIntake[intakeId] ?? {},
      assistant_cards: [],
      validation: validationByIntake[intakeId] ?? createNewValidation
    };
  },

  async updateField(intakeId: string, fieldName: string, value: string): Promise<UpdateFieldResponse> {
    await wait();
    const modules = updateFieldInModules(modulesByIntake[intakeId] ?? createNewModules, fieldName, value);
    const validation = validateModules(modules);
    modulesByIntake[intakeId] = modules;
    validationByIntake[intakeId] = validation;

    return {
      modules,
      validation,
      assistant_cards:
        fieldName === "email_sender_name" && value.trim()
          ? [
              {
                type: "summary",
                title: "Sender captured",
                body: `${value} is now set as the email sender name.`
              }
            ]
          : []
    };
  },

  async validate(intakeId: string): Promise<ValidationResult> {
    await wait();
    const validation = validateModules(modulesByIntake[intakeId] ?? createNewModules);
    validationByIntake[intakeId] = validation;
    return validation;
  },

  async exportForAc(intakeId: string): Promise<ExportForAcResponse> {
    await wait();
    const modules = modulesByIntake[intakeId] ?? {};
    const confirmed_use_case = Object.fromEntries(
      Object.values(modules)
        .flatMap((module) => module.fields)
        .filter((field) => !field.hidden && field.value)
        .map((field) => [field.name, field.value])
    );
    const validation = validateModules(modules);
    return {
      ready_for_ac: validation.ready_for_ac,
      confirmed_use_case,
      semantic_summary:
        "WPB wealth product maturity reminder sent by Email to customers whose products mature soon."
    };
  }
};
