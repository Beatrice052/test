import type {
  ChatApiResponse,
  ChatRequest,
  DatasetRowsResponse,
  EvidenceView,
  SessionContext,
  SessionCreateRequest,
  SessionDetailResponse,
} from "./generated";

const API_ROOT = "/api/v1";

export type RuntimeHealth = {
  status: string;
  profile?: string;
  llm_mode?: string;
  gateway_mode?: string;
};

export type AnalysisProgressStage =
  | "request"
  | "guardrails"
  | "context"
  | "intent"
  | "query_plan"
  | "dsl"
  | "search"
  | "analytics"
  | "dashboard"
  | "complete";

export type AnalysisProgressEvent = {
  sequence: number;
  stage: AnalysisProgressStage;
  status: "running" | "completed";
  title: string;
  detail: string;
  safe_summary: Record<string, unknown>;
  occurred_at: string;
};

type ChatStreamEnvelope =
  | { event: "progress"; progress: AnalysisProgressEvent }
  | { event: "result"; result: ChatApiResponse }
  | { event: "error"; code: string; message: string };

function withSignal(signal: AbortSignal | undefined): Pick<RequestInit, "signal"> {
  return signal === undefined ? {} : { signal };
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body === undefined ? {} : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    let message = `Request failed (${String(response.status)})`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") message = body.detail;
    } catch {
      // Keep the safe status-only message for non-JSON failures.
    }
    throw new ApiError(response.status, message);
  }
  return (await response.json()) as T;
}

function parseEventBlock(block: string): ChatStreamEnvelope | null {
  const data = block
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (data.length === 0) return null;
  return JSON.parse(data) as ChatStreamEnvelope;
}

async function chatStream(
  body: ChatRequest,
  onProgress: (event: AnalysisProgressEvent) => void,
  signal?: AbortSignal,
): Promise<ChatApiResponse> {
  const response = await fetch(`${API_ROOT}/chat/stream`, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    ...withSignal(signal),
  });
  if (!response.ok) {
    throw new ApiError(response.status, `Request failed (${String(response.status)})`);
  }
  if (response.body === null) {
    throw new ApiError(response.status, "分析服务未返回流式响应");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: ChatApiResponse | null = null;

  function consume(block: string) {
    const envelope = parseEventBlock(block);
    if (envelope === null) return;
    if (envelope.event === "progress") {
      onProgress(envelope.progress);
      return;
    }
    if (envelope.event === "error") {
      throw new ApiError(response.status, envelope.message);
    }
    result = envelope.result;
  }

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    buffer = buffer.replaceAll("\r\n", "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      consume(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");
    }
    if (done) break;
  }
  if (buffer.trim().length > 0) consume(buffer);
  if (result === null) {
    throw new ApiError(response.status, "分析流已结束，但未返回最终结果");
  }
  return result;
}

export const workspaceApi = {
  getRuntimeHealth: (signal?: AbortSignal) =>
    request<RuntimeHealth>("/health/ready", withSignal(signal)),
  listSessions: (signal?: AbortSignal) =>
    request<Array<SessionContext>>("/sessions", withSignal(signal)),
  createSession: (body: SessionCreateRequest, signal?: AbortSignal) =>
    request<SessionContext>("/sessions", {
      method: "POST",
      body: JSON.stringify(body),
      ...withSignal(signal),
    }),
  getSession: (sessionId: string, signal?: AbortSignal) =>
    request<SessionDetailResponse>(
      `/sessions/${encodeURIComponent(sessionId)}`,
      withSignal(signal),
    ),
  archiveSession: (sessionId: string, signal?: AbortSignal) =>
    request<SessionContext>(`/sessions/${encodeURIComponent(sessionId)}/archive`, {
      method: "POST",
      ...withSignal(signal),
    }),
  chat: (body: ChatRequest, signal?: AbortSignal) =>
    request<ChatApiResponse>("/chat", {
      method: "POST",
      body: JSON.stringify(body),
      ...withSignal(signal),
    }),
  chatStream,
  getEvidence: (answerId: string, signal?: AbortSignal) =>
    request<EvidenceView>(
      `/answers/${encodeURIComponent(answerId)}/evidence`,
      withSignal(signal),
    ),
  getDatasetRows: (datasetId: string, signal?: AbortSignal) =>
    request<DatasetRowsResponse>(
      `/datasets/${encodeURIComponent(datasetId)}/rows?offset=0&limit=200`,
      withSignal(signal),
    ),
  datasetCsvUrl: (datasetId: string) =>
    `${API_ROOT}/datasets/${encodeURIComponent(datasetId)}/csv`,
};
