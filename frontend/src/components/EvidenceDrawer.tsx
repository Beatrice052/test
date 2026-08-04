import { useQueries, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { workspaceApi } from "../api/client";
import type {
  AdvancedEvidence,
  BusinessEvidence,
  DatasetRowsResponse,
  JsonValue,
} from "../api/generated";
import {
  asRecord,
  asNumber,
  asString,
  asStringArray,
  datasetTitle,
  extractMetricCalculations,
  timeRangeSummary,
} from "../lib/evidenceModel";
import { DataTable } from "./DataTable";

type EvidenceDrawerProps = {
  answerId: string | null;
  onClose: () => void;
};

function readableQuality(message: string): string {
  const translations: Record<string, string> = {
    "unknown or null statuses were excluded": "未知或空状态已按指标口径排除",
    "one or more metric samples are below minimum size": "部分分组样本量低于指标阈值",
    "additive Dashboard rollup reconciles to its source Dataset": "派生聚合与原始检索结果总量一致",
  };
  return translations[message] ?? message;
}

function analyticalResultSummary(value: JsonValue | undefined): string {
  const result = asRecord(value);
  if (result === null) return "未返回可展示的统计结果。";
  const items = Object.entries(result)
    .filter((entry): entry is [string, string | number | boolean] => {
      const [key, item] = entry;
      return key !== "column" && (typeof item === "string" || typeof item === "number" || typeof item === "boolean");
    })
    .map(([key, item]) => `${key}: ${String(item)}`);
  if (items.length > 0) return items.join("；");
  const collection = Object.entries(result).find(
    (entry): entry is [string, JsonValue[]] => Array.isArray(entry[1]),
  );
  return collection === undefined
    ? "统计结果已计算；详细数值可结合对应数据表核查。"
    : `${collection[0]}：已返回 ${collection[1].length} 项结果。`;
}

function EvidenceTableBrowser({ datasets }: { datasets: DatasetRowsResponse[] }) {
  const ordered = [...datasets].sort((left, right) => {
    if (left.kind === right.kind) return left.grain.length - right.grain.length;
    return left.kind === "base" ? -1 : 1;
  });
  const [selectedId, setSelectedId] = useState(ordered[0]?.dataset_id ?? "");
  const selected = ordered.find((item) => item.dataset_id === selectedId) ?? ordered[0];
  if (selected === undefined) return <p className="drawer-empty">暂时没有可展示的数据表。</p>;

  return (
    <section className="evidence-section" aria-labelledby="evidence-data-title">
      <div className="evidence-section-heading">
        <div>
          <span>01 · 数据</span>
          <h3 id="evidence-data-title">OpenSearch 返回了什么</h3>
        </div>
        <a className="download-link" href={workspaceApi.datasetCsvUrl(selected.dataset_id)}>下载当前表</a>
      </div>
      <p className="evidence-help">
        “原始检索结果”指 OpenSearch 返回的受控聚合桶；系统默认执行 size=0 聚合查询，不在业务证据中暴露原始文档。
      </p>
      <label className="evidence-select-label" htmlFor="evidence-dataset">查看数据层级</label>
      <select
        id="evidence-dataset"
        className="evidence-select"
        value={selected.dataset_id}
        onChange={(event) => setSelectedId(event.target.value)}
      >
        {ordered.map((dataset) => (
          <option key={dataset.dataset_id} value={dataset.dataset_id}>
            {datasetTitle(dataset)} · {dataset.rows.length} 行
          </option>
        ))}
      </select>
      <div className="evidence-table-meta">
        <span>{selected.kind === "base" ? "原始检索结果" : "确定性派生结果"}</span>
        <span>粒度：{selected.grain.length === 0 ? "整体" : selected.grain.join(" × ")}</span>
        <span>{selected.complete ? "结果完整" : "结果可能被截断"}</span>
      </div>
      <DataTable dataset={selected} hiddenColumns={["metric_metadata", "raw_metrics"]} />
    </section>
  );
}

function BusinessEvidenceContent({ evidence }: { evidence: BusinessEvidence }) {
  const datasetIds = evidence.data_tables ?? [];
  const datasetQueries = useQueries({
    queries: datasetIds.map((datasetId) => ({
      queryKey: ["dataset", datasetId],
      queryFn: ({ signal }: { signal: AbortSignal }) => workspaceApi.getDatasetRows(datasetId, signal),
      staleTime: Number.POSITIVE_INFINITY,
    })),
  });
  const datasets = datasetQueries
    .map((query) => query.data)
    .filter((item): item is DatasetRowsResponse => item !== undefined);
  const calculations = extractMetricCalculations(evidence, datasets);
  const quality = evidence.quality ?? [];
  const reconciliations = evidence.reconciliations ?? [];
  const exploratoryAnalysis = evidence.exploratory_analysis ?? [];
  const loading = datasetQueries.some((query) => query.isPending);
  const failed = datasetQueries.some((query) => query.isError);

  return (
    <>
      <section className="evidence-scope" aria-label="分析范围">
        <div><span>分析目标</span><strong>{asString(evidence.scope.analysis_goal) ?? "—"}</strong></div>
        <div><span>时间范围</span><strong>{timeRangeSummary(evidence)}</strong></div>
        <div><span>语义版本</span><strong>{asString(evidence.scope.semantic_package_version) ?? "—"}</strong></div>
      </section>
      {loading ? <div className="drawer-state">正在载入检索结果与指标证据…</div> : null}
      {failed ? <div className="drawer-state error-text">部分证据数据暂时无法读取。</div> : null}
      {datasets.length > 0 ? <EvidenceTableBrowser datasets={datasets} /> : null}
      <section className="evidence-section" aria-labelledby="metric-calculation-title">
        <div className="evidence-section-heading">
          <div><span>02 · 计算</span><h3 id="metric-calculation-title">指标是怎么得到的</h3></div>
        </div>
        <p className="evidence-help">这里只展示已落地的计算结果；公式、分子、分母和排除项来自后端 MetricDefinition 与指标证据。</p>
        <div className="calculation-list">
          {calculations.map((item) => (
            <article className="calculation-card" key={item.metricId}>
              <div className="calculation-title"><strong>{item.label}</strong><span>{item.quality}</span></div>
              <p className="calculation-value">{item.formattedValue}</p>
              <code>{item.expression}</code>
              <p>{item.definition}</p>
              {item.exclusions.length > 0 ? <small>排除项：{item.exclusions.join("，")}</small> : <small>无额外排除项</small>}
            </article>
          ))}
          {!loading && calculations.length === 0 ? <p className="drawer-empty">本次没有可展示的正式指标计算。</p> : null}
        </div>
      </section>
      <section className="evidence-section" aria-labelledby="evidence-analysis-title">
        <div className="evidence-section-heading">
          <div><span>03 · 分析</span><h3 id="evidence-analysis-title">AI 选择的统计分析</h3></div>
        </div>
        <p className="evidence-help">AI 选择分析方法与指标列；后端按受治理方法在已验证数据上确定性计算。未适用的方法也会在这里保留原因。</p>
        <div className="calculation-list">
          {exploratoryAnalysis.map((item, index) => (
            <article className="calculation-card" key={asString(item.request_id) ?? `analysis-${String(index)}`}>
              <div className="calculation-title">
                <strong>{asString(item.method_id) ?? "统计分析"}</strong>
                <span>{asString(item.decision) ?? "UNKNOWN"}</span>
              </div>
              <p>{asString(item.measure_column) ?? "未标明指标列"} · 样本 {asNumber(item.sample_size) ?? 0}</p>
              <p>{analyticalResultSummary(item.result)}</p>
              <small>{asString(item.reason) ?? "无额外说明"}</small>
            </article>
          ))}
          {exploratoryAnalysis.length === 0 ? <p className="drawer-empty">本次没有额外的探索性统计计算。</p> : null}
        </div>
      </section>
      <section className="evidence-section" aria-labelledby="evidence-qa-title">
        <div className="evidence-section-heading">
          <div><span>04 · 核验</span><h3 id="evidence-qa-title">质量与对账</h3></div>
        </div>
        <ul className="evidence-checks">
          {reconciliations.map((item, index) => (
            <li key={`reconciliation-${String(index)}`} className={item.passed === true ? "passed" : "failed"}>
              <strong>{item.passed === true ? "通过" : "未通过"}</strong>
              <span>{readableQuality(asString(item.message) ?? "聚合对账")}</span>
            </li>
          ))}
          {quality.map((item, index) => (
            <li key={`quality-${String(index)}`} className={item.passed === true ? "passed" : "failed"}>
              <strong>{item.passed === true ? "通过" : "注意"}</strong>
              <span>{readableQuality(asString(item.message) ?? "数据质量检查")}</span>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}

function AdvancedEvidenceContent({ evidence }: { evidence: AdvancedEvidence }) {
  const planSteps = Array.isArray(evidence.query_plan.steps) ? evidence.query_plan.steps : [];
  const executions = evidence.execution_summaries ?? [];
  return (
    <>
      <p className="privacy-note">
        高级证据面向分析师与开发者：重点展示实际提交给 OpenSearch 的只读 DSL，以及对应的执行与结果契约摘要。
      </p>
      <section className="evidence-scope" aria-label="查询计划摘要">
        <div><span>查询步数</span><strong>{planSteps.length}</strong></div>
        <div><span>复用策略</span><strong>{asString(evidence.query_plan.reuse_strategy) ?? "—"}</strong></div>
        <div><span>已编译查询</span><strong>{evidence.compiled_queries?.length ?? 0}</strong></div>
      </section>
      <section className="evidence-section" aria-labelledby="dsl-title">
        <div className="evidence-section-heading">
          <div><span>OpenSearch · Read only</span><h3 id="dsl-title">实际检索 DSL</h3></div>
        </div>
        <div className="dsl-list">
          {(evidence.compiled_queries ?? []).map((query, index) => {
            const semantics = asRecord(query.semantics);
            const queryId = asString(query.object_id);
            const execution = executions.find((item) => asString(item.query_id) === queryId);
            return (
              <details className="dsl-card" key={queryId ?? `query-${String(index)}`} open={index === 0}>
                <summary>
                  <span>查询 {index + 1}</span>
                  <strong>{asString(query.step_id) ?? "未命名步骤"}</strong>
                </summary>
                <div className="query-meta-grid">
                  <span>索引<strong>{asStringArray(query.indices).join("、") || "—"}</strong></span>
                  <span>数据粒度<strong>{asStringArray(semantics?.grain).join(" × ") || "整体"}</strong></span>
                  <span>执行状态<strong>{asString(execution?.status) ?? "—"}</strong></span>
                  <span>分片失败<strong>{asNumber(execution?.shard_failures) ?? 0}</strong></span>
                </div>
                <pre className="evidence-dsl">{JSON.stringify(query.query_dsl ?? {}, null, 2)}</pre>
              </details>
            );
          })}
        </div>
      </section>
    </>
  );
}

export function EvidenceDrawer({ answerId, onClose }: EvidenceDrawerProps) {
  const [tab, setTab] = useState<"business" | "advanced">("business");
  const evidenceQuery = useQuery({
    queryKey: ["evidence", answerId],
    queryFn: ({ signal }) => workspaceApi.getEvidence(answerId ?? "", signal),
    enabled: answerId !== null,
    staleTime: Number.POSITIVE_INFINITY,
  });

  if (answerId === null) return null;

  const evidence = evidenceQuery.data;
  return (
    <div className="drawer-layer" role="presentation" onMouseDown={onClose}>
      <aside
        className="evidence-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="drawer-header">
          <div>
            <span className="block-kicker">可追溯性</span>
            <h2 id="evidence-title">证据与口径</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭证据抽屉">×</button>
        </div>
        {evidenceQuery.isPending ? <div className="drawer-state">正在载入证据…</div> : null}
        {evidenceQuery.isError ? <div className="drawer-state error-text">证据暂时无法读取。</div> : null}
        {evidence === undefined ? null : (
          <>
            <div className="tabs" role="tablist" aria-label="证据层级">
              <button className={tab === "business" ? "active" : ""} type="button" role="tab" aria-selected={tab === "business"} onClick={() => setTab("business")}>业务证据</button>
              {evidence.advanced === undefined || evidence.advanced === null ? null : (
                <button className={tab === "advanced" ? "active" : ""} type="button" role="tab" aria-selected={tab === "advanced"} onClick={() => setTab("advanced")}>高级证据 · DSL</button>
              )}
            </div>
            <div className="drawer-content">
              {tab === "business" ? (
                <BusinessEvidenceContent evidence={evidence.business} />
              ) : evidence.advanced === undefined || evidence.advanced === null ? null : (
                <AdvancedEvidenceContent evidence={evidence.advanced} />
              )}
            </div>
          </>
        )}
      </aside>
    </div>
  );
}
