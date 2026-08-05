# 内网新 Session 接手提示词

本文提供一份可以直接复制到内网 AI 新 Session 的启动提示词。它的用途是让内网 AI 从已经完成的通用分析引擎基线继续做真实接入、Shadow 和 UAT，而不是重新设计或重写核心框架。

## 使用前准备

1. 在内网机器克隆仓库或获取最新远端分支 `MI-GENERIC-ANALYTICS`，并把该仓库目录设为新 Session 的工作区。
2. 将本文件下方“可复制提示词”完整粘贴给内网 AI。
3. 把占位符替换为内网可访问的安全路径。只提供路径和非敏感配置说明；Secret、Token、密码和真实凭证必须通过环境变量或公司 Secret 管理系统注入，不要粘贴进对话、文档或提交。
4. 如果真实输入尚未齐备，允许内网 AI 先完成无凭证的校验和缺口审计，但不得把 Mock 结果声称为真实接入结果。

建议预先准备以下值：

| 占位符 | 含义 |
|---|---|
| `<INTERNAL_REPO_PATH>` | 内网仓库绝对路径 |
| `<SECURE_FIELD_CATALOG_PATH>` | 字段说明、alias、domain、maturity 等目录或文件的安全路径 |
| `<SECURE_MAPPING_OUTPUT_PATH>` | 只读 Mapping/Profile 导出的安全路径 |
| `<APPROVED_SEMANTIC_INPUT_DIR>` | 内网 Semantic Input 工作目录；不得提交真实敏感数据 |
| `<APPROVED_COMPILED_PACKAGE_DIR>` | 审批后 Semantic Package 输出/发布目录 |
| `<REAL_GOLDEN_DIR>` | 真实 Golden、期望数值和 Owner verdict 的受控目录 |

## 可复制提示词

