# OpenSearch ChatBI 统一智能增强详细技术升级执行方案

> 文档定位：这是交给内网 AI 和开发人员继续实施的唯一升级方案文档。
> 当前状态：项目负责人确认内网已完成 I2，尚未开始 I3。
> 代码边界：外网 GitHub 分支不包含内网 I2，本次只更新并推送本方案文档，不修改外网业务代码。内网真实工程、I0～I2 交付报告和测试结果才是后续实施基线。
> 目标分支：`Beatrice052/test` 的 `MI_ChatBI`。
> 版本管理：后续直接维护本文档，不再并列维护“V3、V4”等多份升级方案；Git 历史作为版本记录。

---

## 1. 本次决策摘要

本次接受并正式采用以下核心升级：

1. 保留 `AnalysisPlan`，它只表达用户想分析什么，不包含 Tool，也不包含 DSL。
2. 在 `AnalysisPlan`、语义字段、指标定义、时间范围和允许 Index 均已确定后，允许 LLM 在**一次结构化调用**中同时生成：
   - `QueryPlan`；
   - 一条或多条 OpenSearch Query DSL；
   - 每条查询的 `ResultContract`。
3. LLM 生成的是**候选查询包**，不是执行授权。只有通过后端全部确定性校验后才能交给 Gateway。
4. 最终 Tool 仍由程序根据已校验查询的执行形态选择。LLM 不选择、不调用 MCP Tool。
5. `failure_rate.v1` 等指标的最终计算仍由 Metric Engine 完成。LLM 只负责生成取得计算所需数据的查询，不能改写指标公式。
6. 保留现有确定性 Query Builder，先作为：
   - shadow 对照基线；
   - 简单场景的受控 fallback；
   - Golden 测试 oracle。
   它不应与 LLM 路径长期演化成两套同等地位的主实现。
7. 不引入自由 Agent Tool Loop，不引入 PPL，不暴露 Generic OpenSearch API，不让 LLM直接执行查询。
8. 当前不需要为了这次升级引入 LangGraph。继续使用显式、可测试的 Python 编排即可。
9. 剩余实施不再拆成很多对外 Phase，只保留一个统一 I3；I3 内部按工作流连续完成，并在最终统一验收。
10. OpenSearch 官方 `QueryPlanningTool` 只作为技术参考，**当前方案不把它作为运行时依赖，也不假定它是现有 OpenSearch MCP Server 已暴露的 Tool**。本项目使用应用侧 `QueryGenerationAgent` 调用内网已批准 LLM，查询执行仍通过 `MCPOpenSearchGateway`。

一句话概括最终架构：

```text
LLM 负责理解和提出候选查询；
Semantic/Policy/Validator/Metric/Gateway 负责限制、证明和执行。
```

### 1.1 对原始升级方案的覆盖审计结论

不能把此前版本简单描述为“已经逐字包含原 V3 的全部内容”。此前统一文档覆盖了主要架构，但压缩或遗漏了若干可执行细节。本次已重新逐节审计原 V3，并将仍然有效的技术提升全部纳入本文。

处理结果分为四类：

```text
保留：原设计仍正确，继续执行；
增强：保留目标，但使用更严格或更贴合当前事实的实现；
替代：不再采用原实现形式，但同一能力由新设计覆盖；
延期：不是当前 I3 范围，明确记录且不得声称已完成。
```

原 V3 中以下内容已被最新业务事实纠正，而不是遗漏：

- “只有 2026 年 7 月单一 Index”改为“支持全部月度 Index，7 月只是默认范围”；
- `failure_rate.v1` 的判断字段由原文错误的 `statusCode` 改为已确认的 `status`；
- `statusCode` 保留给未来运营商码表和独立指标版本；
- 生产完整 Policy/RBAC 延期，但现有 blocked 字段和基础安全机制继续强制执行；
- 原八个实施 Phase 合并为一个统一 I3；
- `ToolHint` 从 LLM 输出中移除，以 `execution_shape` 和程序 `ToolSelector` 替代；
- QueryPlan、DSL、ResultContract 仍由一次 LLM 调用生成；
- 修复上限保留为可配置最多 2 次，默认 1 次；
- Insight 的事实 Claim 优先由程序构造，LLM 负责表达，安全性高于“LLM 自由生成 Claim 后再纠错”。

### 1.2 原 V3 逐项覆盖矩阵

| 原 V3 章节/能力 | 本文状态 | 当前落点或修订 |
|---|---|---|
| 0 执行协议、先审计后编码 | 保留 | 第 4、20、29、30 节 |
| 1 合并智能查询与多轮增强 | 保留 | 第 7、14、20 节；统一 I3 |
| 2 目标、非目标、冻结边界 | 增强 | 第 5、6、28 节；支持全部月份并纠正 status/statusCode |
| 3 单一 Orchestrator、统一状态机、终态 | 补全 | 第 7.3～7.5 节 |
| 4 LLM 与确定性程序边界 | 增强 | 第 1、2、7、10、13 节 |
| 5 模块清单 | 保留 | 第 21 节；以内网真实文件映射为准 |
| 6 统一 LLM Client | 保留 | 第 22 节；增加 structured output、预算与降级 |
| 7 Context Resolver、Turn Router、组合动作 | 补全 | 第 14.2～14.4 节 |
| 8 Intent 与 AnalysisPlan | 保留 | 第 7.1、14.4 节 |
| 9 AnalysisPlanPatch、PresentationPatch、不可变计划 | 增强 | 第 14.3 节；使用 typed discriminated union |
| 10 两阶段 Semantic Retrieval、Value Resolver、candidate_role | 保留 | 第 6.2、9.1、9.2 节 |
| 11 一次 QueryPlan+DSL、steps[]、ResultContract | 增强 | 第 8 节；移除 ToolHint，补固定 alias |
| 12 Validation、Repair、SemanticRepairGuard | 增强 | 第 10、11 节；V01～V10、默认 1 次/最多 2 次 |
| 13 Tool Router、Gateway、部分失败 | 补全 | 第 10.11、15.2、23 节 |
| 14 Normalizer、Metric、Data QA | 保留 | 第 13、15 节 |
| 15 Query Reuse | 保留 | 第 14.5 节 |
| 16 Insight、Claim、Grounding、ChartSpec | 增强 | 第 16 节；事实 Claim 程序优先 |
| 17 Session、不可变 Snapshot、TTL | 保留 | 第 14.1、15.3 节 |
| 18 Orchestrator 伪代码 | 补全 | 第 7.5 节 |
| 19 API 契约 | 增强 | 第 17 节；补 response_mode、ContextDelta |
| 20 Evidence 与审计 | 保留 | 第 17.3、26 节 |
| 21 前端体验与固定 Chart Adapter | 补全 | 第 18 节 |
| 22 Policy 顺序、Prompt Injection、降级 | 补全 | 第 6.4～6.6 节 |
| 23 集中配置 | 补全 | 第 22.1～22.2 节 |
| 24 工程结构 | 保留 | 第 21 节 |
| 25 八阶段计划 | 替代 | 第 20 节统一 I3 内部工作流 |
| 26 Unit/Golden/Security/Frontend 测试 | 增强 | 第 24 节；补完整 Conversation Golden 与手工验收 |
| 27 可观测性与质量指标 | 补全 | 第 26 节 |
| 28 发布门槛 | 增强 | 第 25 节；增加 LLM DSL 特有阻断项 |
| 29 Mock 到内网切换 | 增强 | 第 4、6、20、22、23 节 |
| 30 阶段报告模板 | 替代 | 不再产出大量 Phase Report；使用 checkpoint 测试记录和一份 I3 最终报告 |
| 31 Definition of Done | 增强 | 第 31 节 |
| 32 第一轮审计模板 | 保留 | 第 29、30 节 |
| 33 最终执行摘要 | 保留 | 第 1、7、31 节 |

因此，本文的目标不是逐字复制 V3，而是做到：

```text
所有仍有效的能力要求均有明确落点；
所有冲突内容均按最新确认修订；
所有延期内容均明确标记；
不存在“因为压缩文档而无意丢失”的技术提升。
```

---

## 2. 为什么现在采纳“一次生成 QueryPlan + DSL”

此前完全禁止 LLM 生成 QueryPlan/DSL 的方案过于保守。它能保证已覆盖场景稳定，但也把系统能力限制在人工模板已经预见的组合中，不符合“智能问数”的目标。

### 2.1 一次生成的真实收益

#### 2.1.1 QueryPlan 与 DSL 更容易保持一致

如果 QueryPlan 和 DSL 分两次 LLM 调用生成，第二次调用可能丢失或重新解释第一次的语义。一次返回同一个严格对象，可以让模型同时考虑：

- 指标；
- 分组；
- 过滤；
- 时间粒度；
- Top N；
- 排序；
- 多查询拆分；
- 聚合返回路径；
- ResultContract。

后端随后验证二者是否一致，比两个独立生成步骤更清楚。

#### 2.1.2 能覆盖模板没有穷举的合法组合

例如：

- Channel × 日期趋势 × Failure Rate；
- 两个 Channel 对比并按 Route 下钻；
- 多条件过滤后的 Top N；
- 同一问题中需要多个相互独立聚合；
- 用户对上一轮查询增加维度、过滤或时间粒度。

确定性 Builder 可以继续覆盖核心 Golden，但不必为每个合法组合手写分支。

#### 2.1.3 降低 LLM 调用延迟和语义漂移

在 AnalysisPlan 已确定后，用一次调用生成 QueryPlan 和 DSL，比“先生成 QueryPlan，再把它交给第二次 LLM 生成 DSL”更省调用，也更容易用同一份受限上下文。

#### 2.1.4 OpenSearch DSL 适合结构化约束

OpenSearch DSL 是 JSON 树。相比任意 SQL 字符串，它更容易进行：

- JSON Schema/Pydantic 校验；
- 节点白名单；
- 字段引用遍历；
- 深度和 bucket 数量限制；
- 禁止脚本、runtime mappings 和原始 `_source`；
- QueryPlan 与 DSL 的逐项一致性校验。

因此，允许 LLM 生成 DSL 并不等于允许它自由执行。

### 2.2 不能把“一次生成”误解成“一次调用后直接执行”

一次生成只减少模型调用次数，不减少后端控制层。必须明确：

```text
一次 LLM 生成
≠ 一步直接执行
≠ LLM 拥有 Tool 权限
≠ LLM 可以定义指标
≠ LLM 可以访问任意字段
```

正确流程是：

```text
冻结的 AnalysisPlan
→ 安全语义上下文
→ LLM 一次生成 QueryGenerationBundle
→ 结构校验
→ 语义校验
→ Mapping/字段能力校验
→ DSL AST 白名单校验
→ 跨层一致性校验
→ 成本校验
→ 可选 OpenSearch Validate Query
→ 程序选择 Tool
→ Gateway 执行
→ Metric Engine 计算
→ Data QA
```

---

## 3. 与 SQLBot 和代表性 Text2SQL 项目的对比

这里不是要把 SQL 系统直接复制成 OpenSearch 系统，而是提炼可靠的共同模式。

### 3.1 SQLBot

SQLBot 的公开实现表明：

- 使用表结构、术语、定制 Prompt、样例 SQL 和历史上下文增强生成；
- LLM 生成结构化 JSON，其中包含 SQL；
- 生成后解析真实 SQL，而不是信任模型声明的表名；
- 使用 `sqlglot` 提取实际表，并与允许表清单核对；
- 之后才执行 SQL；
- 支持行权限处理、图表和分析。

对本项目的启示：

1. 允许模型生成正式查询是合理的。
2. 生成前必须检索相关 schema、业务术语和高质量样例。
3. 生成后必须解析实际查询内容，不能相信 LLM 自报的字段或 Index。
4. 权限和执行边界必须由程序控制。
5. SQLBot 的表级校验对银行 ChatBI 仍然不够；本项目必须进一步做到字段、指标、时间、DSL 节点和成本级校验。

不直接照搬的内容：

- 不采用自由数据源选择；
- 不让 LLM 生成权限过滤；
- 不把执行错误无限回灌给模型；
- 不把模型返回的 Tool、表名或字段声明当成事实；
- 不让前端解析一大段 LLM HTML。

### 3.2 Vanna

Vanna 的核心经验是用以下内容做检索增强，再生成 SQL：

- DDL；
- 业务文档；
- 常用 SQL；
- question-SQL pairs；
- 已成功的工具使用记忆。

对本项目的启示：

- `field_catalog_enrich.csv` 不只是字段名单，而是生成质量的核心语义上下文；
- 应建设 question-DSL Golden 示例；
- 只检索当前问题相关的字段、指标和示例；
- 只有经过确认的成功查询才能进入可复用记忆；
- 用户问题相似不代表可以直接复用旧结果，仍需比较数据需求指纹。

