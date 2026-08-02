# Phase 4 Gate Report — Result、Metric、Statistic 与 QA

- 日期：2026-08-01
- 结果：**PASSED**
- 唯一基线 SHA-256：`3762adc6ca42745151d01894c835f6d80c9dfb84a6e1ce9624e8b026ed85b6c6`
- Semantic Package：`sp_c882cd989899b08f`

## 1. 本阶段交付

- `RawResultParser` 校验 query 身份、shard 外层结构与聚合响应存在性，不展开业务 bucket。
- `DatasetContractFactory` 从 `CompiledQuery.semantics` 生成权威 Contract；Normalizer 只按 Contract 的 BucketPath 工作，不猜测业务粒度。
- 递归 Bucket Walker 覆盖 array/keyed/filter/date histogram、nested wrapper、missing/empty bucket、metric object 与 composite metadata；month→channel→status 不在外层提前丢失。
- `row_id` 只由 dataset ID、grain 与按 grain 排序的 key 生成；度量更新不改变逻辑行身份。
- terms 的 `sum_other_doc_count`、`doc_count_error_upper_bound`、显式 Others，以及 composite `after_key` 都进入 `DatasetCompleteness`；两页 composite 合并后才标记 complete。
- `StatusMetricDeriver` 保存 derivation ID、实现版本、输入/输出 grain/columns、公式引用、reconciliation 规则、source hash 与 content hash；相同输入可重放出相同 derived hash/object ID。
- `MetricEngine` 执行 Registry Formula AST；`failure_rate.v1` 不进入 DSL script，而是按 Value Dictionary 聚合 success/failure/pending/unknown/null。
- `StatisticEngine` 实现 rank、contribution 与 MAD robust z-score；小样本、零总数、MAD=0 或未注册方法返回 `NOT_APPLICABLE`，不抛系统失败。
- `DataQAEngine` 实现 shard、timeout、dimension、primary key、reconciliation、ratio、numerator、time range、terms completeness、unknown、small sample、mapping compatibility、derived reproducibility 规则及 INFO/WARNING/ERROR/FATAL 分级。
- `FeatureSummaryBuilder` 仅输出 bounded top/bottom/totals/ranges/time/statistics/QA/sample；任何未通过 FATAL QA 的数据都不能进入 Insight。
- `DatasetBundleBuilder` 汇总 Base/Derived Dataset、QA、Reconciliation、完整性与 warnings。
- Phase 4 已接入同一 StateGraph：Gateway 执行、依赖参数绑定、运行时 q2 编译、Analytics 与结构化 Gateway/QA 终态。
- 默认 Mock Gateway 从签入的扁平行 Fixture 按每个 `CompiledQuery.bucket_path` 渲染确定性聚合结果，并仍以 query fingerprint 注册和计数。

## 2. 指标与 QA 证据

Mock SMS 样例：DELIVERED=70、FAILED=20、PENDING=5、UNKNOWN=5。

- numerator（failure）=`20`
- denominator（success+failure）=`90`
- `failure_rate.v1=0.2222`
- excluded=`{"pending":5,"unknown":5}`
- message record count=`100`
- numerator/denominator/evidence row IDs/metric version 均保存在 MetricValue metadata。

边界断言：

- denominator=0 → `value=null`、`quality=INVALID`，绝不输出 0%。
- denominator=12 < minimum 30 → `INSUFFICIENT_SAMPLE`。
- ratio>1 或 numerator>denominator → FATAL，Feature Summary 被阻断。
- unknown/null → WARNING；小样本 → WARNING；不把统计 anomaly 写成故障结论。
- required shard failure → FATAL，Bundle 可审计但 `feature_summaries=()`。

## 3. 实际验证结果

| 检查 | 结果 |
|---|---:|
| Backend pytest | 150 passed / 0 failed / 0 skipped |
| Phase 4 analytics + graph 定向测试 | 17 passed |
| ruff check | passed |
| ruff format check | passed（142 files） |
| mypy | passed（110 source files） |
| 权威 Schema Snapshot | 39 matched / 0 diff |
| Mock semantic compile | PASSED / `sp_c882cd989899b08f` |

## 4. Gate 判定

| Phase 4 Gate | 证据 | 判定 |
|---|---|---:|
| month×channel 不丢 | 三层递归 month→channel→status 精确产生三行 | PASS |
| failure_rate numerator/denominator 正确 | Registry + Value Dictionary 的 20/90、0.2222 断言 | PASS |
| terms/composite completeness 正确 | truncated/Others/after_key/两页合并测试 | PASS |
| FATAL 数据不进入 Insight | ratio、numerator 与 shard FATAL 阻断测试 | PASS |
| Derived 可复现 | 双次派生 content hash/object ID 相等 + QA rule | PASS |

**Phase 4 Gate：PASSED。**

## 5. 下一阶段

进入 Phase 5：InsightDashboardAgent、Claim selector/grounder、chart feasibility、Dashboard Builder、Evidence Builder/Exporter 与 deterministic fallback。Agent C 只读取 FeatureSummary，不读取大表、raw result、物理 Mapping、DSL 或 Tool。
