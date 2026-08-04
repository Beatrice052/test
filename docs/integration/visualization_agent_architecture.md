# Agent C 双阶段可视化分析架构（当前权威实施说明）

版本：2026-08-04 / MI-NEW

本文是 `docs/baseline/` 唯一需求基线在当前代码中的可视化实施说明。若历史 Gate Report、旧审计或旧提示词仍写着“Agent C 一次输出 Claim 和候选图”，以本文、`AGENTS.md`、`INTERNAL_AI_START_HERE.md` 和当前 Contract 为准；历史报告只用于追溯，不能指导新开发。

跨 Agent 的统一决策边界见 [三 Agent 全流程决策权与验收矩阵](decision_authority_matrix.md)。

## 1. 结论

合理顺序不是“先固定生成几张图，再找一句结论匹配”，也不是“让 LLM 自由调用 Plotly/ECharts 并执行代码”。当前正式链路采用有界双阶段：

```text
已验证 DatasetBundle + FeatureSummary + AnalysisPlan
→ Agent C / Pass 1：提出动态统计工具请求和 1/N 个可视化探索候选
→ GovernedAnalyticsTool：在已验证数值列上执行版本化统计方法
→ GovernedVisualizationExplorer：校验 grain、基数、完整性、编码和安全目录
→ VisualizationPreview：返回最终编码、可行性、数据剖面和证据行
→ Agent C / Pass 2：综合完整特征、统计结果与 Preview，生成总洞察、KPI 选择、ClaimDraft + VisualInsightDraft
→ Grounding/Completeness：校验图、任务、Dataset、指标列和证据完全一致
→ DashboardBuilder → 声明式 DashboardSpec → 前端 Safe ECharts Adapter
```

Agent C 决定“哪些数值/统计方法值得分析、哪些关系值得探索、哪些发现重要、用哪一个通过验证的 Preview 解释发现”。程序决定“能否算、以哪个已版本化算法执行、图是否能画、如何安全编码、结论是否真的有证据”。

## 2. 为什么不让 Agent 自由使用绘图库

LLM 自由产生或执行 Python、JavaScript、Plotly spec、ECharts option 会破坏基线中的安全、审计和复现边界，也会让图表与 Dataset grain、指标口径或证据脱节。因此：

- Agent C 不能直接调用 MCP、OpenSearch、数据库或通用 Tool；
- Agent C 不能输出/执行 Python、JavaScript、HTML、Plotly spec 或 ECharts option；
- Adapter 只消费 Pydantic 白名单 Contract；
- 当前产品渲染器是前端 ECharts 安全 Adapter；Plotly 当前未实现、未启用；
- 若以后经 ADR 批准增加 Plotly，必须新增独立 Renderer Adapter、能力声明、同等安全校验和测试，不能修改 LLM 让它直出 Plotly 代码。

Agent C 拿到的“图”是 `VisualizationPreview` 的受控结构化预览：最终 chart type、encoding、transform、row/category/series/time-point 计数、值域、代表行和证据引用。分析结论来自完整 FeatureSummary、统计结果和 Grounded Claim，而不是对图片像素猜测。

## 3. 两个 Agent C operation

### 3.1 Pass 1：`post_query_visual_exploration`

输出 `VisualizationExplorationDraft`。它包含 `analytics_requests` 与 `VisualizationCandidate`，不是任意 Tool Call。

每个 `AnalyticsToolRequest` 必须只引用：一个已经存在的 Dataset、一个已验证 numeric metric/measure 列、一个 MethodDefinition 中的 `method_id`、受限参数和覆盖的 task ID。Host 拒绝公式、代码、查询、物理字段、未知方法或未知参数；所有结果（包括 NOT_APPLICABLE）可审计地返回 C2 和 Evidence。正式 KPI 公式仍只能来自 MetricDefinition，不能由 LLM 创建。

每个 `VisualizationCandidate` 必须包含：

- 唯一 `candidate_id`；
- 要回答的 `analytical_question` 和 `reason`；
- 实际 `task_ids`；
- 已存在的 `dataset_id`；
- 受治理 `intent`；
- 维度/指标角色和按优先级排列的候选图型。

图表数量没有固定默认值。对非空且 QA 可用的 ChatBI 结果，C1 必须选择 1/N 张诚实图；N 张必须分别回答不同问题。空结果或 QA 阻断才可以没有图并明确说明。程序不会在 C1 缺席时按 Dataset 形状补一张“默认图”，因为那会把分析判断退化为规则。普通问题不得固定四图，二维图、时间图或任何业务字段组合也不得写死。