### 3.3 WrenAI / Wren Engine

WrenAI 强调：仅知道数据库 schema 不足以回答业务问题，系统还必须知道业务模型、指标、关系和治理规则。

对本项目的启示：

- Mapping 只能说明物理字段存在和类型；
- Catalog/Metric Registry 才说明字段和指标在业务上是什么意思；
- LLM 不能仅凭 Mapping 猜测 `Failure Rate`；
- 指标公式、状态归一化、时间字段和可分组能力必须进入受控语义层；
- 真实 Catalog 是主语义来源，实时 Mapping 用于校验和 drift 检测，而不是与 Catalog 竞争成为第二份业务定义。

### 3.4 DB-GPT

DB-GPT 展示了更通用的 Agentic Data Assistant：模型可以规划、生成 SQL/代码、执行工具并生成报告。

对本项目的启示：

- 复杂数据分析可以采用“规划—执行—结果—总结”的分层结构；
- 工具执行应有沙箱、审计和权限控制；
- 但本 POC 的数据源和能力范围很明确，不需要引入通用 Agent、代码执行或自由 Tool Loop；
- 简单、显式的状态机更容易测试和审计。

### 3.5 PICARD

PICARD 的研究结论很重要：生成查询既要语义正确，也要语法/执行有效；对形式语言的生成需要约束。

本项目不一定能在模型逐 token 解码时实现 PICARD，但可以采用等价的工程思想：

- 优先使用模型供应商的 structured output / JSON Schema；
- 生成后进行严格 JSON 和 DSL 树校验；
- 拒绝未知节点和未知字段；
- 只把明确、局部、可修复的错误返回给模型；
- 修复后重新走全部校验。

### 3.6 OpenSearch 官方 QueryPlanningTool

#### 3.6.1 它是什么

OpenSearch 官方 `QueryPlanningTool` 是 **ML Commons / Agentic Search 的内置 Agent Tool**。它在 OpenSearch Agent 中注册，通过模型连接器调用 LLM，将自然语言问题转换成 OpenSearch Query DSL。

它支持：

- Mapping 上下文；
- Query Fields；
- Sample Document；
- 自定义 Prompt；
- Search Templates；
- LLM 生成 DSL；
- 生成失败后的 fallback。

这证明“LLM 生成 OpenSearch DSL”本身是合理技术路线。

#### 3.6.2 它是不是 OpenSearch MCP Tool

必须区分三个不同概念：

| 概念 | 运行位置 | 典型能力 |
|---|---|---|
| OpenSearch ML Commons Agent Tool | OpenSearch 集群内 Agent | `QueryPlanningTool`、`ListIndexTool`、`IndexMappingTool` 等 |
| OpenSearch MCP Server Tool | MCP Server 对外暴露给 MCP Client | 默认核心工具包括 `ListIndexTool`、`SearchIndexTool`、`IndexMappingTool`、`CountTool`、`MsearchTool` 等 |
| 本项目 Gateway 方法 | ChatBI 应用后端 | `list_indices/get_mapping/count/search/msearch` |

结论：

- `QueryPlanningTool` 首先是 OpenSearch 的 ML Commons Agent Tool；
- 它**不是现有 OpenSearch MCP Server 默认核心 Tool 清单中的必然成员**；
- OpenSearch 新版本允许注册或组合 MCP/Agent Tool，但只有在内网实际 `tools/list` 或 MCP 配置中明确出现，才能把它视为可调用 MCP Tool；
- “OpenSearch 文档里叫 Tool”不等于“你们当前 MCP 已经暴露它”；
- 本项目不得根据文档示例臆造它已经可用。

#### 3.6.3 当前方案有没有使用它

当前方案**没有把 `QueryPlanningTool` 作为运行时依赖**。

本文采用的是：

```text
ChatBI 应用侧 QueryGenerationAgent
→ 调用内网批准的真实 LLM
→ 一次生成 QueryPlan + DSL + ResultContract
→ ChatBI 自己执行 V01～V10 Validator
→ 程序 ToolSelector
→ MCPOpenSearchGateway
→ MCP SearchIndexTool/CountTool/MsearchTool
```

`QueryPlanningTool` 在本文中的作用是：

- 证明 OpenSearch 官方认可 LLM 生成 DSL 的技术路线；
- 参考其 Mapping、Query Fields、Search Templates 和 Prompt 设计；
- 不作为当前代码必须安装或调用的组件。

#### 3.6.4 为什么不直接把它作为主 Query Generator

它与本项目仍有明显合同差异：

1. 它主要生成 DSL，不生成完整 `AnalysisPlan → QueryPlan → ResultContract` 链；
2. 它不知道 `failure_rate.v1`、Metric Registry、OtherCount 和空分母规则；
3. 它不知道本项目的 Value Resolver、Session Patch、Query Reuse 和 Evidence；
4. 它的默认 Prompt 允许更宽的搜索节点和近似字段选择，不符合本项目 fail-closed 原则；
5. 其默认失败策略可能回退为 `match_all`，银行指标查询不能接受；
6. 它需要 OpenSearch 集群中的模型连接器、Agent 注册、插件版本和额外权限；
7. 它会把 LLM 编排耦合到 OpenSearch 集群，而内网已有批准的统一 LLM 调用方式；
8. 即使使用它，应用侧 Validator、Metric Engine、ResultContract 和 Tool/Gateway 边界仍然一个都不能少。

所以，直接接入不会减少核心工程，反而可能形成两套 LLM 调用和两套 Prompt。

#### 3.6.5 未来什么情况下可以评估

只有同时满足以下条件才做可选技术验证：

- 内网 OpenSearch 版本和 ML Commons 支持；
- 安全团队批准集群模型连接器；
- MCP `tools/list` 或 Agent 配置确认它真实可用；
- 能关闭宽泛 fallback；
- 能注入本项目最小语义上下文；
- 输出可被本项目 `QueryGenerationBundle` 包装；
- 所有输出仍通过同一个 V01～V10 Validator；
- 与应用侧 Query Generator 做 shadow 对比后有明确收益。

即使未来接入，推荐把它实现为另一个可插拔 `QueryGenerationProvider`：

```python
class QueryGenerationProvider(Protocol):
    async def generate(
        self,
        context: QueryGenerationContext,
    ) -> QueryGenerationBundle:
        ...


class InternalLLMQueryGenerationProvider: ...
class OpenSearchQueryPlanningProvider: ...  # 可选，不是当前默认
```

它不能直接替代 Gateway，也不能获得执行授权。

#### 3.6.6 需要吸收但不能照搬的内容

但本项目不能照搬其默认的宽松行为：

- 不允许生成失败后静默回退为 `match_all`；
- 不允许无关问题使用“最接近字段”勉强查询；
- 不允许直接返回原始 hits；
- 不允许脚本或未知 DSL 节点；
- 不允许绕过 Metric Registry；
- 不允许仅凭 Mapping 解释业务指标；
- 不允许模型控制 Tool 和 MCP 调用。

银行 ChatBI 必须采用 `fail-closed`：

```text
无法确定字段、指标、值、时间或合法查询结构
→ 澄清 / not_answerable / blocked
→ 不执行宽泛查询
```

### 3.7 对比结论

| 项目/方法 | 值得吸收 | 本项目需要加强或不采用 |
|---|---|---|
| SQLBot | LLM 生成正式查询、schema/RAG、样例、查询后解析和允许表校验 | 提升到字段/指标/DSL AST/成本校验；不复制自由权限改写 |
| Vanna | DDL、文档、question-query pairs、成功记忆 | 只保存经审核的 DSL；复用需数据需求指纹 |
| WrenAI | 业务语义层、受控指标和关系 | 以 Catalog + Metric Registry 为主，Mapping 只做物理校验 |
| DB-GPT | 规划、执行、报告的分层思想 | 不引入自由 Agent、代码沙箱和通用 Tool Loop |
| PICARD | 形式语言必须被约束和解析 | 用 structured output + 后置验证实现 |
| OpenSearch QueryPlanningTool | LLM + Mapping/Query Fields/模板生成 DSL | 只作参考；当前不作为 MCP 或运行时依赖；禁止宽松 `match_all` fallback |

---

## 4. 项目事实与权威资料顺序

内网 AI 不能把外网 GitHub 当作 I2 完成后的代码基线。

开始 I3 时按以下顺序判断事实：

1. 项目负责人在当前或最新 Session 的明确确认；
2. 内网真实代码、配置、Git 历史和当前分支；
3. 内网 I0、I1、I2 最终报告及测试记录；
4. 原始项目需求和已冻结业务口径；
5. 本升级方案；
6. 更早的外网代码和历史方案，仅作参考。

如果本方案中的文件名与内网 I2 实际文件不同：

- 不要为了对齐文档强行改名；
- 先形成“现有模块 → 目标职责”的映射；
- 在最小改动原则下复用已有实现。

外网分支的旧 `AGENTS.md`、`TECHNICAL_EXECUTION_SPEC.md` 或历史 Phase Prompt 如果仍写有：

```text
LLM 只能生成 AnalysisPlan，绝对不能生成 QueryPlan/DSL；
剩余工作必须继续拆成多个对外 Phase。
```

这两条已被项目负责人在最新 Session 中明确替代。当前批准口径是：

- LLM 可以在完整受控上下文下，一次生成候选
  `QueryPlan + DSL + ResultContract`；
- 候选必须通过 V01～V10，最终 Tool 和执行权仍属于程序；
- 剩余工作为一个统一 I3，内部使用 checkpoint，不再要求大量 Phase Report。

这不是放宽其他安全规则。`candidate_role` 隔离、blocked 字段、Gateway 边界、Metric
Engine、禁止 PPL/Generic API/自由 Tool Loop 等仍然有效。内网 I3 在首轮审计获确认后，
应把内网仓库的 `AGENTS.md`、README、项目记忆和执行提示同步到本方案，避免后续 AI 被
互相冲突的旧指令误导；该同步属于文档/工程治理 checkpoint，不得顺带覆盖内网 I2 代码。

如果内网实现与本文设计存在实质冲突，第一轮只读审计时必须列出，不得边猜边改。

---

## 5. 已冻结业务口径

### 5.1 数据范围

- 数据按月份拆分为多个 Index。
- `tbl_os_sub_message_2026_07` 只是示例和默认月份，不是唯一数据源。
- 当前可以查询全部月份的数据。
- 用户给出时间范围时，程序根据左闭右开区间选择覆盖月份的物理 Index。
- 用户未给时间范围时，POC 默认 2026 年 7 月完整月份，并在前端明确显示。
- 业务时区：`Asia/Hong_Kong`。
- 时间区间统一为 `[start_time, end_time)`。

### 5.2 记录数量

POC 的“记录数量”固定为 OpenSearch document count：

- 一条 document 等于一条记录；
- 不按 messageId 去重；
- Retry、重复 document、空字段 document 继续计数；
- 未来如需去重，新增独立指标版本，例如 `unique_message_count`。

### 5.3 Failure Rate

当前冻结：

```text
metric_id: failure_rate
version: failure_rate.v1

TotalCount
= 公共过滤条件下的全部 document 数量

TotalSuccessCount
= trim + upper 后的 status 属于 SENT 或 INPROGRESS 的数量

TotalFailedCount
= trim + upper 后的 status 属于 FAILED 或 ACKFAIL 的数量

OtherCount
= TotalCount - TotalSuccessCount - TotalFailedCount

FailureRate
= ROUND(100 × TotalFailedCount / TotalCount, 2)
```

附加约束：

- `TotalCount = 0` 时 `FailureRate = null`；
- 空 status 和未知 status 进入 `OtherCount`；
- 空 status 不得被展示逻辑转换成 `INPROGRESS` 后参与计算；
- Retry 和重复 document 继续进入分母；
- LLM 不得改变分子、分母和舍入规则；
- 回到真实报表对账后，如口径不同，新增指标版本，不静默修改 v1。

### 5.4 status 与 statusCode

- 当前 `failure_rate.v1` 使用 `status` 判断成功/失败。
- `statusCode` 是不同运营商返回的原始编码，不是当前 v1 的计算字段。
- 中国移动、中国电信、中国联通的独立失败率，需要后续补充：
  - carrier 字段；
  - statusCode 版本化码表；
  - 未知码策略；
  - 生效时间；
  - owner；
  - 对账样例。
- 资料未齐前不得让 LLM 猜测运营商编码含义。

---

## 6. Catalog、Mapping 与 Policy 的处理方式

### 6.1 Catalog 与 Mapping 不做重复建设

内网使用真实 `field_catalog_enrich.csv`。

如果该 CSV 已包含：

- 物理字段名；
- OpenSearch 类型；
- keyword/date 等能力；
- 业务名称和别名；
- 描述；
- 指标/维度角色；
- 可过滤/可聚合/可排序能力；
- 枚举或值域信息；

