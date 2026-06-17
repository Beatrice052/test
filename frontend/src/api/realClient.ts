import type {
  BuildDraftRequest,
  IntakeApiClient
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init.headers
    }
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

export const realClient: IntakeApiClient = {
  analyzeRequirement(intakeId: string, requirement: string) {
    return request(`/api/intake/${intakeId}/requirement/analyze`, {
      method: "POST",
      body: JSON.stringify({ requirement })
    });
  },
  buildDraft(intakeId: string, body: BuildDraftRequest) {
    return request(`/api/intake/${intakeId}/draft/build`, {
      method: "POST",
      body: JSON.stringify(body)
    });
  },
  parseAnswer(intakeId: string, questionId: string, answer: string) {
    return request(`/api/intake/${intakeId}/assistant/parse-answer`, {
      method: "POST",
      body: JSON.stringify({ question_id: questionId, answer })
    });
  },
  applyPreview(intakeId: string, previewId: string) {
    return request(`/api/intake/${intakeId}/assistant/apply-preview`, {
      method: "POST",
      body: JSON.stringify({ preview_id: previewId })
    });
  },
  updateField(intakeId: string, fieldName: string, value: string) {
    return request(`/api/intake/${intakeId}/fields/${fieldName}`, {
      method: "PATCH",
      body: JSON.stringify({ value, updated_by: "USER" })
    });
  },
  validate(intakeId: string) {
    return request(`/api/intake/${intakeId}/validate`, {
      method: "POST"
    });
  },
  exportForAc(intakeId: string) {
    return request(`/api/intake/${intakeId}/export-for-ac`, {
      method: "POST"
    });
  }
};
