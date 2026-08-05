import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
    expect(document.querySelector(".loading-panel")).not.toBeInTheDocument();
  });

  it("opens business evidence first and keeps raw DSL behind the advanced tab", async () => {
    const answeredSession = { ...session, latest_answer_id: "ans_demo" };
    const answer = {
      schema_version: "1.0",
      object_id: "ans_demo",
      created_at: "2026-08-01T01:01:00Z",
      content_hash: "answer-hash",
      provenance: { producer: "test", source_ids: [] },
      session_id: "ses_demo",
      turn_kind: "NEW_ANALYSIS",
      status: "ANSWERED",
      semantic_package_version: "sp_test",
      metric_versions: [],
      analysis_plan: { analysis_goal: "按渠道分析消息量" },
      dashboard_spec: {
        title: "按渠道分析消息量",
        blocks: [
          {
            block_id: "summary",
            type: "answer_summary",
            title: "总分析",
            content: { text: "SMS 消息量最高。" },
          },
        ],
      },
      evidence_package: { object_id: "ev_demo" },
      visualization_previews: [],
      claims: [],
      limitations: [],
      warnings: [],
    };
    const evidence = {
      evidence_id: "ev_demo",
      business: {
        scope: {
          analysis_goal: "按渠道分析消息量",
          semantic_package_version: "sp_test",
          time_range: {
            from_inclusive: "2026-05-01T00:00:00+08:00",
            to_exclusive: "2026-08-01T00:00:00+08:00",
            timezone: "Asia/Hong_Kong",
          },
        },
        metric_definitions: [],
        data_tables: [],
        reconciliations: [],
        quality: [{ rule_id: "qa_should_stay_internal", passed: true, message: "DO_NOT_RENDER_QA_PASS" }],
        quality_summary: { status: "VALID", material_warnings: [], blocked_reasons: [], completeness: [], reconciliation_summary: [] },
        downloads: [],
      },
      advanced: {
        query_plan: { steps: [], reuse_strategy: "dataset_fingerprint" },
        compiled_queries: [],
        execution_summaries: [],
        result_contracts: [],
      },
      redaction: { removed_fields: [], masked_fields: [], policy_id: "evidence.v1" },
    };
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
        return Promise.resolve(new Response(JSON.stringify([answeredSession]), { status: 200 }));
      }
      if (url.endsWith("/api/v1/sessions/ses_demo")) {
        return Promise.resolve(new Response(JSON.stringify({
          session: answeredSession,
          answers: [answer],
        }), { status: 200 }));
      }
      if (url.endsWith("/api/v1/answers/ans_demo/evidence")) {
        return Promise.resolve(new Response(JSON.stringify(evidence), { status: 200 }));
      }
      return Promise.resolve(new Response("not found", { status: 404 }));
    });

    renderWorkspace();
    fireEvent.click(await screen.findByRole("button", { name: "查看证据" }));

    expect(await screen.findByRole("dialog", { name: "证据与口径" })).toBeVisible();
    const businessTab = await screen.findByRole("tab", { name: "业务证据" });
    expect(businessTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("指标是怎么得到的")).toBeVisible();
    expect(screen.getByText("Important Limitations")).toBeVisible();
    expect(screen.queryByText("DO_NOT_RENDER_QA_PASS")).not.toBeInTheDocument();
    expect(screen.queryByText("实际检索 DSL")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "高级证据 · DSL" }));
    expect(screen.getByText("实际检索 DSL")).toBeVisible();
  });
});