则不再人为维护第二份同内容的静态 Mapping 文件。

最终职责划分：

| 来源 | 职责 |
|---|---|
| `field_catalog_enrich.csv` | 权威业务语义、物理字段声明、检索文本、能力声明 |
| MCP 读取的实时 OpenSearch Mapping | 验证字段真实存在、类型/keyword/date/nested 能力、检测 drift |
| 测试 Mapping snapshot | 离线测试和回归，不作为生产业务定义 |
| Metric Registry | 指标 ID、版本、依赖字段、计算公式、结果契约 |

编译规则：

```text
Compiled Semantic Model
= Catalog 业务语义
+ 实时 Mapping 验证结果
+ Metric Registry
+ 当前基础安全限制
```

若 Catalog 与实时 Mapping 冲突：

- 字段缺失、类型不兼容、keyword 能力消失：fail-closed；
- 标记 drift；
- 不进入 LLM 可选字段；
- 不生成或执行 DSL；
- Evidence 仅显示安全的错误摘要。

### 6.2 candidate_role

`candidate_role` 必须彻底隔离：

- 不进入 Compiled Semantic Model；
- 不进入 hash；
- 不进入 Prompt；
- 不参与字段召回；
- 不进入 QueryPlan；
- 不进入 DSL；
- 不进入 Evidence。

### 6.3 Policy/RBAC

生产 Policy/RBAC 本轮暂缓，不作为 I3 POC 的阻塞项。

但不得因此移除已有基础安全机制：

- 已标记 blocked 的字段不得进入 Prompt、DSL、结果和 Evidence；
- 消息正文、客户姓名、手机号、邮箱、银行账号、客户标识等 Mock/基础禁止类别继续 fail-closed；
- Generic OpenSearch API 不得暴露；
- Gateway 只能执行允许的方法；
- 任何未分类字段不能因为 LLM 生成而自动放行。

文档和验收报告必须写成：

```text
POC 基础字段安全机制已实现；
生产 Policy/RBAC 尚待后续接入。
```

不得声称生产安全配置已经完成。

### 6.4 基础 Policy 的执行顺序

即使生产 RBAC 延期，基础 Policy 也必须贯穿每轮：

```text
Request Policy Gate
→ Context/Router 输入清理
→ AnalysisPlan Policy
→ Semantic Candidate Policy
→ Value Policy
→ QueryPlan/DSL Policy
→ Result Policy
→ Claim/Chart/Evidence Policy
```

纯换图或复用旧结果也不能跳过：

- 当前 Session 权限和有效性；
- Snapshot 是否安全、完整、未过期；
- PresentationPatch 是否包含脚本或任意配置；
- Evidence 是否仍符合清理规则。

### 6.5 Prompt Injection

用户文本、Catalog 描述、别名、值样例、历史摘要、OpenSearch 错误都视为不可信数据。

后端边界：

- 用户要求“忽略系统规则”不能改变 Schema、Policy 或 Metric；
- Catalog 中疑似指令文本只作为 quoted data；
- 不允许用户选择 Tool、Index、物理字段或 API path；
- 不泄露 Prompt、Mapping 全量、密钥或内部异常；
- LLM 只输出指定 Schema，业务模块不解析其中自然语言命令；
- Query Validator 只信任运行时 allowlist，不信任 Prompt 中的“已允许”声明；
- Prompt Injection 测试必须覆盖初次问题、追问、澄清值、图表标题和 Evidence。

### 6.6 统一降级矩阵

| 失败点 | 安全降级 |
|---|---|
| Router 超时 | 明确自包含问题走 Intent；依赖上下文且有歧义则澄清 |
| Intent LLM 超时/Schema 失败 | 返回有限规则澄清或可理解错误 |
| Semantic/Value 无法确定 | 澄清或 not_answerable，不选择“最接近值” |
| Query LLM 超时 | 已注册简单场景使用确定性 Builder；否则 error |
| Query Schema/Validator 失败 | 默认最多 1 次定向修复、配置最多 2 次；仍失败则 fail-closed |
| Mapping drift | 不执行，返回安全的能力不一致提示 |
| Gateway/MCP 失败 | 不生成结果，不把错误原样返回 |
| 多 step 必需步骤失败 | 整体不产出正式指标；不保存为可复用完整结果 |
| Metric 对账或恒等式失败 | 不展示正式指标 |
| Insight LLM 失败 | 确定性模板总结 |
| Grounding 失败 | 删除不可信 Claim；仍失败则模板回答 |
| Chart 不可行 | 降级为 Bar/Table/none，并解释原因 |
| Snapshot 过期或 partial | REQUERY |
| Evidence 清理失败 | 不返回调试 Evidence，记录安全错误码 |

任何降级都不得放宽字段、指标、时间、DSL 节点或查询成本限制。

---

## 7. 目标主流程

```text
用户问题
→ Session Context Loader
→ Turn Router
→ Intent Parser / AnalysisPlan
→ Clarification 或继续
→ Semantic Retriever（字段、指标、样例）
→ Value Resolver
→ Time Resolver + Index Resolver
→ Query Generation Context Builder
→ LLM 一次生成 QueryPlan + DSL + ResultContract
→ QueryGenerationValidator
→ 可选受限 Query Repair
→ Deterministic ToolSelector
→ OpenSearchGateway
→ NormalizedResult
→ Metric Engine
→ Data QA
→ Claim Builder / Grounding
→ Chart Planner
→ Summary Generator
→ 结构化 API Response + Evidence
→ 聊天页面渲染
```

### 7.1 仍然保留 AnalysisPlan

`AnalysisPlan` 是业务意图层，示例：

```json
{
  "analysis_type": "metric_by_dimension",
  "metrics": [
    {"metric_id": "failure_rate", "version": "failure_rate.v1"}
  ],
  "dimensions": ["channel"],
  "filters": [],
  "time_range": {
    "start": "2026-07-01T00:00:00+08:00",
    "end": "2026-08-01T00:00:00+08:00",
    "timezone": "Asia/Hong_Kong",
    "source": "explicit"
  },
  "sort": null,
  "top_n": null,
  "clarification": null
}
```

AnalysisPlan 不得包含：

- MCP Tool；
- Query DSL；
- 任意 API path；
- Prompt 原文；
- 敏感字段；
- 物理连接凭证。

### 7.2 QueryPlan 和 DSL 同次生成，但仍分层

“一次调用生成”不等于把两层揉成一个不可校验字符串。

LLM 必须返回：

```text
QueryGenerationBundle
├── analysis_plan_ref
├── query_plan
└── compiled_queries[]
    ├── query_id
    ├── index_scope_ref
    ├── request_body
    └── result_contract
```

`query_plan` 描述物理查询意图；`request_body` 才是 DSL。两者是同一响应中的兄弟对象，便于逐项校验。

### 7.3 单一 Orchestrator

项目只保留一个权威入口，例如：

```python
ChatBIOrchestrator.handle_chat()
```

以下操作全部通过同一个 `/api/chat` 主链：

- 新问题；
- 澄清答案；
- 增删改过滤；
- 改时间、指标、维度或粒度；
- 纯换图；
- 本地排序/limit；
- 解释请求；
- reset 后的新问题。

不得形成互相绕开的：

```text
/api/chat      → 完整安全链
/api/follow-up → 另一套简化链
/api/chart     → 前端直接从旧 DOM 换图
```

### 7.4 统一状态机与终态

```text
RECEIVED
→ POLICY_CHECKED
→ CONTEXT_RESOLVED
→ TURN_ROUTED
→ INTENT_RESOLVED | PLAN_PATCHED | NEEDS_CLARIFICATION
→ SEMANTICS_RESOLVED
→ REUSE_DECIDED
→ [QUERY_GENERATED → QUERY_VALIDATED → TOOL_SELECTED → QUERY_EXECUTED]
   或 [SAFE_RESULT_REUSED]
→ RESULT_NORMALIZED
→ METRICS_COMPUTED
→ DATA_QA_COMPLETED
→ CLAIMS_BUILT
→ RESPONSE_GROUNDED
→ CHART_VALIDATED
→ SNAPSHOT_SAVED
→ ANSWERED
```

终态：

```text
answered
needs_clarification
blocked
not_answerable
error
```

执行模式：

```text
new_query
requery
reused_result
clarification
blocked
not_answerable
error
```

复用可以跳过 Query Generation 和 Gateway，但不得跳过：

- 当前轮 Policy；
- Snapshot 完整性/TTL/版本；
- Metric 读取校验；
- Data QA；
- Grounding；
- Chart Feasibility；
- Response Assembly；
- 新 Evidence 和新 Snapshot。

### 7.5 Orchestrator 参考伪代码

```python
async def handle_chat(request: ChatRequest) -> ChatResponse:
    trace = trace_factory.create(request)
    policy_gate.check_request(request.message, trace)

    context = context_resolver.resolve(
        session_id=request.session_id,
        current_message=request.message,
    )
    turn = turn_router.route_or_default(request.message, context)

    if turn.reset_only:
        session_store.reset(request.session_id)
        return response_assembler.reset_acknowledgement(trace)

    if turn.reset_before_analysis:
        session_store.reset(request.session_id)
        context = context_resolver.empty(request.session_id)

    plan, presentation_patch = plan_flow.resolve(
        request=request,
        context=context,
        turn=turn,
    )
    if plan.needs_clarification:
        session_store.save_pending_clarification(request.session_id, plan)
        return response_assembler.clarification(plan, trace)

    validated_plan = analysis_plan_validator.validate(plan)
    policy_gate.check_plan(validated_plan, trace)

    semantics = semantic_pipeline.resolve(validated_plan)
    values = value_resolver.resolve(validated_plan, semantics)
    time_range = time_resolver.resolve(validated_plan.time_request)
    index_scope = index_resolver.resolve(time_range)
    policy_gate.check_resolved_context(semantics, values, index_scope, trace)

    reuse = query_reuse_decider.decide(
        previous=context.base_snapshot,
        plan=validated_plan,
        semantics=semantics,
        values=values,
        index_scope=index_scope,
        presentation_patch=presentation_patch,
    )
    if reuse.action == "CLARIFY":
        return response_assembler.reuse_clarification(reuse, trace)

    if reuse.action == "REQUERY":
        generation_context = query_context_builder.build(
            plan=validated_plan,
            semantics=semantics,
            values=values,
            time_range=time_range,
            index_scope=index_scope,
        )
        candidate_bundle = query_generator.generate(generation_context)
        query_bundle = query_validator.validate_or_repair(
            candidate=candidate_bundle,
            immutable_plan=validated_plan,
            generation_context=generation_context,
        )
        tool_decision = tool_selector.select(query_bundle)
        raw_result = gateway.execute(query_bundle, tool_decision, trace)
        normalized = result_normalizer.normalize(
            raw_result,
            query_bundle.compiled_queries,
        )
    else:
        query_bundle = context.base_snapshot.query_generation_bundle
        tool_decision = context.base_snapshot.tool_decision
        normalized = context.base_snapshot.normalized_result

    metrics = metric_engine.compute_or_read(
        normalized,
        validated_plan.metric_requests,
    )
    qa = data_qa.validate(normalized, metrics, query_bundle, reuse)

    claims = claim_builder.build(validated_plan, metrics, normalized, qa)
    summary = summary_generator.generate_from_claims(claims, qa)
    grounded = grounding_validator.validate_or_fallback(summary, claims, qa)
    chart = chart_planner.plan_and_validate(
        plan=validated_plan,
        result=normalized,
        metrics=metrics,
        patch=presentation_patch,
    )

    response = response_assembler.build(
        turn=turn,
        plan=validated_plan,
        query_bundle=query_bundle,
        tool_decision=tool_decision,
        result=normalized,
        metrics=metrics,
        qa=qa,
        content=grounded,
        chart=chart,
        reuse=reuse,
        trace=trace,
    )
    session_store.append_immutable_snapshot(
        request.session_id,
        snapshot_factory.from_response(response),
    )
    return response
```

内网必须适配真实 async 风格、异常模型和已有类名，不得机械复制。

---

## 8. QueryGenerationBundle 详细契约

建议使用 Pydantic v2，所有模型配置：

```python
model_config = ConfigDict(extra="forbid", frozen=True)
```

### 8.1 顶层结构

```json
{
  "schema_version": "query-generation.v1",
  "analysis_plan_ref": {
    "plan_id": "ap-...",
    "semantic_fingerprint": "sha256:..."
  },
  "query_plan": {},
  "compiled_queries": []
}
```

### 8.2 QueryPlan

建议字段：

