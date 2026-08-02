import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { AnswerSnapshot } from "../src/api/generated";
import { Dashboard } from "../src/components/Dashboard";

const answer = {
  dashboard_spec: {
    title: "最近三个月消息发送情况",
    blocks: [
      {
        block_id: "summary",
        type: "answer_summary",
        title: "直接回答",
        content: { text: "三个月共 269 条消息, 整体失败率为 18.15%。" },
      },
      {
        block_id: "kpis",
        type: "kpi_group",
        title: "核心指标总览",
        description: "规模与质量指标由本次问题动态选择。",
        kpis: [
          {
            kpi_id: "count",
            label: "消息记录数",
            value: 269,
            formatted_value: "269",
            unit: "条",
            semantic_level: "governed",
            quality: "valid",
            definition: "过滤范围内的记录数。",
          },
          {
            kpi_id: "failure",
            label: "失败率",
            value: 0.1815,
            formatted_value: "18.15%",
            unit: "%",
            semantic_level: "certified",
            quality: "valid",
            definition: "失败记录除以正式分母。",
          },
        ],
      },
      {
        block_id: "insights",
        type: "insight_list",
        title: "关键发现",
        insights: ["SMS 消息量最高。", "PUSH 失败率最高。"],
      },
      {
        block_id: "followups",
        type: "follow_up_suggestions",
        title: "推荐追问",
        suggestions: ["下钻失败原因"],
      },
    ],
  },
} as unknown as AnswerSnapshot;

describe("dynamic dashboard", () => {
  it("renders answer-first KPI, insight, and follow-up sections", () => {
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <Dashboard answer={answer} />
      </QueryClientProvider>,
    );

    expect(screen.getByRole("heading", { name: "最近三个月消息发送情况" })).toBeVisible();
    expect(screen.getByText("消息记录数")).toBeVisible();
    expect(screen.getByText("18.15%")).toBeVisible();
    expect(screen.getByText("SMS 消息量最高。")).toBeVisible();
    expect(screen.getByText("下钻失败原因")).toBeVisible();
    expect(screen.getByText("补充发现")).toBeVisible();
    expect(screen.queryByRole("heading", { name: "关键发现" })).not.toBeInTheDocument();
  });

  it("keeps legacy technical detail and QA blocks out of the business dashboard", () => {
    const legacyAnswer = {
      dashboard_spec: {
        title: "历史分析",
        blocks: [
          {
            block_id: "summary",
            type: "answer_summary",
            title: "总分析",
            content: { text: "已完成分析。" },
          },
          {
            block_id: "block_data_quality",
            type: "warning",
            title: "数据质量提示",
            content: { text: "部分分组样本不足。" },
          },
          {
            block_id: "block_table_old_dataset",
            type: "data_table",
            title: "聚合明细与指标口径",
            dataset_id: "ds_old_dataset",
            chart_type: "table",
          },
        ],
      },
    } as unknown as AnswerSnapshot;
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <Dashboard answer={legacyAnswer} />
      </QueryClientProvider>,
    );

    expect(screen.getByText("已完成分析。")).toBeVisible();
    expect(screen.queryByText("数据质量提示")).not.toBeInTheDocument();
    expect(screen.queryByText("聚合明细与指标口径")).not.toBeInTheDocument();
    expect(screen.queryByText("验证明细")).not.toBeInTheDocument();
  });
});
