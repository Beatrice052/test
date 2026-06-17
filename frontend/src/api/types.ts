export type IntakeMode = "CREATE_NEW" | "EDIT_REFERENCE" | "CONFIRM_DIRECTLY";
export type FieldStatus =
  | "Confirmed"
  | "AI Prefilled"
  | "Reference Prefilled"
  | "Needs Confirmation"
  | "Missing Required"
  | "Optional"
  | "Not Applicable";
export type FieldSource = "From requirement" | "From reference" | "User confirmed" | "Default";
export type Priority = "P0" | "P1" | "P2";

export type ExtractedSignals = {
  lob?: string;
  channel?: string;
  trigger?: string;
  audience?: string;
};

export type ReferenceUseCase = {
  id: string;
  name: string;
  source_system: string;
  channel: string;
  status?: string;
};

export type UseCaseCandidate = {
  id: string;
  name: string;
  project: string;
  source_system: string;
  lob: string;
  channel: string;
  similarity: string;
  badge: string;
  reason: string;
};

export type FormField = {
  name: string;
  displayName: string;
  value: string;
  status: FieldStatus;
  source: FieldSource;
  help: string;
  required?: boolean;
  hidden?: boolean;
  options?: Array<{ label: string; value: string; description?: string }>;
};

export type FormModule = {
  id: string;
  title: string;
  complete: number;
  total: number;
  fields: FormField[];
};

export type SummaryCard = {
  type: "summary";
  title: string;
  body: string;
};

export type FindingCard = {
  type: "finding";
  title: string;
  body: string;
};

export type QuestionCard = {
  type: "question";
  group_id?: string;
  question_id: string;
  title: string;
  question: string;
  question_type: "SINGLE_CHOICE" | "FREE_TEXT";
  options?: Array<{ label: string; value: string }>;
  focus_fields: string[];
  why_asking?: string;
  priority?: Priority;
};

export type ActionPreviewUpdate = {
  field_name: string;
  display_name: string;
  old_value: string;
  new_value: string;
  reason: string;
};

export type ActionPreview = {
  preview_id: string;
  user_facing_updates: ActionPreviewUpdate[];
  follow_up_summary?: string;
};

export type ActionPreviewCard = {
  type: "action_preview";
  title: string;
  action_preview: ActionPreview;
};

export type ValidationCard = {
  type: "validation";
  title: string;
  ready_for_ac: boolean;
  body: string;
};

export type FieldExplanationCard = {
  type: "field_explanation";
  title: string;
  field_name: string;
  body: string;
};

export type AssistantCard =
  | SummaryCard
  | FindingCard
  | QuestionCard
  | ActionPreviewCard
  | ValidationCard
  | FieldExplanationCard;

export type BlockingIssue = {
  field_name: string;
  display_name: string;
  message: string;
};

export type ValidationResult = {
  ready_for_ac: boolean;
  blocking_issues: BlockingIssue[];
  warnings: BlockingIssue[];
};

export type BuildDraftRequest = {
  mode: IntakeMode;
  requirement: string;
  selected_reference_use_case_id?: string;
};

export type AnalyzeRequirementResponse = {
  intake_id: string;
  requirement: string;
  extracted_signals: ExtractedSignals;
  candidates: UseCaseCandidate[];
  assistant_cards: AssistantCard[];
};

export type BuildDraftResponse = {
  intake_id: string;
  mode: IntakeMode;
  requirement: string;
  extracted_signals: ExtractedSignals;
  selected_reference?: ReferenceUseCase;
  modules: Record<string, FormModule>;
  assistant_cards: AssistantCard[];
  validation: ValidationResult;
};

export type ParseAnswerResponse = {
  user_message: string;
  assistant_cards: AssistantCard[];
};

export type ApplyPreviewResponse = {
  modules: Record<string, FormModule>;
  assistant_cards: AssistantCard[];
  validation: ValidationResult;
};

export type UpdateFieldResponse = ApplyPreviewResponse;

export type ExportForAcResponse = {
  ready_for_ac: boolean;
  confirmed_use_case: Record<string, string>;
  semantic_summary: string;
};

export interface IntakeApiClient {
  analyzeRequirement(intakeId: string, requirement: string): Promise<AnalyzeRequirementResponse>;
  buildDraft(intakeId: string, request: BuildDraftRequest): Promise<BuildDraftResponse>;
  parseAnswer(intakeId: string, questionId: string, answer: string): Promise<ParseAnswerResponse>;
  applyPreview(intakeId: string, previewId: string): Promise<ApplyPreviewResponse>;
  updateField(intakeId: string, fieldName: string, value: string): Promise<UpdateFieldResponse>;
  validate(intakeId: string): Promise<ValidationResult>;
  exportForAc(intakeId: string): Promise<ExportForAcResponse>;
}