```json
{
  "query_kind": "grouped_metric",
  "metric_requests": [
    {
      "metric_id": "failure_rate",
      "metric_version": "failure_rate.v1",
      "result_contract_id": "failure-rate-input.v1"
    }
  ],
  "dimensions": [
    {
      "semantic_id": "channel",
      "physical_field": "channel.keyword"
    }
  ],
  "filters": [
    {
      "semantic_id": "route",
      "physical_field": "route.keyword",
      "operator": "in",
      "values": ["ROUTE_A"]
    }
  ],
  "time_filter": {
    "semantic_id": "business_time",
    "physical_field": "createdTime",
    "start": "2026-06-30T16:00:00Z",
    "end": "2026-07-31T16:00:00Z",
    "boundary": "[start,end)"
  },
  "grouping": ["channel"],
  "sort": [
    {"field": "failure_rate", "direction": "desc"}
  ],
  "top_n": null,
  "execution_shape": "single_search",
  "expected_queries": 1
}
```

注意：

- `execution_shape` 只是查询形态，不是 Tool 名；
- 最终 ToolSelector 可校正或拒绝该形态；
- Index 名称由程序生成的 `IndexScope` 提供，LLM 只能引用 scope ID，不能创造 Index；
- `physical_field` 必须来自本轮安全上下文；
- 指标版本必须来自 Metric Registry。

### 8.3 CompiledQuery

```json
{
  "query_id": "q1",
  "index_scope_ref": "scope-2026-07",
  "purpose": "failure_rate_by_channel",
  "request_body": {
    "size": 0,
    "query": {
      "bool": {
        "filter": [
          {
            "range": {
              "createdTime": {
                "gte": "2026-06-30T16:00:00Z",
                "lt": "2026-07-31T16:00:00Z"
              }
            }
          }
        ]
      }
    },
    "aggs": {
      "by_channel": {
        "terms": {
          "field": "channel.keyword",
          "size": 50
        },
        "aggs": {
          "by_raw_status": {
            "terms": {
              "field": "status.keyword",
              "size": 100,
              "missing": "__MISSING__"
            }
          }
        }
      }
    }
  },
  "result_contract": {
    "contract_id": "failure-rate-input.v1",
    "grain": ["channel"],
    "paths": {
      "groups": "aggregations.by_channel.buckets",
      "group_key": "key",
      "total_count": "doc_count",
      "raw_status_buckets": "by_raw_status.buckets"
    },
    "metric_engine": {
      "metric_id": "failure_rate",
      "metric_version": "failure_rate.v1"
    }
  }
}
```

字段名只是结构示例，内网必须以真实 Catalog 和 Mapping 为准。

### 8.4 为什么 ResultContract 必须与 DSL 同时生成

DSL 可能执行成功，但系统不知道如何可靠解析聚合结果。ResultContract 用来明确：

- 返回粒度；
- bucket 路径；
- key 路径；
- 原始计数路径；
- 哪个 Metric Engine 消费；
- 空结果和截断检测方式。

Validator 必须证明 ResultContract 中的每条路径在 DSL 结构中有对应定义；执行后 Result Parser 再证明实际响应符合该契约。

### 8.5 统一 execution steps

`compiled_queries[]` 就是原 V3 `execution.steps[]` 的收敛形式。即使多数问题只有一个查询，也保留列表，因为需要表达：

- Msearch 的多个独立子查询；
- 对比期；
- 多指标但不能安全合并的查询；
- 每个 step 的 purpose、contract、状态和 query hash；
- 部分失败判断。

建议补充：

```json
{
  "execution": {
    "mode": "single_search",
    "required_query_ids": ["q1"],
    "optional_query_ids": [],
    "queries": ["q1"]
  }
}
```

当前 POC 原则上只允许：

- 单查询；
- 多个相互独立、可由 `MsearchTool` 执行的查询。

不开放 LLM 自主生成依赖查询链。未来若增加依赖关系，必须：

- 显式 `depends_on`；
- 验证 DAG 无环；
- 限制最大层数；
- 禁止把前一步任意原始值注入下一步 DSL；
- 定义必需/可选 step；
- 增加部分失败和成本测试。

### 8.6 固定 aggregation alias

聚合名称不能由 LLM 任意创造。建立版本化 `AggregationAliasRegistry`，例如：

```text
group_by_dimension
time_buckets
status_distribution
total_count
success_count
failed_count
other_count
metric_value
top_buckets
```

规则：

- Query Generation Context 只提供当前 ResultContract 允许的 alias；
- LLM 必须使用这些 alias；
- Validator 拒绝未声明 alias；
- ResultContract 只能引用 Registry 中 alias；
- alias 变更必须升级 contract/schema 版本；
- Normalizer 不依赖 Prompt 或自然语言 purpose 猜测聚合路径；
- 同一 alias 在同一 contract 中语义唯一。

---

## 9. LLM Query Generation Context

LLM 不得看到整个 Catalog、整个 Mapping 或任意历史。

一次生成调用只接收：

```text
1. 冻结 AnalysisPlan；
2. 与本问题相关的安全字段；
3. 字段物理类型和允许能力；
4. Metric Registry 中所需指标定义和查询输入契约；
5. Value Resolver 已确认的规范值；
6. 程序确定的 TimeRange；
7. 程序确定的 IndexScope ID 与能力交集；
8. 允许的 DSL 节点；
9. 查询成本限制；
10. 检索到的少量已审核 question-DSL examples；
11. QueryGenerationBundle JSON Schema；
12. 当前 semantic/model/mapping/config 版本。
```

不得进入 Prompt：

- blocked 字段；
- `candidate_role`；
- 连接字符串和凭证；
- MCP Tool 列表；
- Generic API 描述；
- 全量原始 Mapping；
- 原始 hits；
- 未清理的历史 Evidence；
- 用户不可见字段；
- 未确认的 statusCode 码表。

### 9.1 两阶段语义检索

#### 阶段 A：Intent Pre-retrieval

依据用户问题和 AnalysisPlan 召回：

- 候选指标；
- 候选维度；
- 候选过滤字段；
- 时间字段；
- 相关业务术语；
- 相关 Golden 查询样例。

#### 阶段 B：Dependency Expansion

根据已选指标补齐：

- 指标依赖字段；
- keyword/date 子字段；
- Metric Engine 输入；
- ResultContract 模板；
- 允许聚合能力；
- 空值/未知值处理。

只把第二阶段得到的最小闭包交给 Query Generator。

### 9.2 Value Resolver

Value Resolver 必须先于 DSL 生成：

```text
用户值
→ 规范化
→ Catalog 枚举/别名匹配
→ 可选受限 value lookup
→ canonical value
→ Query Context
```

LLM 不得自行创造：

- Channel；
- Route；
- status；
- carrier；
- Index；
- statusCode 含义。

值无法确定时：

- 高置信度歧义：澄清；
- 明确不存在：not_answerable；
- 不允许用模糊 wildcard 偷偷扩大查询。

---

## 10. QueryGenerationValidator

这是采用 LLM DSL 的核心。没有它，不允许上线 guarded 模式。

### 10.1 校验顺序

校验必须按固定顺序执行：

```text
V01 JSON/Schema
→ V02 AnalysisPlan 引用与 fingerprint
→ V03 Metric/Dimension/Filter 语义
→ V04 物理字段与 Mapping 能力
→ V05 Time/IndexScope
→ V06 DSL 节点和字段遍历
→ V07 QueryPlan ↔ DSL ↔ ResultContract 一致性
→ V08 成本与结果规模
→ V09 可选 OpenSearch Validate Query
→ V10 Tool compatibility
```

任何一步失败，后续不得执行。

### 10.2 V01：JSON 和 Schema

- 必须是单一 JSON 对象；
- 不接受 Markdown code fence；
- 不从自然语言中“尽量提取”一段 JSON 后直接执行；
- `schema_version` 必须支持；
- 所有对象 `extra="forbid"`；
- 枚举严格校验；
- 数字范围严格校验；
- `compiled_queries` 数量不得超过配置；
- DSL 深度不得超过配置。

### 10.3 V02：AnalysisPlan 引用

生成前对冻结 AnalysisPlan 计算：

```text
semantic_fingerprint
= hash(
  metric_id/version
  + dimensions
  + filters
  + time_range
  + sort
  + top_n
)
```

生成结果必须带同一 fingerprint。

修复前后 fingerprint 也必须一致。否则属于语义漂移，直接拒绝。

### 10.4 V03：语义校验

- metric_id/version 必须存在；
- dimension/filter semantic_id 必须来自已选上下文；
- QueryPlan 不得增加 AnalysisPlan 未要求的业务过滤；
- QueryPlan 不得丢失 AnalysisPlan 已确认的过滤；
- Top N、排序、趋势粒度必须一致；
- `failure_rate.v1` 必须引用 v1 的 ResultContract；
- `statusCode` 不得替代 `status`。

### 10.5 V04：字段和 Mapping

递归遍历 QueryPlan、DSL 和 ResultContract 中全部字段：

- 每个字段必须在本轮 allowlist；
- 每个字段必须存在于实时 Mapping 能力交集；
- terms/grouping 必须使用 aggregatable 字段；
- range/date_histogram 必须使用兼容类型；
- text 精确过滤必须使用确认过的 keyword 子字段；
- nested 仅在 Mapping 明确为 nested 时允许；
- 不允许通过字符串拼接逃逸字段路径；
- 多月 Index 间字段能力不一致时 fail-closed 或缩小 IndexScope 并明确提示，不能静默忽略月份。

### 10.6 V05：时间和 Index

- DSL 必须包含已冻结时间范围；
- 起止时间必须与 Time Resolver 的 UTC 边界完全一致；
- 必须使用 `gte` + `lt`；
- DSL 不得使用新的 `now` 重新解释已冻结时间；
- LLM 不能生成 Index 名；
- `index_scope_ref` 必须来自程序；
- Gateway 使用程序解析出的 Index 列表，而不是模型文本；
- 跨月只允许相同数据族的 Index，不做跨业务 Index join。

### 10.7 V06：DSL 节点白名单

POC 建议允许的查询节点：

- `bool.filter`；
- `term`；
- `terms`；
- `range`；
- `exists`。

LLM 生成路径默认不允许 `match_all`。本项目每个业务查询都必须带已解析的时间范围，
因此即使是“总记录数”也应使用时间 `range`。未来若出现经过批准的真正无范围全量统计，
只能由程序根据明确 AnalysisPlan 生成规范查询，并单独做成本与权限评审。

按需允许的聚合：

- `terms`；
- `date_histogram`；
- `filter` / `filters`；
- `sum`、`avg`、`min`、`max`、`value_count`、`cardinality`，仅限 Metric Registry 允许的字段；
- `bucket_sort`，仅限 Top N 且受大小限制。

默认禁止：

- `script`；
- `script_score`；
- `runtime_mappings`；
- `query_string`；
- `simple_query_string`；
- `regexp`；
- `wildcard`；
- `fuzzy`；
- `percolate`；
- `more_like_this`；
- `neural` / k-NN；
- `terms_lookup`；
- arbitrary pipeline aggregations；
- `profile`；
- `explain`；
- raw `_source`；
- stored script；
- 任意未列入白名单的节点。

未来需要开放新节点时：

1. 增加正式用例；
2. 增加节点校验器；
3. 增加成本限制；
4. 增加安全和 Golden 测试；
5. 配置版本递增。

不得只修改 Prompt。

### 10.8 V07：跨层一致性

至少验证：

- QueryPlan 的每个 filter 都能在 DSL 中找到等价、同值、同字段的 filter；
- DSL 不得出现 QueryPlan 未声明的业务 filter；
- QueryPlan 的 grouping 与 DSL 聚合层级一致；
- Top N 和排序一致；
- 聚合查询 `size = 0`；
- 每个指标都有 ResultContract；
- ResultContract 的聚合路径在 DSL 中存在；
- DSL 引用字段集合是 QueryPlan 字段集合的子集；
- 每个查询都能映射到一个明确 purpose；
- 多查询之间没有重复或冲突时间范围；
- 指标输入能被 Metric Engine 确定性消费。

### 10.9 V08：成本限制

集中配置：

- 最大时间跨度；
- 最大 Index 数；
- 最大 DSL 深度；
- 最大 bool clause 数；
- 最大 terms size；
- 最大 date_histogram buckets；
- 最大聚合层数；
- 最大查询数；
- 最大返回行数；
- 最大 timeout；
- `track_total_hits` 策略；
- msearch 最大子请求数。

估算 buckets：

```text
estimated_buckets
= product(each grouping size or estimated cardinality)
```

超过门槛：

- 缩短时间、减少维度或降低 Top N 的建议；
- 返回澄清；
- 不让模型自行取消限制。

### 10.10 V09：OpenSearch Validate Query

如果真实 MCP/Gateway 能提供 Validate Query 能力，可在执行前增加：

- 指定实际 Index；
- `lenient=false`；
- 必要时 `all_shards=true`；
- 记录安全清理后的 validation 摘要。

