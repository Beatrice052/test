import * as echarts from "echarts/core";
import { BarChart, HeatmapChart, LineChart, PieChart, ScatterChart } from "echarts/charts";
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useMemo, useRef } from "react";

import type { DashboardBlock, DatasetRowsResponse } from "../api/generated";
import { buildSafeOption } from "../lib/safeChartOption";

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  ScatterChart,
  HeatmapChart,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
]);

export function SafeChart({ block, dataset }: { block: DashboardBlock; dataset: DatasetRowsResponse }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const result = useMemo(() => {
    try {
      return { option: buildSafeOption(block, dataset), error: null };
    } catch (error) {
      return {
        option: null,
        error: error instanceof Error ? error.message : "图表数据暂时无法验证。",
      };
    }
  }, [block, dataset]);

  useEffect(() => {
    const element = containerRef.current;
    if (element === null || result.option === null) return;
    const chart = echarts.init(element, undefined, { renderer: "canvas" });
    chart.setOption(result.option, { notMerge: true });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(element);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [result.option]);

  if (result.error !== null) {
    return <div className="chart-validation-error" role="status">{result.error}</div>;
  }
  return <div className="chart-canvas" ref={containerRef} role="img" aria-label={block.title ?? "数据图表"} />;
}