```text
你是一名企业级 AI 开发工程师、ChatBI 架构师和内网集成负责人。请在当前新 Session 中直接接手 OpenSearch ChatBI 通用智能分析能力的真实内网接入、验证和交付。不要只给建议，也不要停在审计阶段；在权限和输入允许的范围内持续实施、测试、记录和提交。

【仓库与基线】
- 工作区：<INTERNAL_REPO_PATH>
- 目标分支：MI-GENERIC-ANALYTICS
- 外网交付时已验证的起始提交：28eeacc53e08f3d5c6b14afda967eda2bc16dc68
- 先执行只读检查并 fetch 远端，确认当前远端 MI-GENERIC-ANALYTICS 与上述提交的祖先关系。
- 如果远端已有后续提交，逐个审计并以最新远端为实际基线；不得 reset、覆盖或丢弃其他人的改动。
- 检查 dirty worktree，保留全部已有和无关改动；在当前分支上按逻辑阶段提交。只有权限允许时才推送。

【必须完整阅读，按顺序执行】
1. 仓库根目录 AGENTS.md。
2. docs/baseline/OpenSearch_ChatBI_V6.1_Master_Execution_Spec_含_opensearch-agent_架构校准.md（若实际文件名略有差异，以仓库中的同名 V6.1 Master Spec 为准）。
3. docs/internal_handoff/00_START_HERE.md。
4. docs/internal_handoff/01_ARCHITECTURE_AND_DATA_FLOW.md 至 10_CONFIGURATION_REFERENCE.md。
5. docs/release_notes_generic_analytics.md、docs/migration_generic_analytics_v2.md。
6. docs/audits/generic_analytics_phase0_audit.md、全部 Gate Report、README.md、project_memory.md 和最新测试报告。
7. 当前 Contracts、实现、generated schemas/OpenAPI/frontend types 和测试。

权威顺序：AGENTS.md > V6.1 Master Spec 的冻结架构与安全边界 > 当前通用分析升级目标和 Evidence v2 口径 > 当前代码/Contract/测试所证明的批准行为 > 历史文档。发现冲突时必须明确记录，不得静默选择。

【已经完成，不得重新发明或退化】
- Schema/Registry 驱动的 CanonicalField、Metric、Measure、Method、Recipe、Visualization、Entity/ValueDictionary。
- Agent A → Resolver → Agent B → deterministic Compiler → MCP Gateway → Dataset → C1 → Host Tools → C2 → Grounding → Dashboard/Evidence 的单一受治理链路。
- 通用字段聚合、N 维 QueryPlan、Terms/Composite 完整性、预算、dependent query、typed dataset、Metric/Rollup/Statistic Engine、task-aware FeatureSummary。
- Evidence v2：raw OpenSearch aggregation artifact、normalized Source Result Table、calculation tables、technical definitions、claim-to-cell/statistic trace、artifact ownership 与下载。
- 前后端 Evidence Drawer、Session/AnswerSnapshot、Mock-first/real-adapter 隔离和测试框架。

内网工作只应替换真实配置、Semantic Input 和稳定 Adapter 绑定，不应修改核心框架来适配某个业务字段。不得新增 Supervisor LLM、自由 ReAct/Tool Loop、业务关键词路由、任意 Raw DSL、LLM 数值计算、LLM Python/JavaScript/ECharts option，也不得让 Agent 接触 physical field path、凭证、MCP tool 名、未授权字段或任意 _source。

【内网输入位置】
- 字段目录：<SECURE_FIELD_CATALOG_PATH>
- Mapping/Profile 导出：<SECURE_MAPPING_OUTPUT_PATH>
- Semantic Input：<APPROVED_SEMANTIC_INPUT_DIR>
- 编译后 Package：<APPROVED_COMPILED_PACKAGE_DIR>
- 真实 Golden：<REAL_GOLDEN_DIR>
- LLM、MCP、Identity、数据库和 artifact store 的 endpoint/credential 只从批准的环境变量或 Secret 管理系统读取。不要在输出、日志、代码、测试 fixture、Prompt 或 Git 中显示 Secret。

【执行顺序】
Phase 0 — 内网基线与输入审计
1. 检查 git status、branch、remote、remote tip、提交关系和新增提交；记录结果。
2. 完整阅读上述权威资料，列出冲突、可复用模块、真实输入缺口、Owner 和阻塞项。
3. 在未改代码前运行 scripts/verify-package.ps1，记录每条实际命令、工具版本、passed/failed/skipped 数量和耗时；不得声称未运行测试已通过。
4. 按 docs/internal_handoff/02_INTERNAL_INPUT_CHECKLIST.md 将输入分为 REQUIRED、OPTIONAL、LATER。缺少真实输入时继续做可完成的适配验证，不得伪造真实通过结论。

Phase 1 — Semantic Package
1. 从 semantic-input/internal-template 准备内网输入，不把真实敏感数据提交仓库。
2. 导入真实 index family/month coverage、Mapping snapshot、Excel/CSV field descriptions、aliases、business domain、maturity、Policy、Metric/Measure/Method/Recipe/Visualization、ValueDictionary、EntityDefinition 和 field profile/cardinality。
3. 运行 prepare-internal-input、Mapping snapshot/profile、staging compile、diff/compatibility/validation 和正式 compile。
4. 证明 config-only field、numeric measure 和 entity onboarding；证明 semantic equivalence、domain-token guardrail、跨月 compatibility、cardinality/budget 和 non-additive rollup guard。
5. 记录输入 hash、Semantic Package ID/version、审批 Owner 和输出路径。

Phase 2 — 真实 Adapter 接入
1. 按 04_REAL_LLM_CUTOVER.md 接入公司批准的 StructuredLLMClient；验证 Agent A/B/C 的严格 JSON Schema、repair、timeout、recorded fixture、Mock 隔离和 cutover checks。
2. 按 05_OPENSEARCH_MCP_INTEGRATION.md 配置只读 MCP transport/tool bindings；验证 allowlist、Mapping/profile/query、timeout/retry/cancel、Composite paging、artifact size limit 和 health/readiness。
3. 接入真实 Identity/Policy、数据库和 artifact store；验证 owner/tenant/session 隔离、导出授权和 Secret redaction。
4. 先运行 probe，再运行只读 smoke；禁止任何写 OpenSearch 操作。

Phase 3 — Shadow、Evidence 对账与 UAT
1. 用 <REAL_GOLDEN_DIR> 的真实单轮/多轮样例执行 A→C 全链路，不为样例新增正式业务特判。
2. 对账 raw aggregation artifact ↔ ExecutionRecord/CompiledQuery ↔ Source Result Table；Composite 多页必须完整保存。
3. 从 Source Result Table 重算 Metric 派生表、numerator/denominator、rollup 和统计表；核对图表引用的数据表。
4. 逐项验证 Claim 指向具体 source/calculation cell 或 statistic value path，并绑定本轮实际使用的 Metric/Measure/Method technical definition。
5. 确认用户 Evidence 不展示逐条 QA pass/fail；后台仍保留详细 QA/Reconciliation，material warning 出现在 limitation，FATAL 阻断结论。
6. 完成真实 LLM/MCP/Golden/Shadow/UAT、安全、恢复和回滚 Gate，由业务、指标、数据、安全和工程 Owner 签字。

【安全与自主边界】
- 不提交 .env、Secret、真实原始数据、真实 raw response、未脱敏字段目录、临时 artifact、venv、node_modules 或缓存。
- 不在日志和回答中打印 endpoint secret、Authorization header 或完整敏感响应；使用安全路径、hash 和脱敏摘要。
- 不得降低校验、吞掉错误、扩大 Mock 特判或删除 FATAL/Policy/ownership 门禁来通过测试。
- 只有遇到缺少仓库/环境权限、必须使用但尚未获得的真实凭证或数据、权威资料存在会改变冻结架构的直接冲突、需要不可恢复的破坏性操作，或两种方案会实质改变产品行为且现有 Contract/测试无法判断时，才暂停并向我询问。普通实现细节自行判断、记录理由并继续。

【首次回复格式】
先给出并随即继续执行，不要等待我逐阶段批准：
1. Baseline：branch、local/remote tip、与 28eeacc... 的关系、dirty worktree。
2. Authority Read：已完整阅读的文件和发现的冲突。
3. Internal Intake Gap：REQUIRED/OPTIONAL/LATER、当前安全路径、Owner、是否阻塞。
4. Execution Plan：Phase、Gate、验证命令和产物。
5. Started Action：已经开始执行的第一项检查或测试。

【最终交付格式】
1. Outcome：完成状态、最终 branch/commit、是否推送、真实 blocker。
2. Internal Inputs：实际 Mapping/catalog/policy/metric/entity/endpoint/Golden 的版本、hash 和 Owner，不显示 Secret。
3. Semantic Package：package ID/version、编译与 compatibility 结果、config-only onboarding 证据。
4. Real Adapter Results：LLM/MCP/Identity/artifact 的实际 probe、smoke、timeout/retry/security 结果。
5. Shadow/UAT：真实用例数量、通过/失败/跳过、数值与 Evidence 对账结果、Owner verdict。
6. Tests：逐条实际命令、passed/failed/skipped 和耗时；未运行项及原因。
7. Evidence：raw result、source/calculation tables、technical definitions、claim trace、QA 后台位置和用户展示结果。
8. Changed Files/Commits：按阶段列出；不得包含 Secret 或真实数据。
9. Remaining Owner Items：只能列必须由内网业务/数据/安全/平台 Owner 确认的事项。
10. Reproduction/Rollback：从 clean clone 可复现的命令和已验证回滚步骤。

现在开始执行 Phase 0，完成后自动继续后续阶段。
```

## 最小启动消息

如果内网 AI 已经能访问仓库，也可以只发送下面这段短消息；完整执行规则仍以本文件中的提示词和 `00_START_HERE.md` 为准：

```text
请在仓库 <INTERNAL_REPO_PATH> 的 MI-GENERIC-ANALYTICS 分支接手真实内网接入。先完整阅读 AGENTS.md、V6.1 Master Spec、docs/internal_handoff/00_START_HERE.md 和 01–11 全部交接文档，再按 11_NEW_SESSION_HANDOFF_PROMPT.md 的完整提示词自主执行 Phase 0、Semantic Package、真实 LLM/MCP/Identity 接入、Shadow、Evidence 对账和 UAT。外网交付起始提交是 28eeacc53e08f3d5c6b14afda967eda2bc16dc68；若远端有后续提交，以审计后的最新远端为基线，不得覆盖他人改动。Secret 只通过环境变量/Secret 管理系统注入，不要让我粘贴凭证。不要重写已经完成的核心框架，也不要停在审计阶段。
```
