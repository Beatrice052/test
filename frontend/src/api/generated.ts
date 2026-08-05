/* Generated from backend OpenAPI by scripts/generate_frontend_types.py. */
/* Do not edit manually. */

export type ActiveAnalyticalContext = {
  analytical_base_answer_id?: string | null;
  dataset_ids?: Array<string>;
  metric_ids?: Array<string>;
  dimension_ids?: Array<string>;
  grain?: Array<string>;
  tasks?: Array<AnalyticalTask>;
  filter_summary?: Array<string>;
  time_summary?: string | null;
};

export type AdvancedEvidence = {
  query_plan: {
  [key: string]: JsonValue;
};
  compiled_queries?: Array<{
  [key: string]: JsonValue;
}>;
  execution_summaries?: Array<{
  [key: string]: JsonValue;
}>;
  result_contracts?: Array<{
  [key: string]: JsonValue;
}>;
};

export type AggregationKind = "document_count" | "value_count" | "cardinality" | "sum" | "avg" | "min" | "max" | "stats" | "extended_stats" | "percentiles";

export type AggregationParameters = {
  percents?: Array<number>;
  precision_threshold?: number | null;
  sigma?: number | null;
  keyed?: boolean;
};

export type AggregationSemantics = "additive" | "semi_additive" | "non_additive" | "weighted";

export type AggregationSpec = {
  measure_id: string;
  source_field_id?: string | null;
  aggregation: AggregationKind;
  parameters?: AggregationParameters;
  unit?: string;
  semantics?: AggregationSemantics;
  approximate?: boolean;
};

export type AnalysisBudget = {
  max_queries?: number;
  max_buckets?: number;
  max_blocks?: number;
};

export type AnalysisPlan = {
  schema_version?: string;
  object_id: string;
  created_at: string;
  content_hash: string;
  provenance: Provenance;
  analysis_goal: string;
  question_archetype: string;
  turn_relation: TurnKind;
  scope: AnalysisScope;
  metric_decisions: Array<MetricDecision>;
  measure_decisions?: Array<MeasureDecision>;
  entity_references?: Array<EntityReference>;
  tasks: Array<AnalyticalTask>;
  presentation_preference?: PresentationPreference;
  clarification?: Clarification | null;
  assumptions?: Array<string>;
  limitations?: Array<string>;
  budget?: AnalysisBudget;
};

export type AnalysisScope = {
  dataset_ids: Array<string>;
  time_range: TimeRange;
  filters?: Array<FilterIntent>;
};

export type AnalyticalTask = {
  task_id: string;
  analytical_question: string;
  analysis_type: string;
  priority: "required" | "recommended" | "optional";
  metric_ids?: Array<string>;
  measure_ids?: Array<string>;
  dimension_ids?: Array<string>;
  grain?: Array<string>;
  statistical_method_ids?: Array<string>;
  visualization_intents?: Array<string>;
  business_value: string;
  drop_conditions?: Array<string>;
};

export type AnalyticsToolResult = {
  schema_version?: string;
  object_id: string;
  created_at: string;
  content_hash: string;
  provenance: Provenance;
  request_id: string;
  task_ids: Array<string>;
  dataset_id: string;
  method_id: string;
  measure_column: string;
  partition_columns?: Array<string>;
  category_column?: string | null;
  time_column?: string | null;
  decision: string;
  result: StatisticalResult;
  reason: string;
};

export type AnswerSnapshot = {
  schema_version?: string;
  object_id: string;
  created_at: string;
  content_hash: string;
  provenance: Provenance;
  session_id: string;
  chronological_parent_answer_id?: string | null;
  analytical_base_answer_id?: string | null;
  turn_kind: TurnKind;
  status: AnswerStatus;
  semantic_package_version: string;
  metric_versions: Array<string>;
  analysis_plan?: AnalysisPlan | null;
  query_plan?: QueryPlan | null;
  dataset_bundle?: DatasetBundle | null;
  feature_summaries?: Array<FeatureSummary>;
  analytics_tool_results?: Array<AnalyticsToolResult>;
  dashboard_spec?: DashboardSpec | null;
  visualization_previews?: Array<VisualizationPreview>;
  claims?: Array<ClaimSpec>;
  overall_claim_ids?: Array<string>;
  kpi_selections?: Array<KpiSelectionDraft>;
  evidence_package?: EvidencePackage | null;
  limitations?: Array<string>;
  warnings?: Array<string>;
};

export type AnswerStatus = "ANSWERED" | "CLARIFICATION_REQUIRED" | "UNANSWERABLE" | "EMPTY" | "PARTIAL" | "FORBIDDEN" | "FAILED" | "CANCELLED";