注意：

- Validate Query 主要验证 query 部分；
- 它不能替代聚合结构、指标语义、字段权限和成本校验；
- 如果 MCP 没有该能力，不应绕过 Gateway 直接调用通用 API；
- 本地结构 validator 仍然是必需项。

### 10.11 V10：Tool compatibility

程序根据最终已验证内容选择：

| 已验证查询形态 | Tool |
|---|---|
| 仅 document count，无分组/趋势/Top N/聚合 | `CountTool` |
| 单个过滤、分组、趋势、Top N 或聚合请求 | `SearchIndexTool` |
| 多个相互独立查询 | `MsearchTool` |
| 任意通用 API | 禁止 |

LLM 输出中不包含 Tool 名。即使出现未知 Tool 字段，也会因 `extra="forbid"` 被拒绝。

`ListIndexTool` 和 `IndexMappingTool` 属于**生成前的元数据发现能力**，不是业务查询执行选择：

```text
IndexResolver 需要刷新 Index 清单
→ 程序调用 ListIndexTool

Semantic Compiler/Drift Detector 需要 Mapping
→ 程序调用 IndexMappingTool

IndexScope 和 Mapping 能力确定
→ 才允许构造 QueryGenerationContext
```

如果 Index 尚未确定或 Mapping 缺失，不得先让 LLM 生成 DSL 再补信息。

### 10.12 多查询与部分失败

每个 query 记录：

```text
query_id
required/optional
status
tool
index_scope_ref
query_hash
latency
bucket/row count
error_category
```

规则：

- 任一 required query 失败：不计算正式指标；
- required query 返回 partial shard：默认整体失败，除非该指标有明确允许 partial 的版本化规则；
- optional query 失败：可保留主结果，但必须产生 warning，且 Claim 不得依赖失败部分；
- partial/truncated 结果不得标为 `complete=true`；
- 不把 partial snapshot 用于后续 REUSE；
- 不允许 LLM 根据部分结果“补齐”缺失值；
- Msearch 每个 item 独立解析错误，不能只看整体 HTTP 成功；
- Evidence 只展示错误类别和安全摘要。

---

## 11. 受限 Query Repair

可以保留最多一次默认、最多两次可配置的修复，但必须是严格受限的。

### 11.1 可修复错误

- JSON Schema 的局部格式错误；
- 使用了已检索字段的错误 keyword 子字段；
- 合法 DSL 节点参数类型错误；
- ResultContract 路径与聚合名不一致；
- terms/date_histogram 参数超出配置但可以缩小；
- OpenSearch 返回的非权限类、非业务语义类解析错误。

### 11.2 不可修复错误

- blocked 字段；
- 未知字段；
- 未知指标；
- 指标版本不一致；
- `statusCode` 代替 `status`；
- 未解析值；
- 时间范围歧义；
- IndexScope 越界；
- Policy 拒绝；
- 用户问题本身需要澄清；
- 语义 fingerprint 变化；
- 需要放宽 DSL 白名单；
- 需要增加数据访问权限。

这些错误直接返回 `blocked`、`not_answerable` 或 `needs_clarification`。

### 11.3 Repair Prompt

只提供：

- 原 QueryGenerationBundle；
- 结构化错误码；
- 错误 JSON Pointer；
- 允许修改的节点路径；
- 原 semantic fingerprint；
- 原最小安全上下文。

不提供：

- 原始 OpenSearch 错误堆栈；
- 凭证；
- blocked 字段名；
- 全量 Mapping；
- 扩大的 Tool 列表。

修复后重新从 V01 开始走完整校验。

---

## 12. Fallback 与渐进启用

### 12.1 禁止宽泛查询 fallback

不得采用：

```json
{"query": {"match_all": {}}}
```

作为任意生成失败时的默认 fallback。

这会把“模型不知道怎么查”变成“查询所有数据”，既可能误导，也可能扩大数据访问和计算成本。

### 12.2 确定性 Builder 的用途

保留已有 Builder，但只用于已注册的简单场景：

- document count；
- 按单一维度计数；
- 单维度 Failure Rate；
- 单一每日趋势；
- 单维度 Top N。

fallback 前提：

- AnalysisPlan 完整；
- 场景在确定性支持矩阵中；
- 不涉及未知字段/值/策略；
- 使用同一 Metric Registry、Time Resolver、IndexScope 和 Validator；
- Evidence 明确记录 `fallback_used=true` 和原因。

### 12.3 三种运行模式

配置：

```text
QUERY_GENERATION_MODE
= deterministic | shadow | guarded | primary
```

#### deterministic

只执行当前 Builder。用于紧急回退。

#### shadow

- LLM 生成 QueryPlan + DSL；
- 完成全部校验；
- 不执行 LLM DSL；
- 仍执行确定性 Builder；
- 比较语义、字段、DSL、结果契约和潜在成本；
- 不向用户暴露未经验证的 shadow 输出。

#### guarded

- 优先执行通过全部校验的 LLM DSL；
- 仅对已注册简单场景使用确定性 fallback；
- 无 fallback 时 fail-closed；
- I3 的推荐验收模式。

#### primary

- LLM 受控生成成为主路径；
- 确定性 Builder 仅用于紧急回退和测试 oracle；
- 只有达到发布门槛后启用。

### 12.4 不长期维护双主路径

完成 shadow/guarded 评估后：

- 新复杂组合优先由受控 LLM 生成覆盖；
- 确定性 Builder 不继续无限扩张；
- 核心指标 Golden 可以继续有确定性模板；
- 所有路径共享相同 Validator、Gateway、Metric Engine 和 Data QA。

---

## 13. Failure Rate 的查询与计算

### 13.1 LLM 不能在 DSL 中计算最终比例

LLM 可以生成取得以下输入的聚合：

- 每个目标粒度的 parent `doc_count`；
- 原始 status buckets；
- 缺失 status 的可识别计数。

Metric Engine 负责：

```python
normalized = raw_status.strip().upper()

success = normalized in {"SENT", "INPROGRESS"}
failed = normalized in {"FAILED", "ACKFAIL"}

other_count = total_count - success_count - failed_count
failure_rate = (
    None
    if total_count == 0
    else round(100 * failed_count / total_count, 2)
)
```

### 13.2 推荐聚合策略

如果真实 Mapping 有可聚合的 raw `status` keyword 字段：

- 外层按 Channel/Route/Date 分组；
- 内层按 raw status 分桶；
- Metric Engine 对 bucket key 做 trim + upper；
- parent `doc_count` 作为 TotalCount；
- 未出现在 status terms 中的数量通过 parent count 差额进入 OtherCount；
- 检查 `sum_other_doc_count`，不能静默丢失状态。

这样无需脚本，也不会把空值变成 `INPROGRESS`。

如果 status 不能安全聚合：

- 不允许 LLM 用 script 临时补救；
- 返回 mapping/capability 不满足；
- 由内网补充 normalized 字段或确定性数据处理方案；
- 完成后新增 Catalog/Mapping/Metric 配置并回归。

### 13.3 运营商 Failure Rate

后续新增独立指标，例如：

```text
carrier_failure_rate
carrier_failure_rate.v1
```

必须依赖：

- carrier 字段；
- carrier-specific statusCode rule set；
- 码表版本；
- 规则生效区间；
- unknown code 处理；
- 对账样例。

不得修改 `failure_rate.v1` 来偷偷承载运营商逻辑。

---

## 14. Session、多轮澄清和 Query Reuse

### 14.1 Session 只保存完成分析所需状态

建议：

```text
SessionState
├── session_id
├── recent_messages
├── pending_clarification
├── last_analysis_plan
├── last_query_generation_bundle
├── last_analysis_snapshot
├── last_data_requirement_fingerprint
├── created_at
├── last_access_at
└── version
```

要求：

- TTL；
- 最大 session 数；
- 每个 session 最大消息数；
- reset；
- 并发更新保护；
- 不把全部历史无限放入 Prompt。

### 14.2 Turn Router

先使用确定性规则识别：

- 新问题；
- 澄清回答；
- 对上一轮修改过滤；
- 修改维度；
- 修改时间；
- 修改 Top N/排序；
- 请求换图；
- 请求解释；
- 请求沿用上一轮数据。

无法可靠判断时，使用受限 LLM Router 返回严格 `TurnDecision`。

Context Resolver 只提供：

```text
current_message
pending_clarification
active_answer_id
最近有效 AnalysisSnapshot 的安全摘要
必要的 ContextDelta
```

不得向 Router 提供原始 document、全量 DSL、全量 Catalog 或无关历史。

`TurnDecision` 至少表达：

```text
turn_relation:
  new_analysis
  clarification_response
  continue_previous
  reset_context

operations[]:
  answer_clarification
  add/replace/remove_filter
  change_time_range
  change_dimension
  change_metric
  add_comparison
  drill_down
  change_chart
  change_presentation
  local_sort
  local_limit
  explanation_request
```

Router 不输出：

- `query_required` 权威值；
- 完整 AnalysisPlan；
- 物理字段；
- DSL；
- Tool；
- Session 修改指令；
- 任意图表代码。

#### 一个追问包含多个动作

用户：

```text
只看 SMS 和 Email，改成横向柱状图并显示数值。
```

必须同时保留：

```text
AddFilter(channel, ["SMS", "Email"])
ChangeChart(bar)
ChangePresentation(horizontal, show_data_labels=true)
```

过滤值仍需 Value Resolver。因为过滤改变，Query Reuse Decider 选择 REQUERY；新查询结果再应用展示 Patch。不得只执行最后一个“显示数值”动作。

路由优化：

- 无有效历史的新 Session 直接进入 Intent；
- pending clarification 先做允许选项的确定性匹配；
- 完整自包含新问题不得因 Session 存在而继承旧过滤；
- 明确 reset 由程序识别；
- reset + 新问题先清空，再把可追溯的 `effective_message` 交给 Intent；
- 低置信度且错误继承会改变数据口径时必须澄清。

### 14.3 Typed Patch

多轮修改使用 typed discriminated union，例如：

```text
SetTimeRange
AddFilter
RemoveFilter
ReplaceDimension
SetTopN
SetSort
ChangeChart
RequestExplanation
```

不允许任意 `path + Any value` 修改 AnalysisPlan。

Patch 分为：

```text
AnalysisPlanPatch   # 改数据需求
PresentationPatch  # 只改展示
```

应用顺序：

```text
读取不可变 base plan
→ 校验 base_plan_id/answer_id
→ 复制新计划
→ 应用 typed patch
→ Semantic/Value/Time/Policy 校验
→ 生成新 plan_id 和 parent_plan_id
→ 生成 ContextDelta
```

不得原地修改旧计划，不得部分应用危险 Patch。

`PresentationPatch` 只能包含声明式字段：

- chart type；
- orientation；
- data labels；
- legend；
- table only；
- 本地 sort/limit。

不得包含 ECharts option、formatter、HTML、CSS 或 JavaScript。

### 14.4 Clarification

例：

```text
用户：看看最近的失败情况。
系统：你希望按 Channel、Route 还是日期趋势查看？时间范围是否沿用当前默认月份？
用户：按 Channel。
```

第二轮必须：

- 识别为 pending clarification 的回答；
- 合并到上一轮未完成 AnalysisPlan；
- 保留已经明确的部分；
- 不把“按 Channel”当成新问题。

### 14.5 DataRequirementFingerprint

用于判断能否复用上一轮安全结果：

```text
fingerprint
= metric versions
+ dimensions/grain
+ canonical filters
+ time range
+ semantic model version
+ mapping fingerprint
+ metric config version
+ basic policy version
+ index scope
+ result contract version
+ query-affecting top_n
```

只有完全相同的数据需求，且上一轮 snapshot 未过期，才能复用查询结果。

以下在旧结果包含所需字段和粒度时通常不需要重查：

- 柱状图横竖方向变化；
- 显示/隐藏数值标签；
- 在同一类别粒度的 Bar/Table 间切换；
- 用另一种措辞总结；
- 展开 Evidence；
- 解释某个已存在 KPI。

以下必须重查：

- 改时间；
- 改过滤；
- 改维度；
- 改指标版本；
- Top N 需要更多数据；
- Mapping/Catalog/Metric 版本变化；
- 上一轮结果不含所需粒度。

需要 CLARIFY：

- “换成折线图”但现有结果没有时间粒度；
- “再细一点”无法确定下钻维度；
- “和之前比”比较对象不清；
- 用户问“为什么最高”但当前数据没有诊断维度；
- 历史引用或 base answer 不明确。

### 14.6 ContextDelta

每轮生成：

```json
{
  "inherited": ["metric: document_count", "time: 2026-07"],
  "added": ["filter: channel in SMS, Email"],
  "changed": ["chart: vertical_bar -> horizontal_bar"],
  "removed": []
}
```

