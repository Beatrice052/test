# Evidence 与对账

## 用户要核对的链条

```text
CompiledQuery / Query fingerprint
  → OpenSearch raw aggregation artifact
  → normalized Source Result Table
  → deterministic Metric / Rollup / Statistic tables
  → Metric / Measure / Method technical definition
  → Claim exact row/cell or statistic value path
```

## Evidence Drawer 六个区块

1. `Source Queries`：logical dataset、actual indices、time range/timezone、filters、dimensions/grain、Metric/Measure、plan/step/query IDs、fingerprint、execution/page/bucket/row/completeness，以及安全 query summary。
2. `OpenSearch Results`：完整 aggregation JSON 下载、normalized source table 的 100 行分页预览与完整 CSV 下载。raw artifact 保留所有实际查询到的 buckets，不因图表 Top-N 丢行。
3. `Calculated Tables`：Metric Engine、Rollup、贡献/排名/期间变化/趋势/异常和 Host statistic 的 source IDs、task IDs、grain、input/output、definition/version、参数、row/value paths、hash、complete/approximate。
4. `Metric & Method Definitions`：只展示本轮实际用到的 Metric/Measure/Method。正式指标包含可读 Formula AST、分子分母、源字段/字典、聚合语义、unit/precision、空值策略、minimum denominator、time semantics、approximate 和 Owner；字段度量和统计方法显示其各自参数、适用性与解释限制。
5. `Claim Trace`：每条最终 Claim 对应具体 table ID、artifact ID/hash、row ID、column 或 `result.values.*` path，以及 definition IDs。
6. `Important Limitations`：只显示 `VALID/WARNING/BLOCKED`、material warnings、blocked reasons、非完整/近似/低样本和 reconciliation 失败摘要。

## 为什么不展示逐条 QA pass/fail

逐条 `qa_rule_001: PASSED` 会淹没真正的数据与计算证据，且对业务核对没有增量价值。因此 `BusinessEvidence.quality` 固定为空，Drawer 不遍历它。删除的是用户展示，不是 QA：完整 `DataQARecord` 仍在 owner-scoped `AnswerSnapshot.dataset_bundle.data_qa`、后台审计/日志与启用后的 developer debug 路径。

Host 在进入 Agent C 和 Grounding 前执行门禁：ERROR/FATAL 数据不进入正式结论；FATAL/ERROR 阻断肯定 Claim；material warning 必须进入状态或 limitation。

## Artifact 生命周期与权限

- JSON artifact 写入 `APP_ARTIFACT_DIR/evidence/<server-generated-prefix>/...`；路径从不接受用户输入。
- AnswerSnapshot 保存引用和 hash。读取 `/api/v1/answers/{answer_id}/artifacts/{artifact_id}` 时先按 subject 查 Answer，再验证引用、size、JSON 和 SHA-256。
- Source/Calculation CSV 由 owner-scoped Dataset API 导出，CSV hash 对实际下载 bytes 计算；restricted/confidential export 再检查角色。
- Artifact 日志记录 ID/hash/size，不记录完整内容。备份、保留期和清理由内网存储策略确定；删除前必须确保 Answer 生命周期已结束。

## 人工核对一个答案

1. 在 Source Queries 确认索引、时间 `[from,to)`、timezone、filters、grain、fingerprint、page/completeness。
2. 下载 raw JSON，数 leaf buckets；确认 source table 行数/keys/doc_count/raw metric values 一一对应，CSV hash 与 ETag/Evidence 相同。
3. 对 Metric table 用 source rows 重算分子、分母和结果；对 Rollup 汇总 additive columns，确认 reconciliation expected=actual。平均值、比率、cardinality/percentile 等 non-additive 值不得直接求和。
4. 对 statistical artifact 用 MethodDefinition 参数和 input columns 复算 `result.values`，核对 calculation table/value paths。
5. 在 Claim Trace 找到每个数字、类别、排名或时间点的 row/cell/statistic path；确认 definition ID 存在于本轮技术口径。
6. 若 status 为 WARNING/BLOCKED，确认最终答案文字反映该限制；BLOCKED 不得有肯定结论。

## 对账失败处理

不要改前端数字或让 LLM“解释差异”。先按 lineage 定位 raw→source、source→metric、rollup 或 statistic 的第一处 hash/数值分叉；分类为 Mapping/数据变化、MetricDefinition 差异、timezone/completeness 修复或 implementation bug，并在修复后重新生成整个 AnswerSnapshot。