export type BusinessEvidence = {
  scope: {
  [key: string]: JsonValue;
};
  metric_definitions?: Array<{
  [key: string]: JsonValue;
}>;
  data_tables?: Array<string>;
  reconciliations?: Array<{
  [key: string]: JsonValue;
}>;
  quality?: Array<{
  [key: string]: JsonValue;
}>;
  exploratory_analysis?: Array<{
  [key: string]: JsonValue;
}>;
  downloads?: Array<string>;
};

export type ChartAnalysis = {
  purpose: string;
  reading_guide: string;
  findings: Array<ChartFinding>;
  caveats?: Array<string>;
};

export type ChartEncoding = {
  x?: string | null;
  y?: string | null;
  category?: string | null;
  value?: string | null;
  color?: string | null;
  series?: string | null;
  tooltip_fields?: Array<string>;
};

export type ChartFinding = {
  claim_id: string;
  text: string;
  importance: "primary" | "secondary" | "supporting";
  evidence_row_ids: Array<string>;
};

export type ChatApiResponse = {
  status: string;
  session_id: string;
  turn_id: string;
  answer?: AnswerSnapshot | null;
};

export type ChatRequest = {
  session_id?: string | null;
  message: string;
  client_turn_id: string;
  mode?: "standard" | "debug";
};

export type ClaimSpec = {
  schema_version?: string;
  object_id: string;
  created_at: string;
  content_hash: string;
  provenance: Provenance;
  source_claim_id?: string | null;
  claim_type: string;
  text: string;
  importance: "primary" | "secondary" | "supporting";
  task_ids?: Array<string>;
  evidence_refs: Array<EvidenceRef>;
};

export type Clarification = {
  question: string;
  reason_code: string;
  allowed_answers?: Array<string>;
};

export type DashboardBlock = {
  block_id: string;
  type: "answer_summary" | "context_summary" | "kpi_group" | "chart" | "data_table" | "pivot_table" | "insight_list" | "warning" | "empty_state" | "clarification" | "follow_up_suggestions";
  title?: string | null;
  description?: string | null;
  dataset_id?: string | null;
  visualization_intent?: string | null;
  chart_type?: GovernedChartType | null;
  encoding?: ChartEncoding | null;
  sort?: Array<string>;
  stack?: boolean;
  axis_format?: {
  [key: string]: string;
};
  legend?: boolean;
  chart_analysis?: ChartAnalysis | null;
  evidence_refs?: Array<string>;
  kpis?: Array<KpiItem>;
  insights?: Array<string>;
  suggestions?: Array<string>;
  content?: {
  [key: string]: JsonValue;
};
};

export type DashboardSpec = {
  schema_version?: string;
  object_id: string;
  created_at: string;
  content_hash: string;
  provenance: Provenance;
  title: string;
  layout?: "auto_grid";
  blocks: Array<DashboardBlock>;
  warnings?: Array<string>;
};

export type DataQARecord = {
  rule_id: string;
  severity: "INFO" | "WARNING" | "ERROR" | "FATAL";
  passed: boolean;
  message: string;
  dataset_id?: string | null;
  metric_id?: string | null;
  evidence_row_ids?: Array<string>;
  details?: {
  [key: string]: JsonValue;
};
};

export type DatasetBundle = {
  schema_version?: string;
  object_id: string;
  created_at: string;
  content_hash: string;
  provenance: Provenance;
  datasets: Array<TabularDataset>;
  data_qa?: Array<DataQARecord>;
  reconciliation?: Array<ReconciliationRecord>;
  complete: boolean;
  warnings?: Array<string>;
};

export type DatasetColumn = {
  name: string;
  data_type: "string" | "integer" | "number" | "boolean" | "datetime" | "metric";
  nullable?: boolean;
  semantic_role: "dimension" | "measure" | "metric" | "metadata";
  field_id?: string | null;
  metric_id?: string | null;
  measure_id?: string | null;
  source_field_id?: string | null;
  aggregation?: string | null;
  aggregation_name?: string | null;
  aggregation_result_path?: string | null;
  aggregation_parameters?: {
  [key: string]: JsonValue;
};
  aggregation_semantics?: string | null;
  source_grain?: Array<string>;
  population_scope?: string | null;
  approximate?: boolean;
  unit?: string | null;
  display_name?: string | null;
  semantic_type?: string | null;
  business_domain?: string | null;
  security_classification?: "public" | "internal" | "confidential" | "restricted";
};

