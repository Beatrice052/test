import { useCallback, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type {
  ActionPreview,
  AssistantCard,
  BuildDraftRequest,
  ExportForAcResponse,
  FormModule,
  IntakeMode,
  ReferenceUseCase,
  UseCaseCandidate,
  ValidationResult
} from "../api/types";
import { createNewRequirement } from "../fixtures/createNewBasic";
import { editReferenceRequirement } from "../fixtures/editReferenceConflict";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
};

export type IntakeState = {
  intakeId: string;
  mode: IntakeMode;
  requirement: string;
  extractedSignals: BuildDraftRequest extends never ? never : Record<string, string | undefined>;
  selectedReference?: ReferenceUseCase;
  modules: Record<string, FormModule>;
  assistantCards: AssistantCard[];
  chatMessages: ChatMessage[];
  currentActionPreview?: ActionPreview;
  validation?: ValidationResult;
  exportResult?: ExportForAcResponse;
  loading: boolean;
  error?: string;
  toast?: string;
  started: boolean;
  phase: "idle" | "analyzed" | "draft";
  candidates: UseCaseCandidate[];
};

const scenarios: Record<"edit" | "create", BuildDraftRequest & { intakeId: string }> = {
  edit: {
    intakeId: "INTAKE-001",
    mode: "EDIT_REFERENCE",
    requirement: editReferenceRequirement,
    selected_reference_use_case_id: "M1004"
  },
  create: {
    intakeId: "INTAKE-002",
    mode: "CREATE_NEW",
    requirement: createNewRequirement
  }
};