ContextDelta 用于：

- 用户看到本轮继承和修改；
- Evidence；
- Grounding；
- 测试新问题是否误继承；
- 解释为什么 REUSE/REQUERY。

它由程序比较不可变计划生成，不由 LLM 自报。

---

## 15. NormalizedResult、Data QA 与不可变 Snapshot

### 15.1 NormalizedResult

所有 Gateway 原始响应先转成受控结构：

```text
NormalizedResult
├── query_id
├── grain
├── columns
├── rows
├── totals
├── metric_inputs
├── source_summary
├── truncation
├── shard_status
├── warnings
└── contract_validation
```

LLM 不直接看到原始 OpenSearch response。

### 15.2 Data QA

至少检查：

- timeout；
- shard failure；
- partial results；
- terms `sum_other_doc_count`；
- bucket truncation；
- parent count 与子 bucket 合计关系；
- Failure Rate 的 `success + failed + other = total`；
- TotalCount 为零；
- 多 Index Mapping drift；
- ResultContract 路径缺失；
- 非有限数；
- Top N 排序；
- 日期 bucket 连续性；
- 空结果。

空结果：

```text
当前条件下没有数据
```

不得生成空图或编造趋势。

### 15.3 AnalysisSnapshot

查询和指标完成后生成不可变 snapshot：

```text
AnalysisSnapshot
├── answer_id
├── parent_answer_id
├── analysis_plan
├── query_generation_bundle
├── tool_decision
├── normalized_result
├── metric_result
├── qa_result
├── chart_spec
├── result_contracts
├── query_hashes
├── context_delta
├── semantic/model/mapping/metric/policy/prompt/schema/config versions
├── data_requirement_fingerprint
├── partial/failed_queries/warnings
├── created_at
└── expires_at
```

后续总结、图表、换图和 Evidence 都从 snapshot 派生，不能各自重新计算指标。

每次成功回答创建新 `answer_id`。纯换图可以沿用旧 query hash 和 NormalizedResult，但仍创建：

- 新 Snapshot；
- 新 ChartSpec；
- 新 Evidence；
- `parent_answer_id`；
- 独立的 ContextDelta。

Snapshot：

- 只保存安全聚合，不保存敏感原始 document；
- Session 间不能共享；
- expired/partial/truncated 不复用；
- reset 后不能继续作为 active context；
- 容量超限按集中策略淘汰；
- 不以自然语言 summary 作为数据源。

---

## 16. Claim、Grounding 与图表

### 16.1 Claim Builder

先由程序从 MetricResult 生成结构化 claims：

```json
{
  "claim_id": "claim-1",
  "type": "ranking",
  "subject": "SMS",
  "metric_id": "failure_rate",
  "metric_version": "failure_rate.v1",
  "value": 12.34,
  "unit": "percent",
  "evidence_refs": ["row:0"],
  "allowed_phrasing": ["最高", "为 12.34%"]
}
```

Claim Builder 是确定性组件，不由 LLM 决定事实。至少支持：

- `metric_value`：某范围内的指标值；
- `comparison`：两个已存在结果之间的高低或差值；
- `ranking`：经过明确排序后的 Top/Bottom；
- `trend`：只有点数、时间顺序和趋势判定规则满足条件时才生成；
- `data_quality`：空结果、未知状态、partial、truncated 等事实；
- `scope`：时间、Index、过滤条件和分组口径。

每个 claim 必须能通过 `evidence_refs` 回指 `MetricResult`、`NormalizedResult`
或 QA 结果；不能仅回指 LLM 自己生成的文字。

LLM Summary 的输入应当最小化为：

```text
用户问题（已清理）
+ 已确认 AnalysisPlan 摘要
+ deterministic claims
+ warnings
+ 可公开的 scope/metric definitions
+ 输出语言和长度约束
```

LLM Summary 不能直接扫描任意原始 hits 后自由推断，也不能生成新的数值、排名、原因或
业务事实。若 LLM Summary 不可用，可由程序模板直接把 claims 渲染为安全答案，不影响
指标、表格、图表和 Evidence 返回。

### 16.2 Grounding Validator

验证：

- 总结中的数值是否来自 claim；
- 百分比、计数、日期单位是否一致；
- 排名是否与排序结果一致；
- 没有把相关性写成因果；
- 没有把 OtherCount 写成失败；
- 没有引用 blocked/raw 数据；
- 空结果没有生成结论；
- warning 被保留。

Grounding Validator 失败时不应重新查询，也不能放宽证据要求。处理顺序为：

```text
丢弃不受支持的句子
→ 尝试一次受约束 summary repair（可选）
→ 再次 grounding
→ 仍失败则使用 deterministic summary
```

用户可见 follow-up questions 也必须由当前结果能力约束。程序先产生可操作候选，例如
“按 Route 查看”“切换到每日趋势”“增加 Channel 过滤”，再允许 LLM 做自然语言润色。
不得推荐会访问 blocked 字段、尚未开放指标、未知 Index 或当前结果无法支持的分析。

### 16.3 Chart Planner

优先确定性选择：

| 结果形态 | 图表 |
|---|---|
| 单 KPI | KPI card |
| 日期趋势 | line |
| 维度对比 | bar |
| Top N | horizontal bar |
| 明细/多列 | table |
| 空结果 | 不生成图 |

LLM 可提出 `ChartIntent`，但程序必须验证：

- 字段存在；
- x/y 数值类型正确；
- 粒度一致；
- 不重新计算指标；
- 图例可见；
- 数据量不超限；
- 标题只描述所绘内容。

第一版不强制 Pie、Scatter。只有真实场景和数据形态需要时再开放。

后端最终输出统一 `ChartSpec`，而不是 ECharts 原生 option：

```json
{
  "type": "bar",
  "title": "Failure Rate by Channel",
  "x_field": "channel",
  "y_fields": ["failure_rate"],
  "series_field": null,
  "unit": "percent",
  "sort": {"field": "failure_rate", "direction": "desc"},
  "data": []
}
```

图表请求分为两类：

- `presentation_only`：当前 Snapshot 已包含所需字段、粒度和完整数据，只重建
  `ChartSpec`，不重新查询；
- `data_required`：需要新的分组、粒度、指标、过滤、时间范围或 Top N，必须先形成
  AnalysisPlanPatch 并重新查询。

若用户要求的图表与当前结果不相容，返回澄清或解释为什么需要重查；不得把缺失列补成
零、改变聚合粒度或用前端二次计算伪造图表。

---

## 17. API 与 Evidence

### 17.1 API 保持兼容

至少保持：

```text
GET  /
POST /api/chat
POST /api/session/reset
GET  /api/health
```

请求：

```json
{
  "session_id": "session-001",
  "message": "2026年7月各Channel的Failure Rate是多少？"
}
```

状态：

```text
answered
needs_clarification
blocked
not_answerable
error
```

### 17.2 响应建议新增但不破坏已有字段

```json
{
  "session_id": "session-001",
  "answer_id": "answer-002",
  "parent_answer_id": "answer-001",
  "status": "answered",
  "response_mode": "query",
  "data_reused": false,
  "assistant_message": "2026年7月各Channel的失败率如下。",
  "needs_clarification": false,
  "clarification_question": null,
  "clarification_options": [],
  "follow_up_questions": [],
  "active_context": {
    "metric_id": "failure_rate",
    "time_range": {
      "start": "2026-07-01T00:00:00+08:00",
      "end": "2026-08-01T00:00:00+08:00"
    },
    "group_by": ["channel"]
  },
  "context_delta": {},
  "kpis": [],
  "table": {"columns": [], "rows": []},
  "chart": {},
  "warnings": [],
  "evidence": {
    "analysis_plan": {},
    "query_plan": {},
    "query_generation": {
      "mode": "guarded",
      "llm_generated": true,
      "validated": true,
      "repair_count": 0,
      "fallback_used": false
    },
    "tool": "SearchIndexTool",
    "tool_reason": "Validated query contains grouped aggregations.",
    "query_dsl": {},
    "result_contract": {},
    "metric_id": "failure_rate",
    "metric_version": "failure_rate.v1",
    "versions": {},
    "qa": {}
  }
}
```

兼容原则：

- 现有必需字段不删除、不改类型；
- 新字段先定义为可选，前端按 capability 渐进展示；
- `response_mode` 至少支持 `query`、`reuse`、`clarification`、`blocked`、
  `not_answerable`；
- `data_reused=true` 时 Evidence 必须包含来源 Snapshot/answer ID；
- `context_delta` 只记录本轮明确继承、增加、替换、删除的分析条件；
- `clarification_options` 是可选快捷项，不能替代可自由输入的澄清；
- `assistant_message` 是展示文本，不得成为前端结构化渲染的数据源。

### 17.3 Evidence 清理

Evidence 默认折叠，只显示经过清理的：

- AnalysisPlan；
- 最终字段；
- QueryPlan；
- LLM query generation 模式；
- validation 摘要和错误码；
- repair 次数；
- fallback 标志；
- Tool 和程序选择原因；
- Query DSL；
- ResultContract；
- 原始聚合结果摘要；
- Metric ID/version；
- QA warnings；
- 关键版本 fingerprint。

不得显示：

- system prompt；
- chain-of-thought；
- 凭证；
- MCP 原始错误堆栈；
- blocked 字段；
- 敏感值；
- 未清理原始 hits；
- 全量 Mapping/Catalog。

---

## 18. 前端保持简单单体

继续使用：

```text
Python + FastAPI + Jinja2 + HTML + CSS + Vanilla JavaScript + 本地 ECharts
```

职责：

- FastAPI：页面路由、API、依赖注入；
- Jinja2：仅渲染初始 HTML 骨架；
- JavaScript：聊天、请求、loading、session、结构化组件渲染；
- ECharts：只渲染后端提供的数据；
- Metric Engine：唯一指标计算位置。

前端不得：

- 根据 DSL 自己计算 Failure Rate；
- 解析 LLM 生成的 HTML/JavaScript；
- 用另一套公式计算图表；
- 显示未清理 Evidence；
- 硬编码 Mock 或真实查询结果。

I3 重点是后端智能生成和可信链路，前端只做兼容性增强：

- 展示 query generation mode；
- 展示 validation/fallback 标志；
- 继续支持多轮澄清；
- Evidence 折叠；
- 空结果、blocked、not_answerable、error 状态；
- 不增加 Node 构建流程。

页面继续保留并验收以下完整结构：

1. 顶部信息栏：项目名、Mock/Connected、当前 IndexScope、默认时间范围、Semantic
   Model 版本；
2. 聊天记录区：用户消息、澄清、回答、blocked/not_answerable/error；
3. 输入区：多行输入、Enter、Shift+Enter、Send、Clear、示例问题、loading 和重复
   提交保护；
4. 回答组件：summary、KPI、table、chart、metric definition、warnings、Evidence；
5. 澄清快捷选项和安全的 follow-up questions；
6. Evidence 默认折叠；
7. 页面刷新前会话保留，reset 后清除 active context。

前端使用固定 Chart Adapter：

```text
后端 ChartSpec
→ schema/type/column existence 校验
→ 允许的 bar/line/horizontal-bar/table adapter
→ 本地 ECharts option
```

禁止直接执行服务端返回的 JavaScript、`eval()`、动态 formatter 函数或未经白名单的
ECharts option。所有 vendor 资源继续放在本地 `static/vendor`，不得依赖外部 CDN。

---

## 19. 是否使用 LangGraph

当前不建议引入 LangGraph，原因不是它不能实现，而是当前流程：

- 节点固定；
- Tool 选择固定；
- 无自由 Tool Loop；
- 不需要长时间分布式 checkpoint；
- 现有 Python 编排已经可测试；
- 内网 I2 已完成，引入框架会扩大改动面。

推荐：

```text
显式 Orchestrator
+ typed state
+ typed node result
+ 明确 transition
+ trace
+ timeout/retry policy
```

只有后续出现以下需求时再评估 LangGraph：

- 多 Agent 并行；
- 可暂停/恢复的长任务；
- 人工审批节点；
- 大量条件分支；
- 持久化 checkpoint；
- 多数据源复杂协同。

LLM 一次生成 QueryPlan+DSL 并不要求 LangGraph。

---

## 20. 内网 I3 实施方式

只保留一个统一 I3，不再要求每个小步骤都开新 Session 或形成独立 Phase Report。

### 20.1 两个对外确认点

```text
确认点 A：首轮只读审计与实施映射
→ 连续开发、checkpoint commit、自动化测试
→ 确认点 B：统一 I3 最终验收
```

只有以下情况中途停止：

- 内网实际代码与 I2 报告严重不一致；
- 需要改变已冻结业务口径；
- 真实 Catalog 无法支持目标字段；
- MCP 缺少必需的只读能力；
- 需要扩大数据访问或生产权限；
- 需要开放新的高风险 DSL 节点；
- 现有 API 必须做破坏性变更。