export type DatasetCompleteness = "COMPLETE" | "TOP_N_WITH_OTHERS" | "TRUNCATED" | "PARTIAL" | "UNKNOWN";

export type DatasetRow = {
  row_id: string;
  values: {
  [key: string]: JsonValue;
};
};

export type DatasetRowsResponse = {
  object_id: string;
  dataset_id: string;
  kind: string;
  grain: Array<string>;
  columns: Array<DatasetColumn>;
  rows: Array<DatasetRow>;
  offset: number;
  limit: number;
  total: number;
  complete: boolean;
  warnings: Array<string>;
};

export type EntityReference = {
  entity_id: string;
  mention: string;
  resolved_member_id?: string | null;
};

export type EvidencePackage = {
  schema_version?: string;
  object_id: string;
  created_at: string;
  content_hash: string;
  provenance: Provenance;
  business: BusinessEvidence;
  advanced: AdvancedEvidence;
  debug_ref?: string | null;
  redaction?: EvidenceRedaction;
};

export type EvidenceRedaction = {
  removed_fields?: Array<string>;
  masked_fields?: Array<string>;
  policy_id?: string | null;
};

export type EvidenceRef = {
  dataset_id: string;
  row_id: string;
  column: string;
  metric_id?: string | null;
  statistical_method_id?: string | null;
  statistical_result_hash?: string | null;
};

export type EvidenceView = {
  evidence_id: string;
  business: BusinessEvidence;
  advanced?: AdvancedEvidence | null;
  redaction: EvidenceRedaction;
};

export type FeatureSummary = {
  schema_version?: string;
  object_id: string;
  created_at: string;
  content_hash: string;
  provenance: Provenance;
  dataset_id: string;
  row_count: number;
  columns: Array<string>;
  task_ids?: Array<string>;
  grain?: Array<string>;
  completeness?: string | null;
  top_rows?: Array<{
  [key: string]: JsonValue;
}>;
  bottom_rows?: Array<{
  [key: string]: JsonValue;
}>;
  totals?: {
  [key: string]: JsonValue;
};
  ranges?: {
  [key: string]: JsonValue;
};
  time_features?: {
  [key: string]: JsonValue;
};
  statistical_results?: Array<StatisticalResult>;
  qa_summary?: {
  [key: string]: number;
};
  sample_rows?: Array<{
  [key: string]: JsonValue;
}>;
};

export type FilterIntent = {
  field_id: string;
  operator: "eq" | "in" | "range" | "exists" | "not";
  values?: Array<string | number | boolean>;
};

export type GovernedChartType = "bar" | "line" | "heatmap" | "stacked_bar" | "donut" | "dot" | "pareto" | "table" | "pivot";

export type HTTPValidationError = {
  detail?: Array<ValidationError>;
};

export type JsonScalar = string | number | boolean | null;

export type JsonValue = JsonScalar | Array<unknown> | Record<string, unknown>;

export type KpiItem = {
  kpi_id: string;
  label: string;
  value: JsonScalar;
  formatted_value: string;
  unit?: string | null;
  semantic_level: "certified" | "governed" | "operational" | "exploratory";
  quality?: "valid" | "insufficient_sample" | "not_applicable";
  definition: string;
  evidence_row_ids?: Array<string>;
};

export type KpiSelectionDraft = {
  selection_id: string;
  dataset_id: string;
  measure_column: string;
  task_ids: Array<string>;
  reason: string;
};

export type MeasureDecision = {
  measure_id: string;
  aggregation?: string | null;
  decision: "required" | "recommended" | "optional" | "rejected" | "downgraded";
  role: string;
  reason: string;
  confidence: number;
};

export type MetricDecision = {
  metric_id: string;
  decision: "required" | "recommended" | "optional" | "rejected" | "downgraded";
  role: string;
  reason: string;
  rejection_code?: string | null;
  required_capabilities?: Array<string>;
  confidence: number;
};

export type ParameterBinding = {
  parameter: string;
  source_dataset_contract: string;
  selection: "top_n" | "distinct" | "scalar";
  metric_id?: string | null;
  n?: number | null;
};

export type PresentationPreference = {
  requested_chart_type?: GovernedChartType | null;
  user_specified?: boolean;
  unsupported_chart_label?: string | null;
};

export type Provenance = {
  producer: string;
  source_ids?: Array<string>;
  source_hashes?: {
  [key: string]: string;
};
  metadata?: {
  [key: string]: JsonValue;
};
};

export type QueryFilter = {
  field_id: string;
  operator: "eq" | "in" | "range" | "exists" | "not";
  values?: Array<string | number | boolean>;
};

