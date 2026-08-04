import type { EChartsOption } from "echarts";

import type { DashboardBlock, DatasetRowsResponse } from "../api/generated";

const PALETTE = ["#1f6f78", "#d58a3b", "#557a5f", "#9b6a86", "#7a6c52"];

function textValue(value: unknown): string {
  if (typeof value === "string") {
    return /^\d{4}-\d{2}/.test(value) ? value.slice(0, 7) : value;
  }
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "—";
}

function numberValue(value: unknown, percent: boolean): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return percent ? Number((value * 100).toFixed(4)) : value;
}

function unique(values: string[]): string[] {
  return [...new Set(values)];
}

function sameMembers(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((item) => right.includes(item));
}

type ParetoPoint = {
  row_id: string;
  category: string | number | boolean | null;
  value: number;
  cumulative_percent: number;
};

function governedParetoPoints(block: DashboardBlock): ParetoPoint[] {
  const content = block.content as Record<string, unknown> | undefined;
  const raw = content?.pareto_points;
  if (!Array.isArray(raw)) return [];
  return raw.filter((item): item is ParetoPoint => {
    if (typeof item !== "object" || item === null) return false;
    const point = item as Record<string, unknown>;
    return typeof point.row_id === "string"
      && (typeof point.category === "string"
        || typeof point.category === "number"
        || typeof point.category === "boolean"
        || point.category === null)
      && typeof point.value === "number"
      && Number.isFinite(point.value)
      && typeof point.cumulative_percent === "number"
      && Number.isFinite(point.cumulative_percent);
  });
}

export function validateChartDataset(
  block: DashboardBlock,
  dataset: DatasetRowsResponse,
): string | null {
  const categoryField = block.encoding?.x ?? block.encoding?.category ?? dataset.grain[0];
  const seriesField = block.encoding?.series ?? block.encoding?.color ?? undefined;
  const encodedGrain = unique(
    [categoryField, seriesField].filter((item): item is string => item !== undefined),
  );
  const singleScopeBar = encodedGrain.length === 0
    && dataset.grain.length === 0
    && dataset.rows.length === 1
    && block.chart_type === "bar";
  if (encodedGrain.length === 0 && !singleScopeBar) return "图表没有绑定分析维度。";
  const columnNames = dataset.columns.map((column) => column.name);
  const missing = encodedGrain.filter((item) => !columnNames.includes(item));
  if (missing.length > 0) return `图表字段不存在：${missing.join("、")}。`;
  if (!sameMembers(dataset.grain, encodedGrain)) {
    return "图表维度与数据粒度不一致，已停止渲染以避免重复或错误汇总。";
  }
  const keys = dataset.rows.map((row) => JSON.stringify(
    encodedGrain.map((field) => row.values[field] ?? null),
  ));
  if (new Set(keys).size !== keys.length) {
    return "图表数据在当前维度下存在重复行，已停止渲染以避免误导。";
  }
  return null;
}