### 20.2 工作流 A：审计与合同冻结

目标：

- 完整研读项目背景、本方案、I0～I2 报告；
- 确认真实 LLM 接入方式；
- 确认真实 Catalog 结构；
- 确认 MCP Gateway 能力；
- 确认当前 Query Builder、Validator、Metric Engine、Session 和 API；
- 输出“复用/增强/新增/删除”映射；
- 冻结 QueryGenerationBundle schema 和 validation error codes。

此工作流第一轮只读，不改代码。

### 20.3 工作流 B：受控生成核心

目标：

- QueryGenerationContextBuilder；
- LLM structured output；
- QueryPlan + DSL + ResultContract 一次生成；
- QueryGenerationValidator V01～V10；
- semantic fingerprint；
- ToolSelector 确定性选择；
- 基础 repair；
- deterministic/shadow/guarded/primary feature flag；
- 审计 trace。

先完成后端 unit/golden，再接真实 MCP 执行。

### 20.4 工作流 C：结果、会话和可信回答

目标：

- Value Resolver；
- 多轮 Typed Patch；
- DataRequirementFingerprint；
- Query Reuse；
- NormalizedResult；
- ResultContract Parser；
- Metric Engine；
- Data QA；
- immutable AnalysisSnapshot；
- Claim/Grounding；
- Chart Planner；
- API/Evidence/前端兼容。

### 20.5 工作流 D：真实对账与统一验收

目标：

- 真实多月 Index；
- 真实 Catalog/Mapping drift；
- 真实 LLM structured output 稳定性；
- 真实 MCP；
- `failure_rate.v1` 报表对账；
- shadow 差异分析；
- guarded 模式 Golden；
- 安全、故障、成本和并发测试；
- 统一最终报告。

工作流 A～D 是同一个 I3 的内部实施顺序，不是四个需要用户逐个批准的 Phase。

---

## 21. 内网模块目标清单

实际文件名以首轮审计为准。下面是职责，不要求机械复制目录。

```text
app/
├── agent/
│   ├── orchestrator.py
│   ├── intent_parser.py
│   ├── turn_router.py
│   ├── state.py
│   └── grounding.py
├── llm/
│   ├── client.py
│   ├── structured_output.py
│   ├── query_generator.py
│   └── prompts/
├── semantic/
│   ├── compiler.py
│   ├── retriever.py
│   ├── resolver.py
│   ├── value_resolver.py
│   └── models.py
├── query/
│   ├── generation_models.py
│   ├── generation_context.py
│   ├── validator.py
│   ├── consistency_validator.py
│   ├── cost_guard.py
│   ├── repair.py
│   ├── deterministic_builder.py
│   └── tool_selector.py
├── metrics/
│   ├── registry.py
│   ├── engine.py
│   └── failure_rate.py
├── results/
│   ├── contracts.py
│   ├── normalizer.py
│   ├── qa.py
│   ├── claims.py
│   └── snapshots.py
├── gateways/
│   ├── base.py
│   ├── mock.py
│   └── mcp.py
├── sessions/
│   ├── store.py
│   ├── models.py
│   └── fingerprint.py
├── policies/
│   └── ...
├── api/
├── templates/
└── static/
```

如果 I2 已有同职责模块：

- 在原模块增强；
- 不复制第二套；
- 不为了文档目录美观做大规模搬迁。

---

## 22. LLM 接入要求

内网应参考已批准项目的真实 LLM 调用方式，复用：

- 认证；
- endpoint；
- model deployment；
- timeout；
- retry；
- trace ID；
- 日志脱敏；
- structured output；
- token 统计；
- 并发限制；
- 环境变量管理；
- 证书和代理规范。

Query Generator 专用配置：

```text
temperature: 0 或内网最低稳定值
structured output: required
schema: QueryGenerationBundle
timeout: centralized
max retries: centralized
max repair: 1（默认）
prompt version: recorded
model id/version: recorded
```

LLM Client 接口建议：

```python
class QueryGenerationLLM(Protocol):
    async def generate_query_bundle(
        self,
        context: QueryGenerationContext,
    ) -> QueryGenerationBundle:
        ...
```

不得让业务模块直接调用供应商 SDK。

### 22.1 按任务隔离 LLM 配置

即使底层复用同一个批准的 LLM Client，也应把任务配置分开：

```yaml
llm:
  intent_parser:
    prompt_version: intent.v1
    temperature: 0
  query_generator:
    prompt_version: query_bundle.v1
    temperature: 0
    structured_schema: QueryGenerationBundle
  query_repair:
    prompt_version: query_repair.v1
    temperature: 0
    max_attempts: 1
  summary:
    prompt_version: grounded_summary.v1
    temperature: 0
```

各任务使用不同输入模型、输出 schema、timeout 和 token 上限，不能用一个“大 Prompt”
同时承担意图、生成、修复和总结。

### 22.2 集中配置与 Feature Flag

以下参数必须集中配置并在启动时校验，不能散落为魔法数字：

```yaml
query_generation:
  mode: shadow
  provider: application_llm
  max_repair_attempts: 1
  hard_max_repair_attempts: 2
  allow_llm_match_all: false
query_limits:
  max_indices: 12
  max_time_range_days: 366
  max_buckets: 500
  max_terms_size: 100
  request_timeout_ms: 10000
sessions:
  ttl_seconds: 1800
  max_sessions: 1000
  max_turns: 20
visualization:
  allowed_types: [bar, line, horizontal_bar, table]
  max_points: 500
```

示例数值需要根据内网容量测试确认；安全默认值必须 fail-closed。配置版本和 hash 要进入
Evidence/trace。

---

## 23. OpenSearch MCP 接入要求

业务模块只能依赖：

```python
class OpenSearchGateway:
    def list_indices(self): ...
    def get_mapping(self, index: str): ...
    def count(self, index: str | list[str], query: dict): ...
    def search(self, index: str | list[str], body: dict): ...
    def msearch(self, requests: list[dict]): ...
```

如 MCP 支持且项目批准，可增加受控：

```python
def validate_query(self, index: str | list[str], query: dict): ...
```

要求：

- Adapter 封装真实 Tool 名称和 schema；
- Tool 参数由程序构造；
- LLM 不接触 MCP Tool Registry；
- 只读；
- timeout/retry/circuit breaker；
- 错误分类；
- 日志脱敏；
- 返回统一类型；
- Index allowlist；
- 不暴露 Generic API；
- 不使用 PPL。

`QueryPlanningTool` 不在本轮 Gateway 的必需接口中。首轮只读审计应通过真实 MCP
`tools/list`、平台配置和权限证明确认可用工具，不能根据 OpenSearch 文档推断内网一定
暴露了该 Tool。即使内网存在，也先保持：

```text
provider = application_llm
QueryGenerationBundle → V01～V10 → ToolSelector → MCP Gateway
```

后续若要评估 OpenSearch `QueryPlanningTool`，必须放在可替换
`QueryGenerationProvider` 后，通过单独 ADR、shadow 对比和安全评审；不得与应用侧
Query Generator 同时成为双主路径，也不得绕过 ResultContract、Metric Engine 或
Validator。

---

## 24. 测试矩阵

### 24.1 既有回归

- I0～I2 全部测试；
- `/api/chat` Golden 必须走同一主入口；
- 首页和静态资源；
- Session reset；
- Node syntax；
- lint/type check；
- 内网完整质量命令。

### 24.2 Query Generation Unit

- QueryGenerationBundle schema；
- extra fields 拒绝；
- 非 JSON 拒绝；
- AnalysisPlan fingerprint；
- metric version；
- unknown field；
- blocked field；
- candidate_role 全链路为零；
- time/index scope；
- keyword/date/nested capability；
- DSL allowlist/denylist；
- ResultContract 路径；
- QueryPlan/DSL filter 一致性；
- grouping/top N/sort 一致性；
- cost guard；
- ToolSelector；
- repair allowed/disallowed；
- fallback 条件；
- feature flag。

### 24.3 LLM Contract

固定安全上下文测试：

- 单 count；
- Failure Rate by Channel；
- SMS 每日趋势；
- Route Top N；
- SMS 与 Email 对比；
- 多条件过滤；
- 跨月；
- 空结果；
- 未知值；
- 未知字段；
- 模糊问题；
- statusCode 误用诱导；
- prompt injection；
- 要求使用 blocked 字段；
- 要求执行任意 API。

每个场景验证：

- schema；
- semantic fingerprint；
- 字段集合；
- DSL 节点；
- ResultContract；
- Tool；
- 指标；
- Evidence。

### 24.4 Failure Rate

- SENT；
- INPROGRESS；
- FAILED；
- ACKFAIL；
- 小写；
- 前后空格；
- null；
- empty string；
- unknown；
- TotalCount=0；
- Retry；
- duplicate；
- 按 Channel；
- 按 Route；
- 按日；
- 多月；
- statusCode 不参与；
- `success + failed + other = total`；
- round 2 decimals。

### 24.5 多轮

- 澄清后继续；
- 增加过滤；
- 替换维度；
- 改时间；
- 改 Top N；
- 换图不重查；
- 改指标必须重查；
- 新问题不误继承；
- pending clarification TTL；
- 并发同 session；
- reset。

### 24.6 Shadow 对比

至少比较：

- AnalysisPlan；
- 字段；
- 时间；
- IndexScope；
- QueryPlan；
- DSL 归一化树；
- ResultContract；
- Tool；
- MetricResult；
- QA；
- 执行耗时；
- bucket 数；
- LLM token/latency。

差异要分类：

```text
equivalent
llm_better
deterministic_better
both_wrong
unsupported
unsafe_rejected
```

### 24.7 安全和故障

- malformed JSON；
- extra field；
- blocked field；
- unknown Index；
- missing Mapping；
- Mapping drift；
- MCP timeout；
- partial shard；
- LLM timeout；
- LLM 429/5xx；
- repair timeout；
- script injection；
- wildcard/regexp/query_string；
- raw hits；
- oversized terms；
- aggregation explosion；
- silent match_all fallback；
- Evidence 泄露；
- Prompt 泄露；
- 原始错误泄露。

### 24.8 Conversation Golden

至少固定以下端到端多轮场景，全部通过同一个 `/api/chat`：

| 编号 | 对话/动作 | 关键验收 |
|---|---|---|
| A | “2026年7月各Channel的Failure Rate” | 分组、v1、Search、bar |
| B | “SMS每天的发送记录趋势” | daily、line、时间左闭右开 |
| C | “哪个Route失败记录最多” | Top N、稳定排序 |
| D | “比较SMS和Email记录数量” | 多值过滤、document count |
| E | “看看最近的失败情况”→“按Channel” | clarification 后续接，不误当新问题 |
| F | “换成表格/柱状图” | Snapshot 足够时复用，不发新查询 |
| G | “再看六月” | 时间和 IndexScope 替换，其他条件按规则继承 |
| H | “按Route并只看SMS” | 同轮多 action 合并为 typed patch |
| I | 跨两个月查询 | 正确 IndexScope、无重复或漏月 |
| J | 空结果 | `answered` 或明确空数据状态，无误导图 |
| K | blocked 字段/prompt injection | 后端阻断，全链路无泄露 |
| L | LLM malformed/unsafe DSL、MCP partial | repair/降级/错误分类可审计 |

每个 Golden 除用户可见结果外，还要断言 AnalysisPlan、ContextDelta、是否重查、
QueryGenerationBundle、Tool、MetricResult、QA、Snapshot 和安全 Evidence。

### 24.9 前端手工验收

- 常见桌面分辨率无横向滚动；
- loading 期间禁用重复提交；
- Enter/Shift+Enter 正确；
- 澄清选项和自由输入都可继续原问题；
- Clear Conversation 调用 reset 并更新 session；
- KPI/table/chart 按结构化响应渲染；
- chart resize、空数据、长标签和 Top N 正常；
- Evidence 默认折叠且无 blocked/raw 数据；
- 后端 4xx/5xx、timeout、not_answerable 有可理解提示；
- 页面源代码和网络响应中没有外部 CDN、凭证或动态可执行代码。

---

## 25. 发布门槛

建议 I3 guarded 验收门槛：

| 指标 | 门槛 |
|---|---|
| 既有回归 | 100% |
| 核心 Golden answered/clarify/block 状态 | 100% |
| Failure Rate 对账 | 100% |
| blocked/candidate_role 泄露 | 0 |
| 未知字段执行 | 0 |
| 未知 Index 执行 | 0 |
| 禁止 DSL 节点执行 | 0 |
| QueryPlan/DSL/ResultContract 不一致仍执行 | 0 |
| 语义 fingerprint 漂移仍执行 | 0 |
| 生成失败静默 match_all | 0 |
| LLM 选择或直接调用 Tool | 0 |
| 前端重新计算指标 | 0 |
| 空结果生成误导图 | 0 |
| MCP 原始敏感错误外泄 | 0 |

