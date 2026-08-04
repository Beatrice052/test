import { useQuery } from "@tanstack/react-query";

import { workspaceApi } from "../api/client";
import type { AnswerSnapshot, DashboardBlock, KpiItem } from "../api/generated";
import { contentText } from "../lib/format";
import { DataTable } from "./DataTable";
import { SafeChart } from "./SafeChart";

function DatasetBlock({ block }: { block: DashboardBlock }) {
  const datasetId = block.dataset_id ?? "";
  const datasetQuery = useQuery({
    queryKey: ["dataset", datasetId],
    queryFn: ({ signal }) => workspaceApi.getDatasetRows(datasetId, signal),
    enabled: datasetId.length > 0,
    staleTime: Number.POSITIVE_INFINITY,
  });

  if (datasetQuery.isPending) return <div className="block-loading">正在载入验证数据…</div>;
  if (datasetQuery.isError) return <div className="block-error">数据集暂时无法读取。</div>;
  if (datasetQuery.data === undefined) return <div className="block-error">这个区块缺少数据集引用。</div>;

  if (block.type === "data_table" || block.type === "pivot_table" || block.chart_type === "table") {
    // Technical metric evidence belongs in the Evidence drawer, not in a business
    // fallback table produced when a requested chart is incompatible.
    return <DataTable dataset={datasetQuery.data} hiddenColumns={["metric_metadata", "raw_metrics"]} />;
  }
  return <SafeChart block={block} dataset={datasetQuery.data} />;
}

function BlockHeader({ block, kicker }: { block: DashboardBlock; kicker: string }) {
  return (
    <div className="block-heading">
      <div>
        <span className="block-kicker">{kicker}</span>
        <h3 id={`${block.block_id}-title`}>{block.title ?? "分析结果"}</h3>
      </div>
      {block.dataset_id === undefined || block.dataset_id === null ? null : (
        <a className="download-link" href={workspaceApi.datasetCsvUrl(block.dataset_id)}>下载 CSV</a>
      )}
    </div>
  );
}

function KpiCard({ item }: { item: KpiItem }) {
  const qualityLabel = item.quality === "insufficient_sample"
    ? "样本不足"
    : item.quality === "not_applicable"
      ? "不适用"
      : "已验证";
  const semanticLabel = {
    certified: "认证指标",
    governed: "治理指标",
    operational: "运行护栏",
    exploratory: "探索指标",
  }[item.semantic_level];
  return (
    <article className={`kpi-card quality-${item.quality ?? "valid"}`}>
      <div className="kpi-meta"><span>{semanticLabel}</span><span>{qualityLabel}</span></div>
      <p className="kpi-label">{item.label}</p>
      <p className="kpi-value">{item.formatted_value}</p>
      <p className="kpi-definition">{item.definition}</p>
    </article>
  );
}

function KpiBlock({ block }: { block: DashboardBlock }) {
  return (
    <section className="dashboard-block kpi-block" aria-labelledby={`${block.block_id}-title`}>
      <BlockHeader block={block} kicker="指标概览" />
      {block.description ? <p className="block-description">{block.description}</p> : null}
      <div className="kpi-grid">
        {(block.kpis ?? []).map((item) => <KpiCard key={item.kpi_id} item={item} />)}
      </div>
    </section>
  );
}

function InsightBlock({ block }: { block: DashboardBlock }) {
  const items = block.insights ?? [];
  return (
    <section className="dashboard-block insight-block" aria-labelledby={`${block.block_id}-title`}>
      <BlockHeader block={block} kicker={block.type === "context_summary" ? "范围与口径" : "数据解读"} />
      {block.description ? <p className="block-description">{block.description}</p> : null}
      <ol className="insight-list">
        {items.map((item, index) => <li key={`${index}-${item}`}><span>{index + 1}</span><p>{item}</p></li>)}
      </ol>
    </section>
  );
}

function FollowUpBlock({ block }: { block: DashboardBlock }) {
  return (
    <section className="dashboard-block follow-up-block" aria-labelledby={`${block.block_id}-title`}>
      <BlockHeader block={block} kicker="继续探索" />
      <div className="suggestion-list">
        {(block.suggestions ?? []).map((item) => <span key={item}>{item}</span>)}
      </div>
    </section>
  );
}