export function buildSafeOption(block: DashboardBlock, dataset: DatasetRowsResponse): EChartsOption {
  const validationError = validateChartDataset(block, dataset);
  if (validationError !== null) throw new Error(validationError);
  const categoryField = block.encoding?.x ?? block.encoding?.category ?? dataset.grain[0];
  const valueField = block.encoding?.y ?? block.encoding?.value;
  const seriesField: string | undefined = block.encoding?.series
    ?? block.encoding?.color
    ?? undefined;
  const percent = block.axis_format?.value === "percent";
  const singleScopeBar = categoryField === undefined
    && dataset.grain.length === 0
    && dataset.rows.length === 1
    && block.chart_type === "bar";
  const categories = singleScopeBar
    ? [block.title ?? "当前查询范围"]
    : unique(dataset.rows.map((row) => textValue(row.values[categoryField ?? ""])));
  const axisLabel = percent ? { formatter: "{value}%" } : undefined;
  const common: EChartsOption = {
    animationDuration: 260,
    color: PALETTE,
    grid: { left: 42, right: 20, top: 34, bottom: 48, containLabel: true },
    tooltip: { trigger: "axis", confine: true },
    textStyle: { color: "#334b48", fontFamily: "Inter, Noto Sans SC, sans-serif" },
  };

  if (block.chart_type === "donut") {
    const points = dataset.rows.flatMap((row) => {
      const value = numberValue(row.values[valueField ?? ""], percent);
      return value === null
        ? []
        : [{ name: textValue(row.values[categoryField ?? ""]), value }];
    });
    return {
      ...common,
      tooltip: { trigger: "item", confine: true },
      legend: { bottom: 0, type: "scroll", icon: "circle" },
      series: [{
        type: "pie",
        radius: ["48%", "72%"],
        center: ["50%", "43%"],
        padAngle: 2,
        itemStyle: { borderColor: "#fff", borderWidth: 2 },
        label: { formatter: percent ? "{b}\n{c}%" : "{b}\n{c}" },
        data: points,
      }],
    };
  }

  if (block.chart_type === "heatmap" && seriesField !== undefined) {
    const seriesNames = unique(
      dataset.rows.map((row) => textValue(row.values[seriesField])),
    );
    const heatmapData = dataset.rows.flatMap((row) => {
      const value = numberValue(row.values[valueField ?? ""], percent);
      return value === null
        ? []
        : [[
          categories.indexOf(textValue(row.values[categoryField ?? ""])),
          seriesNames.indexOf(textValue(row.values[seriesField])),
          value,
        ]];
    });
    if (heatmapData.length === 0) throw new Error("图表没有可用的数值数据。");
    const values: number[] = heatmapData.map((item) => item[2]!);
    return {
      ...common,
      tooltip: { position: "top", confine: true },
      grid: { left: 42, right: 58, top: 24, bottom: 52, containLabel: true },
      xAxis: { type: "category", data: categories, splitArea: { show: true } },
      yAxis: { type: "category", data: seriesNames, splitArea: { show: true } },
      visualMap: {
        min: Math.min(...values),
        max: Math.max(...values),
        calculable: false,
        orient: "vertical",
        right: 0,
        top: "middle",
        inRange: { color: ["#edf5f1", "#1f6f78"] },
      },
      series: [{
        type: "heatmap",
        data: heatmapData,
        label: { show: dataset.rows.length <= 24 },
        emphasis: { itemStyle: { shadowBlur: 8, shadowColor: "rgba(0, 0, 0, 0.18)" } },
      }],
    };
  }

  if (block.chart_type === "pareto" && seriesField === undefined) {
    const points = governedParetoPoints(block);
    if (points.length === 0) throw new Error("Pareto 图缺少后端验证的累计贡献数据。");
    return {
      ...common,
      legend: { top: 0, data: ["贡献值", "累计占比"] },
      grid: { left: 42, right: 48, top: 58, bottom: 54, containLabel: true },
      xAxis: {
        type: "category",
        data: points.map((point) => textValue(point.category)),
        axisLabel: { rotate: points.length > 7 ? 28 : 0 },
      },
      yAxis: [
        { type: "value", name: "贡献值", splitLine: { lineStyle: { color: "#e7ece8" } } },
        { type: "value", name: "累计占比", min: 0, max: 100, axisLabel: { formatter: "{value}%" } },
      ],
      series: [
        {
          name: "贡献值",
          type: "bar",
          data: points.map((point) => point.value),
          barMaxWidth: 38,
          itemStyle: { borderRadius: [4, 4, 0, 0] },
        },
        {
          name: "累计占比",
          type: "line",
          yAxisIndex: 1,
          data: points.map((point) => point.cumulative_percent),
          symbol: "circle",
          symbolSize: 7,
        },
      ],
    };
  }

  const seriesNames = seriesField === undefined
    ? [""]
    : unique(dataset.rows.map((row) => textValue(row.values[seriesField])));
  const chartSeries = seriesNames.map((seriesName) => {
    const matchingRows = seriesField === undefined
      ? dataset.rows
      : dataset.rows.filter((row) => textValue(row.values[seriesField]) === seriesName);
    const valueByCategory = new Map(
      matchingRows.map((row) => [
        singleScopeBar ? categories[0] : textValue(row.values[categoryField ?? ""]),
        numberValue(row.values[valueField ?? ""], percent),
      ]),
    );
    const type = block.chart_type === "line" ? "line" : "bar";
    return {
      name: seriesName || undefined,
      type,
      data: categories.map((category) => valueByCategory.get(category) ?? null),
      stack: block.stack || block.chart_type === "stacked_bar" ? "total" : undefined,
      smooth: false,
      showSymbol: type === "line",
      symbol: "circle",
      symbolSize: 7,
      barMaxWidth: seriesField === undefined ? 44 : 34,
      emphasis: { focus: seriesField === undefined ? "self" : "series" },
      itemStyle: { borderRadius: type === "bar" ? [4, 4, 0, 0] : 0 },
    };
  });

  if (block.visualization_intent === "ranked_comparison" && seriesField === undefined) {
    const rows = dataset.rows
      .flatMap((row) => {
        const value = numberValue(row.values[valueField ?? ""], percent);
        return value === null
          ? []
          : [{ category: textValue(row.values[categoryField ?? ""]), value }];
      })
      .sort((left, right) => left.value - right.value);
    return {
      ...common,
      grid: { left: 24, right: 34, top: 24, bottom: 28, containLabel: true },
      xAxis: {
        type: "value",
        ...(axisLabel === undefined ? {} : { axisLabel }),
        splitLine: { lineStyle: { color: "#e7ece8" } },
      },
      yAxis: { type: "category", data: rows.map((row) => row.category), axisTick: { show: false } },
      series: [{
        type: block.chart_type === "dot" ? "scatter" : "bar",
        data: rows.map((row) => row.value),
        barMaxWidth: 30,
        label: { show: true, position: "right", formatter: percent ? "{c}%" : "{c}" },
        itemStyle: { borderRadius: [0, 5, 5, 0] },
      }],
    };
  }

  return {
    ...common,
    legend: seriesNames.length > 1 ? { top: 0, type: "scroll", icon: "circle" } : undefined,
    grid: { left: 42, right: 20, top: seriesNames.length > 1 ? 58 : 28, bottom: 52, containLabel: true },
    xAxis: {
      type: "category",
      data: categories,
      boundaryGap: block.chart_type !== "line",
      axisLabel: { rotate: categories.length > 7 ? 28 : 0 },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      ...(axisLabel === undefined ? {} : { axisLabel }),
      splitLine: { lineStyle: { color: "#e7ece8" } },
    },
    series: chartSeries,
  } as EChartsOption;
}