shadow → guarded 的额外条件：

- 核心 Golden 全部通过；
- 无安全回归；
- LLM bundle schema 稳定；
- validator 覆盖全部允许 DSL 节点；
- 真实 MCP 错误分类完成；
- fallback 触发可审计；
- p95 延迟在 POC 可接受范围；
- 项目负责人确认。

guarded → primary 的额外条件：

- 扩展 Golden 稳定；
- shadow 差异已经人工抽查；
- 真实报表对账完成；
- 误查/越权为零；
- 线上观测和 emergency switch 可用。

---

## 26. 可观测性

每轮记录结构化 trace：

```text
request_id
session_id_hash
turn_type
analysis_plan_id
semantic_fingerprint
semantic_model_version
mapping_fingerprint
metric_config_version
prompt_version
model_id
query_generation_mode
validation_codes
repair_count
fallback_used
tool
index_scope_hash
query_shape_hash
estimated_cost
gateway_latency
metric_latency
qa_status
response_status
```

除单次 trace 外，至少聚合以下质量与产品指标：

| 类型 | 指标示例 |
|---|---|
| 路由 | clarification/REUSE/REQUERY/blocked 准确率、错误继承率 |
| 生成 | schema 成功率、V01～V10 各错误率、repair 成功率、语义漂移率 |
| 安全 | blocked/candidate_role/未知字段/禁用 DSL 拦截数与漏过数 |
| 查询 | Count/Search/Msearch 分布、partial/timeout、bucket/耗时 p50/p95 |
| 指标 | Failure Rate 对账通过率、QA warning、空分母、unknown status 比例 |
| 回答 | grounding 通过率、deterministic summary 降级率、chart feasibility |
| 成本 | 每任务 LLM 调用数、token、延迟和失败率 |
| 复用 | Snapshot 命中率、无效重查率、过期/partial 拒绝复用率 |

任何指标都不得以记录原始敏感内容为代价。质量阈值由内网 Golden 和容量测试基线确定，
不能凭空写成“生产 SLA 已满足”。

不得记录：

- 原始敏感用户值；
- blocked 字段；
- 凭证；
- 全量 Prompt；
- chain-of-thought；
- 未清理原始 hits。

---

## 27. 回滚策略

必须可通过配置立即切换：

```text
primary/guarded
→ shadow
→ deterministic
```

回滚不应修改：

- API；
- Session 协议；
- Metric Engine；
- Gateway；
- 前端结构；
- Catalog；
- Mapping；
- 已保存 Evidence schema。

回滚触发条件示例：

- validator 漏过禁用节点；
- 真实结果对账差异；
- LLM schema 大量失败；
- p95 延迟超阈值；
- MCP 压力异常；
- Evidence 泄露风险；
- 映射 drift 未被正确拦截。

---

## 28. 当前不阻塞 I3 的事项

- 生产完整 Policy/RBAC；
- 运营商 statusCode 码表；
- carrier failure rate；
- 数据库持久 Session；
- LangGraph；
- React/Vue；
- PPL；
- Generic API；
- 自由 Agent Tool Loop；
- Python 任意代码执行；
- 复杂预测模型；
- 未经验证的自动学习。

这些事项不得描述为已完成，但不阻塞当前 POC。

---

## 29. I3 首轮只读审计必须回答

内网 AI 在修改代码前必须提交一份简洁审计：

1. 当前分支、HEAD、dirty files；
2. I0～I2 的真实提交和测试证据；
3. 当前 `/api/chat` 主流程；
4. 当前 AnalysisPlan、QueryPlan、DSL、Tool 边界；
5. 当前真实 LLM 调用方式和 structured output 能力；
6. 当前 `field_catalog_enrich.csv` 列定义及 compiler 行为；
7. Catalog 与实时 Mapping 如何校验；
8. 当前多月 Index 选择；
9. 当前 Metric Registry 和 `failure_rate.v1`；
10. 当前 MCP Tool 名、参数、返回和错误样例；
11. 当前 Session/clarification；
12. 当前 Validator 能力和缺口；
13. 当前确定性 Builder 可覆盖场景；
14. 当前测试数量和已知失败；
15. 本方案各目标职责对应“复用/增强/新增/不做”的文件映射；
16. 预计 checkpoint commit 顺序；
17. 真实 MCP `tools/list` 中是否存在 QueryPlanningTool；如果存在，其版本、权限、
    输入输出与默认行为是什么；无论是否存在，本轮是否保持 `application_llm`；
18. 真实阻塞项。

项目负责人确认该审计后，同一 Session 继续完成统一 I3。

---

## 30. 可直接交给内网新 Session 的提示词

```text
你负责继续完成 OpenSearch ChatBI 项目的统一 I3：受控智能查询生成、真实 OpenSearch
MCP 接入完善、可信结果链路和最终 POC 验收。

已知前提：
1. I0、I1、I2 已在内网完成，I3 尚未开始。
2. 外网 GitHub 不包含内网 I2，不能把外网代码当作当前实现基线，也不要从外网分支
   覆盖内网代码。
3. 请先完整研读：
   - 原始项目背景与需求；
   - 《OpenSearch ChatBI 统一智能增强详细技术升级执行方案》；
   - 内网 I0、I1、I2 最终报告；
   - 内网真实代码、配置、Git 历史和测试。
4. 如果文档文件名与真实工程不同，以职责映射为准，不要为了对齐目录重写工程。
5. 生产完整 Policy/RBAC 本轮暂缓，但已有 blocked 字段和基础安全机制不能削弱。
6. failure_rate.v1 使用 status；statusCode 是运营商原始编码，当前不得替代 status。
7. 数据覆盖全部月份，2026年7月只是默认月份；时间区间使用 Asia/Hong_Kong 和
   [start,end)。
8. 使用 OpenSearch Query DSL，不使用 PPL，不暴露 Generic OpenSearch API。

核心技术决策：
- AnalysisPlan 只表达业务意图，不含 Tool/DSL。
- 在 AnalysisPlan、语义字段、指标、值、时间和 IndexScope 都确定后，允许真实 LLM
  在一次 structured-output 调用中同时生成 QueryPlan、OpenSearch DSL 和
  ResultContract。
- LLM 输出只是候选 QueryGenerationBundle。必须完整通过方案中的 V01～V10
  确定性校验后才能执行。
- 最终 Tool 由程序选择；LLM 不知道、不选择、不调用 MCP Tool。
- Metric Engine 唯一负责 failure_rate.v1 等指标的最终计算。
- 生成失败不得静默 fallback 到 match_all。
- 保留现有确定性 Builder 作为 shadow 对照、受控简单场景 fallback 和测试 oracle。
- 不引入自由 Agent/Tool loop；当前不引入 LangGraph。
- OpenSearch QueryPlanningTool 仅作为可研究的官方能力，不假设它是当前 MCP Tool，
  本轮默认不作为运行时 Query Generator。

第一轮只能做只读审计，不修改代码。请按方案第29节回答，并给出：
- 内网真实现状；
- 复用/增强/新增/不做映射；
- QueryGenerationBundle 最终 schema 草案；
- Validator V01～V10 落点；
- shadow/guarded 切换方式；
- checkpoint commit 顺序；
- 测试计划；
- 真实阻塞项。

我确认首轮审计后，你在同一个统一 I3 中连续实施，不再拆很多 Phase，也不要每做一个
小模块就暂停。使用小而可回滚的 checkpoint commit；每个 checkpoint 运行相关测试。
只有遇到方案列出的真实阻塞才停下来询问。

最终必须通过同一 /api/chat 主入口完成：
- 单纯 document count；
- Failure Rate by Channel；
- SMS 每日趋势；
- Route Top N；
- SMS 与 Email 对比；
- 多条件过滤；
- 跨月查询；
- 空结果；
- 未知值/字段；
- 多轮澄清；
- 换图复用；
- Policy 阻断；
- LLM malformed/unsafe DSL；
- MCP timeout/partial failure；
- failure_rate.v1 真实报表对账。

统一 I3 完成后只输出一份最终报告：
- 修改文件；
- 架构和关键合同；
- LLM、Catalog、Mapping、MCP 的真实接入；
- QueryPlan+DSL 一次生成和 validator；
- feature flag 与回滚；
- 测试命令及结果；
- Golden/对账结果；
- 性能和已知限制；
- 未完成事项；
- commit 清单。

不要修改冻结指标口径，不要让 LLM 直接执行查询，不要让前端重新计算指标，不要声称
生产 Policy/RBAC 或运营商码表已经完成。
```

---

## 31. Definition of Done

- [ ] 内网真实 I2 基线完成只读审计；
- [ ] 真实 LLM 按内网批准方式接入；
- [ ] QueryGenerationBundle 使用 strict structured output；
- [ ] QueryPlan + DSL + ResultContract 一次生成；
- [ ] AnalysisPlan 不含 Tool/DSL；
- [ ] LLM 不选择、不调用 Tool；
- [ ] QueryPlanningTool 未被误当作默认 MCP Tool 或绕过应用校验；
- [ ] 单一 Orchestrator、typed state、明确 transition 和终态；
- [ ] Turn Router 支持多 action 和 ContextDelta；
- [ ] V01～V10 validator 全部实现；
- [ ] semantic fingerprint 防止 repair 语义漂移；
- [ ] DSL allowlist 和 denylist 完整；
- [ ] 固定 aggregation alias 与 ResultContract 路径通过测试；
- [ ] Msearch 部分失败有明确状态，禁止拼成完整成功；
- [ ] 生成失败不会静默 match_all；
- [ ] deterministic/shadow/guarded/primary 可配置；
- [ ] LLM、query limits、session、visualization 配置集中且可审计；
- [ ] 真实 Catalog 成为主语义来源；
- [ ] 实时 Mapping drift fail-closed；
- [ ] `candidate_role` 全链路为零；
- [ ] 基础 blocked 字段全链路为零；
- [ ] Value Resolver 使用 canonical values；
- [ ] 多月 Index 正确；
- [ ] `failure_rate.v1` 使用 status；
- [ ] Metric Engine 确定性计算并完成真实对账；
- [ ] statusCode 未被错误用于 v1；
- [ ] NormalizedResult、Data QA、AnalysisSnapshot；
- [ ] Query Reuse 使用数据需求指纹；
- [ ] Claim/Grounding 防止无依据总结；
- [ ] Summary 失败可降级为 deterministic claims；
- [ ] follow-up questions 只包含当前能力允许的动作；
- [ ] Chart 不重复计算指标；
- [ ] ChartSpec 与固定前端 adapter 通过可行性校验；
- [ ] API 向后兼容；
- [ ] Evidence 完整且安全清理；
- [ ] Golden 全部走 `/api/chat`；
- [ ] Conversation Golden A～L 和前端手工清单通过；
- [ ] Prompt Injection 和统一降级矩阵通过；
- [ ] 质量、性能、安全、成本和复用指标可观测；
- [ ] 安全和故障测试通过；
- [ ] emergency deterministic switch 可用；
- [ ] README/项目记忆/最终报告反映真实实现，不保留过时阶段口径；
- [ ] 统一 I3 最终报告完成。

---

## 32. 参考资料

- [SQLBot 官方仓库](https://github.com/dataease/SQLBot)
- [SQLBot 查询生成与执行实现](https://github.com/dataease/SQLBot/blob/main/backend/apps/chat/task/llm.py)
- [Vanna 官方文档](https://vanna.ai/docs)
- [Vanna 训练/RAG 资料类型](https://try.vanna.ai/docs/train/)
- [DB-GPT 官方仓库](https://github.com/eosphoros-ai/DB-GPT)
- [WrenAI 官方仓库](https://github.com/Canner/WrenAI)
- [PICARD 官方实现](https://github.com/ServiceNow/picard)
- [PICARD 论文](https://arxiv.org/abs/2109.05093)
- [OpenSearch Query Planning Tool](https://docs.opensearch.org/latest/ml-commons-plugin/agents-tools/tools/query-planning-tool/)
- [OpenSearch ML Commons Tools](https://docs.opensearch.org/latest/ml-commons-plugin/agents-tools/tools/index/)
- [OpenSearch MCP Server](https://docs.opensearch.org/latest/ai-agent-integrations/mcp-server/index/)
- [OpenSearch Agentic Search 与外部 MCP Tools](https://docs.opensearch.org/latest/vector-search/ai-search/agentic-search/mcp-server/)
- [OpenSearch Validate Query API](https://docs.opensearch.org/latest/api-reference/search-apis/validate/)
- [OpenSearch Query DSL](https://docs.opensearch.org/latest/query-dsl/)