export type QueryPlan = {
  schema_version?: string;
  object_id: string;
  created_at: string;
  content_hash: string;
  provenance: Provenance;
  analysis_plan_id: string;
  steps: Array<QueryStep>;
  reuse_strategy?: "dataset_fingerprint";
  consolidation_notes?: Array<string>;
  total_estimated_buckets: number;
};

export type QueryStep = {
  step_id: string;
  purpose_task_ids: Array<string>;
  dataset_id: string;
  index_patterns: Array<string>;
  time_range: TimeRange;
  time_field_id: string;
  filters: Array<QueryFilter>;
  dimensions: Array<string>;
  measures: Array<string>;
  field_measures?: Array<AggregationSpec>;
  grain: Array<string>;
  result_contract_id: string;
  depends_on?: Array<string>;
  parameter_bindings?: Array<ParameterBinding>;
  estimated_buckets: number;
  timeout_ms?: number;
  required?: boolean;
};

export type ReconciliationRecord = {
  reconciliation_id: string;
  passed: boolean;
  expected: number | null;
  actual: number | null;
  tolerance?: number;
  message: string;
  dataset_ids: Array<string>;
};

export type SemanticCompileRequest = {
  profile?: string;
};

export type SemanticPackageResponse = {
  package_version: string;
  manifest_hash: string;
  field_count: number;
  metric_count: number;
  generated_at: string;
};

export type SessionContext = {
  schema_version?: string;
  object_id: string;
  created_at: string;
  content_hash: string;
  provenance: Provenance;
  subject_id: string;
  title: string;
  version: number;
  archived?: boolean;
  active_context?: ActiveAnalyticalContext;
  latest_answer_id?: string | null;
  updated_at: string;
};

export type SessionCreateRequest = {
  title?: string;
};

export type SessionDetailResponse = {
  session: SessionContext;
  answers: Array<AnswerSnapshot>;
};

export type SessionPatchRequest = {
  title: string;
  expected_version: number;
};

export type StatisticalResult = {
  result_id?: string | null;
  method_id: string;
  version: string;
  applicability: "APPLICABLE" | "NOT_APPLICABLE";
  sample_size: number;
  values?: {
  [key: string]: JsonValue;
};
  value_paths?: Array<string>;
  calculation_table_id?: string | null;
  warnings?: Array<string>;
  exploratory?: boolean;
};

export type TabularDataset = {
  schema_version?: string;
  object_id: string;
  created_at: string;
  content_hash: string;
  provenance: Provenance;
  dataset_id: string;
  contract_id: string;
  kind: "base" | "derived";
  grain: Array<string>;
  columns: Array<DatasetColumn>;
  rows: Array<DatasetRow>;
  completeness: DatasetCompleteness;
  complete: boolean;
  truncated: boolean;
  source_dataset_ids?: Array<string>;
  derivation_id?: string | null;
  warnings?: Array<string>;
};

export type TimeRange = {
  from_inclusive: string;
  to_exclusive: string;
  timezone: string;
};

export type TurnKind = "NEW_ANALYSIS" | "CLARIFICATION" | "FILTER_CHANGE" | "TIME_CHANGE" | "DIMENSION_CHANGE" | "PRESENTATION_CHANGE" | "EXPLANATION" | "NEW_TOPIC";

export type TurnResponse = {
  turn_id: string;
  session_id: string;
  client_turn_id: string;
  attempt: number;
  status: string;
  retryable: boolean;
  created_at: string;
  updated_at: string;
  error?: {
  [key: string]: JsonValue;
} | null;
};

export type ValidationError = {
  loc: Array<string | number>;
  msg: string;
  type: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
};

export type VisualProfile = {
  row_count: number;
  category_count: number;
  series_count: number;
  time_point_count: number;
  visible_columns: Array<string>;
  value_range?: {
  [key: string]: JsonScalar;
};
  representative_rows?: Array<{
  [key: string]: JsonValue;
}>;
};

export type VisualizationPreview = {
  schema_version?: string;
  object_id: string;
  created_at: string;
  content_hash: string;
  provenance: Provenance;
  candidate_id: string;
  task_ids: Array<string>;
  analytical_question: string;
  purpose: string;
  dataset_id: string;
  visualization_intent: string;
  decision: "ACCEPT" | "ACCEPT_WITH_TRANSFORM" | "DOWNGRADE_TO_TABLE" | "REJECT";
  renderer: "echarts_contract" | "table";
  chart_type?: string | null;
  encoding?: ChartEncoding | null;
  transforms?: Array<string>;
  reason: string;
  profile: VisualProfile;
  evidence_row_ids?: Array<string>;
};