function ContentBlock({ block }: { block: DashboardBlock }) {
  if (block.type === "kpi_group") return <KpiBlock block={block} />;
  if (block.type === "insight_list" || block.type === "context_summary") {
    return <InsightBlock block={block} />;
  }
  if (block.type === "follow_up_suggestions") return <FollowUpBlock block={block} />;
  const text = contentText(block.content);
  const tone = block.type === "warning" ? " warning-block" : "";
  const answer = block.type === "answer_summary" ? " answer-summary-block" : "";
  const insights = block.insights ?? [];
  return (
    <section className={`dashboard-block narrative-block${tone}${answer}`} aria-labelledby={`${block.block_id}-title`}>
      <span className="block-kicker">{block.type === "answer_summary" ? "结论与关键发现" : "分析提示"}</span>
      {block.title === undefined || block.title === null ? null : <h3 id={`${block.block_id}-title`}>{block.title}</h3>}
      <p>{text || "暂无可展示内容。"}</p>
      {block.type === "answer_summary" && insights.length > 0 ? (
        <div className="answer-findings">
          <strong>补充发现</strong>
          <ul>
            {insights.map((item) => <li key={item}>{item}</li>)}
          </ul>
        </div>
      ) : null}
      {block.description ? <small>{block.description}</small> : null}
    </section>
  );
}

function normalizeNarrative(value: string): string {
  return value.toLocaleLowerCase().replace(/[\p{P}\p{S}\s]/gu, "");
}

function analysisBlocks(blocks: DashboardBlock[]): DashboardBlock[] {
  // Older persisted answers may still contain the former technical-detail and
  // full-width QA blocks. Keep those answers compatible with the current
  // information architecture: both now live exclusively in Evidence.
  const businessBlocks = blocks.filter((block) =>
    block.block_id !== "block_data_quality"
    && !(
      (block.type === "data_table" || block.type === "pivot_table")
      && block.title === "聚合明细与指标口径"
    ),
  );
  const summary = businessBlocks.find((block) => block.type === "answer_summary");
  if (summary === undefined) return businessBlocks;
  const summaryText = contentText(summary.content);
  const normalizedSummary = normalizeNarrative(summaryText);
  const candidates = [
    ...(summary.insights ?? []),
    ...businessBlocks
      .filter((block) => block.type === "insight_list")
      .flatMap((block) => block.insights ?? []),
  ];
  const seen = new Set<string>();
  const insights = candidates.filter((item) => {
    const normalized = normalizeNarrative(item);
    if (normalized.length === 0 || normalizedSummary.includes(normalized) || seen.has(normalized)) {
      return false;
    }
    seen.add(normalized);
    return true;
  });
  return businessBlocks
    .filter((block) => block.type !== "insight_list")
    .map((block) => block.block_id === summary.block_id ? { ...block, insights } : block);
}

function VisualBlock({ block }: { block: DashboardBlock }) {
  const isTable = block.type !== "chart";
  const analysis = block.chart_analysis;
  const caveats = analysis?.caveats ?? [];
  return (
    <section className={`dashboard-block visual-block${isTable ? " table-block" : ""}`} aria-labelledby={`${block.block_id}-title`}>
      <BlockHeader block={block} kicker={isTable ? "结果表格" : "分析图表"} />
      {isTable && block.description ? (
        <div className="chart-explanation"><strong>展示内容</strong><p>{block.description}</p></div>
      ) : null}
      <DatasetBlock block={block} />
      {!isTable && analysis ? (
        <div className="chart-analysis" aria-label="图表解读">
          <div className="chart-purpose"><strong>图表解读</strong><p>{analysis.purpose}</p></div>
          <div className="chart-findings">
            <ul>
              {analysis.findings.map((finding) => (
                <li key={finding.claim_id}>{finding.text}</li>
              ))}
            </ul>
          </div>
          {caveats.length > 0 ? (
            <div className="chart-caveats"><strong>注意</strong><p>{caveats.join("；")}</p></div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

export function Dashboard({ answer }: { answer: AnswerSnapshot }) {
  const dashboard = answer.dashboard_spec;
  if (dashboard === undefined || dashboard === null) {
    return <div className="empty-inline">本次回答没有可展示的 Dashboard。</div>;
  }
  const blocks = analysisBlocks(dashboard.blocks);
  return (
    <section className="dashboard-shell" aria-label={dashboard.title}>
      <div className="dashboard-title-row">
        <div><span className="header-kicker">Dynamic Dashboard</span><h2>{dashboard.title}</h2></div>
        <span>{blocks.filter((block) => block.type === "chart").length} 个分析图表</span>
      </div>
      <div className="dashboard-grid">
        {blocks.map((block) =>
          block.type === "chart" || block.type === "data_table" || block.type === "pivot_table" ? (
            <VisualBlock key={block.block_id} block={block} />
          ) : (
            <ContentBlock key={block.block_id} block={block} />
          ),
        )}
      </div>
    </section>
  );
}
