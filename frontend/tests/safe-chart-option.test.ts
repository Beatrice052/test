import { describe, expect, it } from "vitest";

import type { DashboardBlock, DatasetRowsResponse } from "../src/api/generated";
import { buildSafeOption, validateChartDataset } from "../src/lib/safeChartOption";

const dataset: DatasetRowsResponse = {
  object_id: "ds_obj",
  dataset_id: "message_health",
  kind: "derived",
  grain: ["service"],
  columns: [
    { name: "service", data_type: "string", semantic_role: "dimension" },
    { name: "failure_rate", data_type: "metric", semantic_role: "metric", unit: "%" },
  ],
  rows: [
    { row_id: "row_a", values: { service: "checkout", failure_rate: 2.5 } },
    { row_id: "row_b", values: { service: "search", failure_rate: 1.25 } },
  ],
  offset: 0,
  limit: 200,
  total: 2,
  complete: true,
  warnings: [],
};

describe("safe chart adapter", () => {
  it("builds a known chart shape only from closed encoding fields", () => {
    const block: DashboardBlock = {
      block_id: "chart_1",
      type: "chart",
      chart_type: "bar",
      encoding: { x: "service", y: "failure_rate" },
    };

    const option = buildSafeOption(block, dataset);

    expect(option.xAxis).toMatchObject({ type: "category", data: ["checkout", "search"] });
    expect(option.series).toEqual([
      expect.objectContaining({ type: "bar", data: [2.5, 1.25] }),
    ]);
    expect(JSON.stringify(option)).not.toContain("raw_option");
  });

  it("renders a validated one-value scope as a governed scalar chart", () => {
    const overall: DatasetRowsResponse = {
      ...dataset,
      dataset_id: "overall_scope",
      grain: [],
      columns: [
        { name: "record_count", data_type: "integer", semantic_role: "measure", unit: "count" },
      ],
      rows: [{ row_id: "row_overall", values: { record_count: 269 } }],
      total: 1,
    };
    const block: DashboardBlock = {
      block_id: "overall_chart",
      type: "chart",
      title: "当前范围消息量",
      chart_type: "bar",
      visualization_intent: "single_value",
      encoding: { value: "record_count" },
    };

    expect(validateChartDataset(block, overall)).toBeNull();
    const option = buildSafeOption(block, overall);
    expect(option.xAxis).toMatchObject({ data: ["当前范围消息量"] });
    expect(option.series).toEqual([
      expect.objectContaining({ type: "bar", data: [269] }),
    ]);
  });

  it("pivots a validated series field into a stacked multi-series chart", () => {
    const composition: DatasetRowsResponse = {
      ...dataset,
      grain: ["channel", "status"],
      columns: [
        { name: "channel", data_type: "string", semantic_role: "dimension" },
        { name: "status", data_type: "string", semantic_role: "dimension" },
        { name: "record_count", data_type: "integer", semantic_role: "measure", unit: "count" },
      ],
      rows: [
        { row_id: "row_1", values: { channel: "SMS", status: "成功", record_count: 70 } },
        { row_id: "row_2", values: { channel: "SMS", status: "失败", record_count: 20 } },
        { row_id: "row_3", values: { channel: "EMAIL", status: "成功", record_count: 30 } },
        { row_id: "row_4", values: { channel: "EMAIL", status: "失败", record_count: 10 } },
      ],
      total: 4,
    };
    const block: DashboardBlock = {
      block_id: "chart_composition",
      type: "chart",
      chart_type: "stacked_bar",
      stack: true,
      legend: true,
      encoding: { x: "channel", y: "record_count", series: "status" },
    };

    const option = buildSafeOption(block, composition);

    expect(option.xAxis).toMatchObject({ type: "category", data: ["SMS", "EMAIL"] });
    expect(option.series).toEqual([
      expect.objectContaining({ name: "成功", type: "bar", stack: "total", data: [70, 30] }),
      expect.objectContaining({ name: "失败", type: "bar", stack: "total", data: [20, 10] }),
    ]);
  });

  it("rejects a chart when its encoding hides part of the Dataset grain", () => {
    const tooDetailed: DatasetRowsResponse = {
      ...dataset,
      grain: ["month", "service"],
      columns: [
        { name: "month", data_type: "datetime", semantic_role: "dimension" },
        { name: "service", data_type: "string", semantic_role: "dimension" },
        { name: "record_count", data_type: "integer", semantic_role: "measure", unit: "count" },
      ],
      rows: [
        { row_id: "row_1", values: { month: "2026-05-01", service: "SMS", record_count: 45 } },
        { row_id: "row_2", values: { month: "2026-06-01", service: "SMS", record_count: 55 } },
      ],
      total: 2,
    };
    const rankBlock: DashboardBlock = {
      block_id: "rank_invalid",
      type: "chart",
      chart_type: "bar",
      visualization_intent: "ranked_comparison",
      encoding: { category: "service", value: "record_count" },
    };

    expect(validateChartDataset(rankBlock, tooDetailed)).toContain("数据粒度不一致");
    expect(() => buildSafeOption(rankBlock, tooDetailed)).toThrow("数据粒度不一致");
  });

  it("rejects duplicate rows at an otherwise matching chart grain", () => {
    const duplicated: DatasetRowsResponse = {
      ...dataset,
      rows: [
        dataset.rows[0]!,
        { row_id: "row_duplicate", values: { service: "checkout", failure_rate: 3.1 } },
      ],
      total: 2,
    };
    const block: DashboardBlock = {
      block_id: "duplicate",
      type: "chart",
      chart_type: "bar",
      encoding: { x: "service", y: "failure_rate" },
    };

    expect(validateChartDataset(block, duplicated)).toContain("存在重复行");
  });

  it("renders a two-dimensional validated grain as a heatmap", () => {
    const matrix: DatasetRowsResponse = {
      ...dataset,
      grain: ["region", "state"],
      columns: [
        { name: "region", data_type: "string", semantic_role: "dimension" },
        { name: "state", data_type: "string", semantic_role: "dimension" },
        { name: "record_count", data_type: "integer", semantic_role: "measure", unit: "count" },
      ],
      rows: [
        { row_id: "row_1", values: { region: "north", state: "ok", record_count: 10 } },
        { row_id: "row_2", values: { region: "north", state: "failed", record_count: 2 } },
        { row_id: "row_3", values: { region: "south", state: "ok", record_count: 7 } },
      ],
      total: 3,
    };
    const block: DashboardBlock = {
      block_id: "matrix",
      type: "chart",
      chart_type: "heatmap",
      encoding: { x: "region", y: "record_count", series: "state", value: "record_count" },
    };

    const option = buildSafeOption(block, matrix);

    expect(option.xAxis).toMatchObject({ type: "category", data: ["north", "south"] });
    expect(option.yAxis).toMatchObject({ type: "category", data: ["ok", "failed"] });
    expect(option.series).toEqual([
      expect.objectContaining({ type: "heatmap", data: [[0, 0, 10], [0, 1, 2], [1, 0, 7]] }),
    ]);
  });

  it("renders a governed Pareto view with cumulative contribution", () => {
    const reasons: DatasetRowsResponse = {
      ...dataset,
      grain: ["reason"],
      columns: [
        { name: "reason", data_type: "string", semantic_role: "dimension" },
        { name: "record_count", data_type: "integer", semantic_role: "measure", unit: "count" },
      ],
      rows: [
        { row_id: "row_1", values: { reason: "timeout", record_count: 50 } },
        { row_id: "row_2", values: { reason: "rejected", record_count: 30 } },
        { row_id: "row_3", values: { reason: "unknown", record_count: 20 } },
      ],
      total: 3,
    };
    const block: DashboardBlock = {
      block_id: "pareto",
      type: "chart",
      chart_type: "pareto",
      encoding: { category: "reason", value: "record_count" },
      content: {
        pareto_points: [
          { row_id: "row_1", category: "timeout", value: 50, cumulative_percent: 50 },
          { row_id: "row_2", category: "rejected", value: 30, cumulative_percent: 80 },
          { row_id: "row_3", category: "unknown", value: 20, cumulative_percent: 100 },
        ],
      },
    };

    const option = buildSafeOption(block, reasons);

    expect(option.xAxis).toMatchObject({ data: ["timeout", "rejected", "unknown"] });
    expect(option.series).toEqual([
      expect.objectContaining({ type: "bar", data: [50, 30, 20] }),
      expect.objectContaining({ type: "line", yAxisIndex: 1, data: [50, 80, 100] }),
    ]);
  });

  it("does not recalculate governed Pareto values in the browser", () => {
    const block: DashboardBlock = {
      block_id: "pareto_governed",
      type: "chart",
      chart_type: "pareto",
      encoding: { category: "service", value: "failure_rate" },
      content: {
        pareto_points: [
          { row_id: "row_b", category: "search", value: 1.25, cumulative_percent: 33.3 },
          { row_id: "row_a", category: "checkout", value: 2.5, cumulative_percent: 99.9 },
        ],
      },
    };

    const option = buildSafeOption(block, dataset);

    expect(option.xAxis).toMatchObject({ data: ["search", "checkout"] });
    expect(option.series).toEqual([
      expect.objectContaining({ type: "bar", data: [1.25, 2.5] }),
      expect.objectContaining({ type: "line", data: [33.3, 99.9] }),
    ]);
  });

  it("omits null values from donut and heatmap instead of converting them to zero", () => {
    const nullDataset: DatasetRowsResponse = {
      ...dataset,
      grain: ["service"],
      rows: [
        dataset.rows[0]!,
        { row_id: "row_null", values: { service: "unknown", failure_rate: null } },
      ],
      total: 2,
    };
    const donut = buildSafeOption(
      {
        block_id: "donut_null",
        type: "chart",
        chart_type: "donut",
        encoding: { category: "service", value: "failure_rate" },
      },
      nullDataset,
    );

    expect(donut.series).toEqual([
      expect.objectContaining({ data: [{ name: "checkout", value: 2.5 }] }),
    ]);
  });
});
