import { describe, expect, it } from "vitest";

import type { BusinessEvidence, DatasetRowsResponse } from "../src/api/generated";
import { datasetTitle, extractMetricCalculations } from "../src/lib/evidenceModel";

describe("readable evidence model", () => {
  it("extracts generic numerator, denominator, exclusion, and result evidence", () => {
    const evidence: BusinessEvidence = {
      scope: {},
      metric_definitions: [{
        metric_id: "quality_ratio",
        display_name: "质量率",
        business_definition: "符合质量条件的记录占正式分母的比例。",
      }],
    };
    const dataset: DatasetRowsResponse = {
      object_id: "ds_overall",
      dataset_id: "overall_metrics",
      kind: "derived",
      grain: [],
      columns: [{ name: "metric_metadata", data_type: "metric", semantic_role: "metadata" }],
      rows: [{
        row_id: "row_overall",
        values: {
          metric_metadata: {
            quality_ratio: {
              metric_id: "quality_ratio",
              value: 0.2,
              unit: "ratio",
              numerator: 20,
              denominator: 100,
              excluded: { unknown: 4 },
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

    expect(extractMetricCalculations(evidence, [dataset])).toEqual([
      expect.objectContaining({
        metricId: "quality_ratio",
        label: "质量率",
        formattedValue: "20%",
        expression: "20 ÷ 100 = 20%",
        exclusions: ["unknown: 4"],
      }),
    ]);
    expect(datasetTitle(dataset)).toBe("整体指标结果");
  });
});
