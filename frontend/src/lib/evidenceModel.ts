import type {
  BusinessEvidence,
  DatasetRowsResponse,
  JsonValue,
} from "../api/generated";

export type JsonRecord = Record<string, JsonValue>;

export type MetricCalculation = {
  metricId: string;
  label: string;
  definition: string;
  formattedValue: string;
  expression: string;
  exclusions: string[];
  quality: string;
  datasetId: string;
};

export function asRecord(value: JsonValue | undefined): JsonRecord | null {
  if (value === null || value === undefined || Array.isArray(value) || typeof value !== "object") {
    return null;
  }
  return value as JsonRecord;
}

export function asString(value: JsonValue | undefined): string | null {
  return typeof value === "string" ? value : null;
}

export function asNumber(value: JsonValue | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function asStringArray(value: JsonValue | undefined): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function formatMetricValue(value: number | null, unit: string | null): string {
  if (value === null) return "—";
  if (unit === "ratio") {
    return `${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value * 100)}%`;
  }
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value);
}

function metricDefinitions(evidence: BusinessEvidence): Map<string, JsonRecord> {
  return new Map(
    (evidence.metric_definitions ?? [])
      .map((item) => [asString(item.metric_id) ?? "", item] as const)
      .filter(([metricId]) => metricId.length > 0),
  );
}

export function extractMetricCalculations(
  evidence: BusinessEvidence,
  datasets: DatasetRowsResponse[],
): MetricCalculation[] {
  const definitions = metricDefinitions(evidence);
  const ordered = [...datasets].sort((left, right) => left.grain.length - right.grain.length);
  const results: MetricCalculation[] = [];
  const seen = new Set<string>();
  for (const dataset of ordered) {
    for (const row of dataset.rows) {
      const metadata = asRecord(row.values.metric_metadata);
      if (metadata === null) continue;
      for (const [fallbackMetricId, raw] of Object.entries(metadata)) {
        const metric = asRecord(raw);
        if (metric === null) continue;
        const metricId = asString(metric.metric_id) ?? fallbackMetricId;
        if (seen.has(metricId)) continue;
        const definition = definitions.get(metricId);
        const numerator = asNumber(metric.numerator);
        const denominator = asNumber(metric.denominator);
        const value = asNumber(metric.value);
        const unit = asString(metric.unit);
        const exclusions = asRecord(metric.excluded);
        const exclusionItems = exclusions === null
          ? []
          : Object.entries(exclusions).map(([key, count]) => {
              const displayed = typeof count === "number" || typeof count === "string"
                ? String(count)
                : "—";
              return `${key}: ${displayed}`;
            });
        const expression = denominator !== null
          ? `${formatMetricValue(numerator, null)} ÷ ${formatMetricValue(denominator, null)} = ${formatMetricValue(value, unit)}`
          : `按已验证数据汇总 = ${formatMetricValue(value, unit)}`;
        results.push({
          metricId,
          label: asString(definition?.display_name) ?? metricId,
          definition: asString(definition?.business_definition) ?? "使用语义包中已确认的指标定义。",
          formattedValue: formatMetricValue(value, unit),
          expression,
          exclusions: exclusionItems,
          quality: asString(metric.quality) ?? "UNKNOWN",
          datasetId: dataset.dataset_id,
        });
        seen.add(metricId);
      }
    }
  }
  return results;
}

export function datasetTitle(dataset: DatasetRowsResponse): string {
  if (dataset.kind === "base") return "OpenSearch 检索结果（聚合桶）";
  if (dataset.grain.length === 0) return "整体指标结果";
  const columns = new Map(dataset.columns.map((column) => [column.name, column.display_name]));
  const grain = dataset.grain.map((field) => columns.get(field) ?? field.split(".").at(-1) ?? field);
  return `按 ${grain.join(" × ")} 聚合`;
}

export function timeRangeSummary(evidence: BusinessEvidence): string {
  const range = asRecord(evidence.scope.time_range);
  if (range === null) return "未提供";
  const from = asString(range.from_inclusive) ?? "—";
  const to = asString(range.to_exclusive) ?? "—";
  const timezone = asString(range.timezone) ?? "—";
  return `${from.slice(0, 10)} 至 ${to.slice(0, 10)}（右开区间，${timezone}）`;
}