### 3.2 Adapter：`GovernedVisualizationExplorer`

Adapter 对每个 Candidate 执行确定性检查并生成 `VisualizationPreview`：

- Candidate ID、Dataset、intent、column 是否存在且唯一；
- DataQA 是否阻断；
- measure 是否有变化；
- 时间点、类别基数、series 和完整性是否符合注册约束；
- encoding 是否覆盖 Dataset 完整 grain；
- encoding key 是否唯一，避免 SMS/EMAIL 等类别重复显示；
- 用户指定图型是否与数据关系兼容；
- 不兼容时是降级表格还是拒绝；
- 最终 encoding、transform、剖面与 evidence row IDs。

Adapter 不产生业务结论，不调用 LLM，不执行模型代码。

### 3.3 Pass 2：`post_query_insight_dashboard`

输入在 Pass 1 的所有治理输入之外增加 `analytics_tool_results` 与 `visualization_previews`，输出 `InsightDashboardDraft`：

- `ClaimDraft[]`：每条有唯一 `claim_id`、任务、selector 和列绑定；
- `VisualInsightDraft[]`：每条同时绑定一个 `preview_id` 和一个或多个本次 `claim_id`；
- `overall_claim_ids`：总分析使用的 grounded Claim；
- `kpi_selections`：C2 选择的、已有的整体标量 metric/measure；
- 完整总分析所需的 limitations、追问建议和非数值 lead。

这是“统计结果与图形结果都已返回后，再形成结论”的阶段。不是先画固定候选再按文字相似度匹配，也不允许 DashboardBuilder 猜测哪个结论属于哪个图。总分析不是把所有图结论串起来：它是 C2 对完整分析结果的整合；一个事实需要同时解释图和直接回答时可以引用同一 Grounded Claim，前端不另建重复“关键发现页”。

## 4. 强制一致性不变量

任何图进入 Dashboard 前必须全部满足：

1. preview 存在且不是 REJECT；
2. insight_id、preview 选择和 claim_id 无重复冲突；
3. Candidate task 与 Claim task 有交集，且没有未知 task；
4. Claim 的全部 EvidenceRef 与 Preview 使用同一个逻辑 Dataset；
5. Claim 至少绑定 Preview 最终 encoding 的 measure 列；
6. Claim 至少有一个且名称唯一的 binding，并已由 ClaimGrounder 落到真实 row/column 或唯一 statistical result；
7. 图必须至少有一条 material finding；
8. required task 必须由 grounded claim 覆盖或明确 limitation；
9. KPI selection 必须是可用的整体标量 Dataset 和受治理 numeric 列，不会由 Agent A 的指标列表自动补齐；
10. 不允许把相关性写成因果，不允许使用 QA 阻断数据；
11. 图数量、Dashboard block 数量必须在 AnalysisPlan budget 内。

校验失败最多进行两次有界 `json_repair`。Repair payload 只有错误码、原结构、允许的 task/dataset/column/preview ID 和 hash，不包含原始大表，也不能扩大权限或预算。仍失败则删除不可信图/Claim并返回 PARTIAL；绝不切换到 RuleBased Mock。

## 5. 每张图的用户解释

每个 Chart Block 都携带 `ChartAnalysis`：

- `purpose`：本图的业务分析目标；
- `findings`：Grounded 结论，带 claim/evidence row；
- `reading_guide`：由程序保留给 accessibility/测试，不作为机械用户文案；
- `caveats`：必要的样本、完整性、统计或解释边界。

前端展示为“图 → 图表解读（purpose、finding、必要时注意）”。不显示“本图回答”“如何阅读”或通用证据提示的重复模板。主页面不展示技术聚合明细、完整 QA 或 DSL；这些只在 Evidence Drawer 中。Business Evidence 依次提供 OpenSearch 受控聚合表、正式指标计算、AI 选择的统计分析及 QA/对账；Advanced Evidence 才在 ACL 下显示实际只读 DSL。

## 6. 用户指定图型与多轮追问

Agent A 是多轮和展示偏好的唯一正式语义权威：

- “把上一个结果改成柱状图”且逐任务数据签名不变：`PRESENTATION_CHANGE + reuse`，零 OpenSearch 查询；复用 Dataset、Evidence、FeatureSummary 和 grounded findings，重新执行 Agent C Pass 1，并由 Adapter 生成新的 Preview；
- 指定图型兼容：采用该安全类型并更新读图说明；
- 指定图型不兼容：保留业务结果表并说明原因，C1/C2 仍须选择另一张真实可行图；数据为空或 QA 阻断时才展示不可用状态；
- “按地区重新分析并改成热力图”：维度导致数据签名变化，必须 requery，不能当作纯换图；
- “为什么这个峰值最高”：`EXPLANATION + reuse`，零 OpenSearch 查询，但重新执行 Agent C Pass 2 并再次 Grounding，不是复制旧回答；
- 图型不在安全目录：记录 unsupported preference，按真实数据关系选安全图，不让 LLM 注入新 renderer。