export function useIntakeStore() {
  const [scenario, setScenario] = useState<"edit" | "create">("edit");
  const [state, setState] = useState<IntakeState>({
    intakeId: "INTAKE-NEW",
    mode: "EDIT_REFERENCE",
    requirement: "",
    extractedSignals: {},
    modules: {},
    assistantCards: [],
    chatMessages: [],
    loading: false,
    started: false,
    phase: "idle",
    candidates: []
  });

  const buildDraft = useCallback(async (request: BuildDraftRequest & { intakeId: string }, nextScenario: "edit" | "create") => {
    setState((current) => ({
      ...current,
      loading: true,
      error: undefined,
      toast: undefined,
      exportResult: undefined,
      currentActionPreview: undefined
    }));

    try {
      const response = await apiClient.buildDraft(request.intakeId, request);
      setState((current) => ({
        intakeId: response.intake_id,
        mode: response.mode,
        requirement: response.requirement,
        extractedSignals: response.extracted_signals,
        selectedReference: response.selected_reference,
        modules: response.modules,
        assistantCards: response.assistant_cards,
        chatMessages: [],
        validation: response.validation,
        loading: false,
        started: true,
        phase: "draft",
        candidates: current.candidates,
        toast: `${response.mode === "CREATE_NEW" ? "Create New" : "Edit Reference"} scenario loaded`
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        loading: false,
        error: error instanceof Error ? error.message : "Unable to build draft"
      }));
    }
  }, []);

  const analyzeRequirement = useCallback(async (requirement: string) => {
    const intakeId = `INTAKE-${Date.now().toString().slice(-6)}`;
    setState((current) => ({ ...current, intakeId, requirement, loading: true, error: undefined, toast: undefined }));
    try {
      const response = await apiClient.analyzeRequirement(intakeId, requirement);
      setState((current) => ({
        ...current,
        intakeId: response.intake_id,
        requirement: response.requirement,
        extractedSignals: response.extracted_signals,
        candidates: response.candidates,
        assistantCards: response.assistant_cards,
        loading: false,
        started: true,
        phase: "analyzed",
        toast: "Requirement analyzed"
      }));
    } catch (error) {
      setState((current) => ({
        ...current,
        loading: false,
        error: error instanceof Error ? error.message : "Unable to analyze requirement"
      }));
    }
  }, []);

  const buildFromChoice = useCallback(
    async (mode: IntakeMode, selectedReferenceId?: string) => {
      const nextScenario = mode === "CREATE_NEW" ? "create" : "edit";
      setScenario(nextScenario);
      const request: BuildDraftRequest & { intakeId: string } = {
        intakeId: state.intakeId,
        mode,
        requirement: state.requirement,
        selected_reference_use_case_id: selectedReferenceId
      };
      await buildDraft(request, nextScenario);
      setState((current) => ({ ...current, phase: "draft" }));
    },
    [buildDraft, state.intakeId, state.requirement]
  );

  const selectScenario = useCallback((nextScenario: "edit" | "create") => {
    setScenario(nextScenario);
    void buildDraft(scenarios[nextScenario], nextScenario);
  }, [buildDraft]);

  const resetIntake = useCallback(() => {
    setState({
      intakeId: "INTAKE-NEW",
      mode: "EDIT_REFERENCE",
      requirement: "",
      extractedSignals: {},
      modules: {},
      assistantCards: [],
      chatMessages: [],
      loading: false,
      started: false,
      phase: "idle",
      candidates: []
    });
  }, []);

  const answerQuestion = useCallback(
    async (questionId: string, answer: string) => {
      setState((current) => ({
        ...current,
        loading: true,
        chatMessages: [
          ...current.chatMessages,
          { id: `${Date.now()}-user`, role: "user", text: answer }
        ]
      }));

      try {
        const response = await apiClient.parseAnswer(state.intakeId, questionId, answer);
        const preview = response.assistant_cards.find((card) => card.type === "action_preview")?.action_preview;
        setState((current) => ({
          ...current,
          loading: false,
          assistantCards: response.assistant_cards,
          currentActionPreview: preview,
          toast: preview ? "Action preview ready" : "Answer captured"
        }));
      } catch (error) {
        setState((current) => ({
          ...current,
          loading: false,
          error: error instanceof Error ? error.message : "Unable to parse answer"
        }));
      }
    },
    [state.intakeId]
  );

  const applyPreview = useCallback(
    async (previewId: string) => {
      setState((current) => ({ ...current, loading: true }));
      try {
        const response = await apiClient.applyPreview(state.intakeId, previewId);
        setState((current) => ({
          ...current,
          modules: response.modules,
          assistantCards: response.assistant_cards,
          validation: response.validation,
          currentActionPreview: undefined,
          loading: false,
          toast: "Preview applied"
        }));
      } catch (error) {
        setState((current) => ({
          ...current,
          loading: false,
          error: error instanceof Error ? error.message : "Unable to apply preview"
        }));
      }
    },
    [state.intakeId]
  );

  const updateField = useCallback(
    async (fieldName: string, value: string) => {
      setState((current) => ({ ...current, loading: true }));
      try {
        const response = await apiClient.updateField(state.intakeId, fieldName, value);
        setState((current) => ({
          ...current,
          modules: response.modules,
          assistantCards: response.assistant_cards.length ? response.assistant_cards : current.assistantCards,
          validation: response.validation,
          loading: false,
          toast: "Field updated"
        }));
      } catch (error) {
        setState((current) => ({
          ...current,
          loading: false,
          error: error instanceof Error ? error.message : "Unable to update field"
        }));
      }
    },
    [state.intakeId]
  );

  const validate = useCallback(async () => {
    setState((current) => ({ ...current, loading: true }));
    const validation = await apiClient.validate(state.intakeId);
    setState((current) => ({
      ...current,
      validation,
      loading: false,
      toast: validation.ready_for_ac ? "Ready for AC" : "Validation found blocking issues"
    }));
  }, [state.intakeId]);

  const exportForAc = useCallback(async () => {
    setState((current) => ({ ...current, loading: true }));
    const exportResult = await apiClient.exportForAc(state.intakeId);
    setState((current) => ({
      ...current,
      exportResult,
      loading: false,
      toast: exportResult.ready_for_ac ? "Export package generated" : "Resolve blocking issues before export"
    }));
  }, [state.intakeId]);

  return useMemo(
    () => ({
      scenario,
      state,
      analyzeRequirement,
      buildFromChoice,
      selectScenario,
      resetIntake,
      answerQuestion,
      applyPreview,
      updateField,
      validate,
      exportForAc
    }),
    [scenario, state, analyzeRequirement, buildFromChoice, selectScenario, resetIntake, answerQuestion, applyPreview, updateField, validate, exportForAc]
  );
}
