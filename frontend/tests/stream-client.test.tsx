import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { workspaceApi } from "../src/api/client";
import type { AnalysisProgressEvent } from "../src/api/client";
import { AnalysisProgress } from "../src/components/AnalysisProgress";

function progress(sequence: number, stage: AnalysisProgressEvent["stage"]): AnalysisProgressEvent {
  return {
    sequence,
    stage,
    status: stage === "query_plan" ? "running" : "completed",
    title: stage === "intent" ? "Agent A 已完成意图识别" : "正在规划查询步骤",
    detail: stage === "intent" ? "识别到用户需要：按渠道分析消息量" : "Agent B 正在生成 QueryPlan。",
    safe_summary: {},
    occurred_at: "2026-08-02T03:00:00Z",
  };
}

describe("chat streaming", () => {
  afterEach(() => vi.restoreAllMocks());

  it("parses split SSE chunks and returns the final immutable result", async () => {
    const first = JSON.stringify({ event: "progress", progress: progress(1, "intent") });
    const second = JSON.stringify({ event: "progress", progress: progress(2, "query_plan") });
    const result = JSON.stringify({
      event: "result",
      result: { status: "COMPLETED", session_id: "ses_demo", turn_id: "trn_demo", answer: null },
    });
    const payload = `event: progress\ndata: ${first}\n\nevent: progress\ndata: ${second}\n\nevent: result\ndata: ${result}\n\n`;
    const midpoint = Math.floor(payload.length / 2) + 3;
    const encoder = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(payload.slice(0, midpoint)));
        controller.enqueue(encoder.encode(payload.slice(midpoint)));
        controller.close();
      },
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } }),
    );
    const received: AnalysisProgressEvent[] = [];

    const response = await workspaceApi.chatStream(
      {
        session_id: "ses_demo",
        message: "按渠道分析消息量",
        client_turn_id: "client_stream_demo",
        mode: "standard",
      },
      (event) => received.push(event),
    );

    expect(received.map((event) => event.stage)).toEqual(["intent", "query_plan"]);
    expect(response).toMatchObject({ status: "COMPLETED", session_id: "ses_demo" });
  });

  it("shows confirmed stages and explains that private reasoning is not exposed", () => {
    render(
      <AnalysisProgress
        question="按渠道分析消息量"
        events={[progress(1, "intent"), progress(2, "query_plan")]}
      />,
    );

    expect(screen.getByRole("region", { name: "分析进度" })).toBeVisible();
    expect(screen.getByText("Agent A 已完成意图识别")).toBeVisible();
    expect(screen.getAllByText("正在规划查询步骤").length).toBeGreaterThan(0);
    expect(screen.getByText(/不展示模型私有推理/)).toBeVisible();
  });
});
