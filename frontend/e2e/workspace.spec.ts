import { expect, test, type Page } from "@playwright/test";
import type { SessionContext } from "../src/api/generated";

const baseSession: SessionContext = {
  object_id: "ses_restored",
  created_at: "2026-08-01T01:00:00Z",
  content_hash: "session-hash",
  provenance: { producer: "e2e", source_ids: [] },
  subject_id: "mock-user",
  title: "消息健康度分析",
  version: 1,
  archived: false,
  latest_answer_id: "ans_restored",
  updated_at: "2026-08-01T01:05:00Z",
};

const answer = {
  object_id: "ans_restored",
  created_at: "2026-08-01T01:05:00Z",
  content_hash: "answer-hash",
  provenance: { producer: "e2e", source_ids: [] },
  session_id: "ses_restored",
  turn_kind: "NEW_ANALYSIS",
  status: "ANSWERED",
  semantic_package_version: "sp_mock",
  metric_versions: ["failure_rate@1"],
  analysis_plan: { analysis_goal: "按服务查看消息量和失败率" },
  evidence_package: { object_id: "ev_restored" },
  dashboard_spec: {
    title: "消息健康度",
    blocks: [
      { block_id: "summary", type: "answer_summary", title: "结论", content: { text: "checkout 消息量最高，证据已校验。" } },
      { block_id: "chart", type: "chart", title: "各服务失败率", dataset_id: "message_health", chart_type: "bar", encoding: { x: "service", y: "failure_rate" } },
      { block_id: "table", type: "data_table", title: "验证数据", dataset_id: "message_health", chart_type: "table" },
    ],
  },
};

const dataset = {
  object_id: "ds_restored",
  dataset_id: "message_health",
  kind: "derived",
  grain: ["service"],
  columns: [
    { name: "service", data_type: "string", semantic_role: "dimension" },
    { name: "failure_rate", data_type: "metric", semantic_role: "metric", unit: "ratio" },
    { name: "metric_metadata", data_type: "metric", semantic_role: "metadata" },
  ],
  rows: [{
    row_id: "row_checkout",
    values: {
      service: "checkout",
      failure_rate: 0.025,
      metric_metadata: {
        failure_rate: {
          metric_id: "failure_rate",
          value: 0.025,
          unit: "ratio",
          numerator: 25,
          denominator: 1000,
          excluded: { unknown: 3 },
          quality: "VALID",
        },
      },
    },
  }],
  offset: 0,
  limit: 200,
  total: 1,
  complete: true,
  warnings: [],
};

async function installApi(page: Page) {
  let sessions: Array<SessionContext> = [baseSession];
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const json = async (body: unknown, status = 200) => route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
    if (url.pathname === "/api/v1/sessions" && request.method() === "GET") return json(sessions);
    if (url.pathname === "/api/v1/sessions" && request.method() === "POST") {
      const created = { ...baseSession, object_id: "ses_new", title: "New analysis", latest_answer_id: null };
      sessions = [created, ...sessions];
      return json(created, 201);
    }
    if (url.pathname === "/api/v1/sessions/ses_restored") return json({ session: baseSession, answers: [answer] });
    if (url.pathname === "/api/v1/sessions/ses_new") return json({ session: sessions[0], answers: [] });
    if (url.pathname.includes("/datasets/message_health/rows")) return json(dataset);
    if (url.pathname === "/api/v1/answers/ans_restored/evidence") return json({
      evidence_id: "ev_restored",
      business: {
        scope: {
          analysis_goal: "按服务查看消息量和失败率",
          time_range: {
            from_inclusive: "2026-07-01T00:00:00Z",
            to_exclusive: "2026-08-01T00:00:00Z",
            timezone: "Asia/Hong_Kong",
          },
          semantic_package_version: "sp_mock",
        },
        metric_definitions: [{ metric_id: "failure_rate", display_name: "失败率", business_definition: "失败消息占比" }],
        data_tables: ["message_health"],
        quality: [{ rule_id: "non_negative", passed: true, message: "所有指标均为非负数" }],
        quality_summary: { status: "VALID", material_warnings: [], blocked_reasons: [], completeness: ["message_health: COMPLETE"], reconciliation_summary: [] },
        downloads: ["/api/v1/datasets/ds_restored/csv"],
      },
      advanced: {
        query_plan: { plan_id: "qp_1", steps: [{ step_id: "query_health" }], reuse_strategy: "dataset_fingerprint" },
        compiled_queries: [{
          object_id: "cq_1",
          step_id: "query_health",
          indices: ["message-index"],
          semantics: { grain: ["service"] },
          query_dsl: { size: 0, aggs: { by_service: { terms: { field: "service.keyword" } } } },
        }],
        execution_summaries: [{ query_id: "cq_1", status: "SUCCEEDED", shard_failures: 0 }],
      },
      redaction: { removed_fields: ["credentials"], policy_id: "evidence.v1" },
    });
    return json({ detail: "not found" }, 404);
  });
}

test("G02/G15/G25 restores isolated sessions and renders safe evidence-backed results", async ({ page }) => {
  await installApi(page);
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "消息健康度分析" })).toBeVisible();
  await expect(page.getByText("checkout 消息量最高，证据已校验。")).toBeVisible();
  await expect(page.getByRole("img", { name: "各服务失败率" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "checkout" })).toBeVisible();

  await page.reload();
  await expect(page.getByText("checkout 消息量最高，证据已校验。")).toBeVisible();

  await page.getByRole("button", { name: /查看证据/ }).click();
  await expect(page.getByRole("heading", { name: "证据与口径" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "OpenSearch 返回了什么" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "指标是怎么得到的" })).toBeVisible();
  await expect(page.getByText("25 ÷ 1,000 = 2.5%")).toBeVisible();
  await expect(page.getByText("所有指标均为非负数")).toHaveCount(0);
  await page.getByRole("tab", { name: /高级证据/ }).click();
  await expect(page.getByRole("heading", { name: "实际检索 DSL" })).toBeVisible();
  await expect(page.getByRole("dialog").locator("pre").filter({ hasText: '"size": 0' })).toBeVisible();
  await page.getByRole("button", { name: "关闭证据抽屉" }).click();

  await page.getByRole("button", { name: /新建分析/ }).click();
  await expect(page.getByRole("heading", { name: "New analysis" })).toBeVisible();
  await expect(page.getByText("这是一张干净的分析画布")).toBeVisible();
  await expect(page.getByText("checkout 消息量最高，证据已校验。")).toHaveCount(0);
});
