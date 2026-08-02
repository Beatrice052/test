import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../src/App";

const session = {
  schema_version: "1.0",
  object_id: "ses_demo",
  created_at: "2026-08-01T01:00:00Z",
  content_hash: "hash",
  provenance: { producer: "test", source_ids: [] },
  subject_id: "mock-user",
  title: "消息健康度分析",
  version: 1,
  archived: false,
  latest_answer_id: null,
  updated_at: "2026-08-01T01:00:00Z",
};

function renderWorkspace() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><App /></QueryClientProvider>);
}

describe("Session Workspace", () => {
  afterEach(() => vi.restoreAllMocks());

  it("restores the selected session and exposes the analysis composer", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      if (url.endsWith("/api/v1/health/ready")) {
        return Promise.resolve(new Response(JSON.stringify({
          status: "ready",
          profile: "mock",
          llm_mode: "rule_based",
          gateway_mode: "mock",
        }), { status: 200 }));
      }
      if (url.endsWith("/api/v1/sessions")) {
        return Promise.resolve(new Response(JSON.stringify([session]), { status: 200 }));
      }
      if (url.endsWith("/api/v1/sessions/ses_demo")) {
        return Promise.resolve(new Response(JSON.stringify({ session, answers: [] }), { status: 200 }));
      }
      return Promise.resolve(new Response("not found", { status: 404 }));
    });

    renderWorkspace();

    expect(await screen.findByRole("heading", { name: "消息健康度分析" })).toBeVisible();
    expect(screen.getByText("这是一张干净的分析画布")).toBeVisible();
    expect(screen.getByRole("textbox", { name: "分析问题" })).toBeEnabled();
    expect(await screen.findByText("rule_based · mock")).toBeVisible();
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledTimes(3));
  });

  it("shows a credential-free welcome state when no sessions exist", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), { status: 200 }),
    );

    renderWorkspace();

    expect(await screen.findByRole("heading", { name: "从一个可验证的问题开始" })).toBeVisible();
    expect(screen.getByText(/Mock 模式无需真实凭证/)).toBeVisible();
  });
});
