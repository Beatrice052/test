# LLM 决策边界深度审计

## 结论

正式链路不是规则引擎。`rule_based` 是无凭证、本地可重复测试使用的 Mock LLM Adapter；`mcp` 内网 profile 默认使用 `openai_compatible`，缺少 endpoint/model 时启动失败，不会静默退回 Mock。

系统遵循基线中的职责分离：AI 决定“分析什么以及为什么”，确定性程序保证“ID 是否受治理、查询是否安全、指标如何计算、图表是否误导、结论是否有证据”。因此 QueryPlan 由 LLM 规划，但最终 OpenSearch DSL 必须由程序编译，不能改成 LLM 直出。

## 权威边界

| 环节 | 决策权威 | 正式适配器 | Mock 行为 | 确定性保护 |
|---|---|---|---|---|
| 多轮关系与用户意图 | Agent A | `turn_and_analysis_plan` 严格 JSON Schema | Mock 内部规则模拟不同 turn kind | Session 继承边界、所有权、幂等校验 |
| 指标、维度、时间、分析任务 | Agent A | 同上 | 从候选摘要生成多种可重复计划 | 候选 ID allowlist、Policy、Answerability |
| 用户显式图表要求 | Agent A 的 `presentation_preference` | 同上 | Mock 内部别名解析 | 安全图表目录与 Dataset grain 校验 |
| 逻辑 QueryPlan、Dataset grain、依赖步骤 | Agent B | `logical_query_plan` 严格 JSON Schema | 根据实际 tasks/resolved IDs 生成 1 或多步计划 | Finalizer、Consolidator、预算、依赖和 ID 校验 |
| 最终 DSL | 不属于 LLM | 无 | 无 | Index Router + allowlisted AST/DSL Compiler + Validator |
| 正式指标与统计结果 | 不属于 LLM | 无 | 无 | Metric/Statistic Engine 按注册版本计算 |
| 洞察、图表候选与图表数量 | Agent C | `post_query_insight_dashboard` 严格 JSON Schema | 根据 AnalysisPlan、Dataset schema、FeatureSummary 生成不同候选 | Claim Grounding、Feasibility、Utility/Dedup、Dashboard budget |
| ECharts option | 不属于 LLM | 无 | 无 | 前端安全 Adapter，只接受闭合 DashboardSpec |

## 本次发现并修复的问题

1. 编排器曾在 Agent A 之前用关键词判断“展示变化/解释/重新查询”。现在编排器只生成非权威 provisional hint；所有允许请求都先调用 Agent A，再按其结构化 `turn_relation` 路由。
2. 用户显式说“热力图/折线图”等要求，曾由 Agent 外的字符串解析器直接决定。现在 Agent A 输出 `presentation_preference`；正式编排链不再解析自然语言图表别名。
3. Mock Agent C 曾为一个普通概览同时生成总趋势与多系列趋势，形成重复图。现在一个可读的多系列趋势会替代重复总趋势，图数由任务、数据粒度、系列数和可视化意图共同决定。
4. `time_trend` 的注册表曾禁止二维时间热力图，导致同一显式热力图请求只覆盖部分兼容 Dataset。注册表现允许时间×类别使用 heatmap/stacked bar，并仍由完整 grain 校验约束。
5. 失败原因此前只能退化为普通排名。现在注册了 Pareto intent 与受控 Pareto 渲染器；异常问题注册了 anomaly intent。
6. `backend-mcp` 曾可能默认 `rule_based`。现在默认 `openai_compatible`；`mcp` 与生产环境同时拒绝 `fixture`、`rule_based` 和 `recorded`。
7. 前端曾固定显示“Mock 数据已连接”。现在读取 readiness，直接显示当前 `llm_mode` 与 `gateway_mode`，避免内网接入后仍伪装成 Mock。

## 动态性回归矩阵

| 问题形态 | Mock 预期 | 验证目的 |
|---|---:|---|
| 普通消息运行概览 | 3 张不同问题的图 | 趋势、类别排名、状态构成；不重复总趋势 |
| 失败原因 | 1 张 Pareto | 按原因贡献选择图，不套 Channel 模板 |
| 显式要求表格 | 0 张图 | 用户展示要求进入 Agent A，并安全落为表格 |
| 显式要求热力图的概览 | 2 张 heatmap | 只保留时间×类别、类别×状态两个兼容二维关系 |
| 单维排名后要求热力图 | 0 张 heatmap，降级表格 | 不为满足图型伪造第二维 |
| Agent C 失败 | PARTIAL + 表格 + Evidence | 不用无证据的固定图填充 |

这些数量不是产品默认值，而是当前 Mock 数据和问题计划的测试断言。真实模式下，Agent A/C 的结构化输出可为 0、1 或多张候选；最终数量仍受预算、去重、完整性、基数和粒度校验限制。

## 内网接入条件

内网只需要提供获准 LLM endpoint/model/Secret，并执行 `probe-llm` 与 Shadow/Golden 校准。若端点不支持 strict JSON Schema，应修复 Adapter 兼容层，不能把 Agent Contract 改成自由文本，也不能用 `rule_based` 代替正式意图、QueryPlan 或 Dashboard 决策。
