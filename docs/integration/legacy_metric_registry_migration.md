# 旧项目指标注册迁移：认证口径，而非分析上限

状态：2026-08-04 / MI-NEW 的内网必读执行说明。

## 结论

内网必须把旧项目中已被业务 Owner 确认的指标迁移到 `semantic-input/internal/metric_registry/`，再通过正式编译进入 `MetricDefinition`。这一步的目的，是让正式 KPI 的公式、分子、分母、排除项和版本可重算、可审计；它**不是**把 Agent C 的统计分析限制为这些指标。

系统中的三个层级不可混淆：

| 层级 | 谁选择 | 谁计算 | 能否显示为正式 KPI |
|---|---|---|---|
| L1 Certified Metric | Agent A/C2 从已注册版本中选择 | Metric Engine | 可以 |
| L2 Governed Derived Metric | Agent A/C2 从预批准公式中选择 | Metric Engine/Derivation | 可以，但必须标明受控派生 |
| L3 Exploratory Statistic | Agent C Pass 1 从 MethodDefinition 和真实数据列中选择 | GovernedAnalyticsTool / StatisticEngine | 不可以；Evidence 标记探索性 |
| L4 Unsupported Candidate | Agent 可说明不能算 | 不执行 | 不可以 |

因此，“LLM 像数据分析师一样决定分析指标/统计”表示它可以从已验证的 metric/measure 列选择统计对象、方法、图表和解释；不表示它可以现场发明失败率、去重口径或任意 Python 公式。

## 迁移步骤

1. 从旧项目导出每个业务指标的名称、版本、Owner、业务定义、公式、时间语义、粒度、状态映射、分子、分母、null/pending/unknown policy、最小样本、单位、精度和已知限制。
2. 逐项分类为 L1/L2/L3/L4。没有 Owner 确认的旧“指标”不得偷升为 L1；只能保留为 L2/L3/L4 或不导入。
3. 用当前 `MetricDefinition` AST 表示公式；禁止把 Excel 文本、SQL/PPL、Python、物理字段路径或字符串公式直接交给 LLM。
4. 将真实状态/枚举映射放入 `value_dictionaries/`；率指标的分子分母必须通过真实 status mapping 可重算。
5. 运行 `prepare-internal-input`、`compile-internal-semantic` 和 schema/import gate。包内 metric version 必须唯一、可执行且受 Policy 允许。
6. 用真实 Shadow 对每个 L1/L2 指标重算，至少核对值、分子、分母、excluded、minimum denominator、时区、近似标记和 Evidence row 定位；Owner 给出 verdict。
7. 更新 Golden，使真实 LLM 能选择指标但不能绕过 Metric Engine；不要复制 Mock 的 `message_record_count`/`failure_rate` 文案或状态值。

## Agent C 的统计工具如何工作

C1 不拿到可执行代码。它只能返回：

```text
dataset_id + measure_column + registered method_id + allowed parameters + task_ids + purpose
```

Host 对每个请求验证 Dataset/任务/QA/数值列/MethodDefinition/参数名/最低样本/语义能力，再调用 `StatisticEngine`。返回的 `AnalyticsToolResult` 包含 method version、sample size、值、warning、hash 与来源 Dataset。C2 只能在这些结果与图表 Preview 返回后引用 `statistic:<method_id>@<source_column>` selector 写 Claim；Grounder 再把它绑定到统计 hash 与源行。

扩展统计能力时应新增版本化 `MethodDefinition + StatisticalMethod` 实现和测试；不能让真实 LLM 输出公式、Pandas、Plotly 或 ECharts option。扩展业务 KPI 时应新增版本化 `MetricDefinition` 并完成 Owner 重算；不能把一次探索统计自动固化成 KPI。

## 验收问题

- [ ] 每个迁移的 L1/L2 都有 Owner、版本、公式 AST 和重算证据。
- [ ] 未确认的旧指标没有显示为 Certified KPI。
- [ ] C1 可对受治理的 numeric metric/measure 请求探索统计，不只对 L1 指标工作。
- [ ] C2 的 KPI 卡片来自其 `kpi_selections`，而不是 Agent A 或旧项目的默认列表。
- [ ] Evidence 区分正式指标计算与探索性统计；主 Dashboard 不展示技术口径大表。
- [ ] 真实 LLM/MCP/Shadow 成功后才允许把 internal 包发布为正式运行包。