Presentation reuse 不会生成新的业务结论，因为数据、任务和 grounded claim 都没有改变；它只用 Pass 1 重做展示探索并按 task/Dataset/measure 精确绑定既有 Claim。Explanation reuse 会用 Pass 2 基于已持久化的完整 FeatureSummary 生成新的解释。若用户要求新的比较、下钻、统计方法、指标或粒度，逐任务签名守卫必须强制 requery，不能把它伪装成换图/解释。

## 7. 安全图表目录不是固定业务模板

当前目录为 bar、line、heatmap、stacked_bar、donut、dot、pareto、table、pivot，并含 `single_value` 这个受治理单值视图。这是可扩展的安全能力白名单，不是 Agent 的固定答案表。真实 Agent C 根据问题、task、Dataset shape、FeatureSummary、统计结果和用户偏好动态选择；Registry/Validator 只负责拦截不可实现或误导性的组合。

增加新图型必须同时完成：Contract literal、VisualizationDefinition、Candidate shape、后端 Feasibility、renderer adapter、前端安全 option、读图说明、降级路径、单元/集成/E2E 和安全扫描。只改 Prompt 或在 Mock 中加关键词不算实现。

## 8. Mock 与真实 LLM

`RuleBasedMockLLMClient` 只是离线结构替身。它用规则模拟 A/B/C 两个 Pass，因此只能产生有限、机械的分析。正式环境必须为 `openai_compatible`；代码已禁止 mcp/prod 使用 rule_based、fixture 或 recorded。

内网不得复制以下任何 Mock 逻辑：关键词意图分类、图型别名、固定 Dataset 形态、`_insight_dashboard` 的 Claim 模板、候选图模板、Mock repair。真实模型应完整执行两个 Agent C operation；正式编排、Adapter、Grounding 和 Contract 保持不变。

真实 Agent C 验收不能只看 JSON 合法，必须检查：C1 动态统计请求、1/N 动态选图、图和 claim 五项一致性、总分析在 C2 统计/预览之后产生、动态 KPI、每图解释、非因果化、真实非固定维度、显式图型请求与不兼容降级。

## 9. 代码定位

| 责任 | 位置 |
|---|---|
| Agent C 两个 Pass 与 payload | `backend/app/agents/insight_dashboard.py` |
| Agent C Prompt | `backend/app/agents/prompts/insight_dashboard.md` |
| Candidate/Preview/ChartAnalysis Contract | `backend/app/contracts/dashboard.py` |
| Claim/VisualInsight Contract | `backend/app/contracts/insight.py` |
| 受控探索 Adapter | `backend/app/presentation/exploration.py` |
| Feasibility/ChartAnalysis/Dashboard | `backend/app/presentation/dashboard.py` |
| 两段编排与一致性校验 | `backend/app/orchestration/phase5_nodes.py` |
| Grounding | `backend/app/presentation/grounding.py` |
| 前端 ECharts 安全渲染 | `frontend/src/components/SafeChart.tsx`、`frontend/src/lib/safeChartOption.ts` |
| 每图解释 | `frontend/src/components/Dashboard.tsx` |
| Mock-only A/B/C 模拟 | `backend/app/llm/rule_based.py` |

## 10. 内网修改前的验收清单

- [ ] 两个 Agent C operation 都在真实 endpoint 的审计日志中出现；
- [ ] LLM request 没有 tools/tool_choice/MCP/DB handle；
- [ ] Pass 1 只输出 Candidate，不输出 Claim 或代码；
- [ ] Pass 2 只选择 Adapter 返回的 preview；
- [ ] 图与 Claim 的 task/dataset/measure/evidence 校验全部通过；
- [ ] 普通问题没有固定图数或固定维度；
- [ ] 每张图都有 purpose/findings，必要时有 caveat；主 UI 只显示简洁“图表解读”，不展示机械 reading guide；
- [ ] 纯换图零查询且重跑 Pass 1；解释追问零查询且重跑 Pass 2；新分析请求一定 requery；
- [ ] readiness 不是 rule_based/fixture/recorded；
- [ ] 真实 Shadow 和业务 Owner verdict 已通过。
