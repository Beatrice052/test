# 内网分阶段新 Session 执行提示词

## 使用方法

I0 已完成。后续 POC 只分三个阶段：

```text
I1  真实语义模型
I2  真实 LLM + OpenSearch MCP 连接和端到端联调
I3  指标对账和 POC 最终验收
```

生产 Policy/RBAC、认证、持久化 Session、正式审计和生产压测不属于当前 POC
必做项，统一放在可选的 Production 阶段。

每次只把当前阶段的提示词复制到一个新 Session。AI 必须先阅读提示词指定的文档，
按文档实现，不需要在提示词中重新解释整套架构和公式。

所有阶段共同遵守：

- 用户最新确认和 `docs/DECISION_LOG.md` 优先；
- 不重写 Agent 主流程、Metric Engine、API 契约或前端；
- AnalysisPlan/QueryPlan 不含 Tool/DSL；
- DSL 由 QueryDslBuilder 生成，Tool 在 DSL 校验后由程序选择；
- 不使用 PPL、Generic API、LLM 自由 Tool loop；
- 不提交凭证、内网 URL、生产明细或客户数据；
- 每阶段运行 `docs/INTRANET_EXECUTION_CHECKLIST.md` 中的完整质量命令；
- 完成阶段报告后停止，等待项目负责人确认。

---

## I1 新 Session 提示词：真实语义模型

复制下面内容：

````text
你负责 OpenSearch ChatBI 的 I1：真实语义模型。

仓库：Beatrice052/test
分支：MI_ChatBI

I0 已经由项目负责人确认完成。开始前先确认 branch、HEAD、working tree 和测试基线。

必须完整阅读：

1. AGENTS.md
2. docs/DECISION_LOG.md
3. docs/REAL_SEMANTIC_ONBOARDING.md
4. docs/INTRANET_EXECUTION_CHECKLIST.md 的 I1
5. ARCHITECTURE.md 的语义编译和安全边界
6. app/semantic/compiler.py
7. app/semantic/models.py
8. app/semantic/resolver.py
9. app/semantic/retriever.py
10. app/query/planner.py、app/query/validator.py
11. 对应单元测试和 /api/chat 集成测试

本阶段目标：

1. 使用真实 field_catalog_enrich.csv 作为语义主资料。
2. 校验 CSV schema、重复字段、类型提示、别名、access、sensitivity 和
   candidate_role 隔离。
3. 通过 MCP list_indices/get_mapping 自动获取实际月份 Mapping。
4. Mapping 只用于验证字段存在性、物理类型、keyword/date/object/nested、
   aggregatable/searchable 和跨月 drift；不要要求业务方再维护一份 Mapping 表。
5. Catalog-only 不可查询；Mapping-only 或缺少 access 的字段默认
   review_required；类型冲突和不兼容 drift 必须 fail closed。
6. 编译真实 CompiledSemanticModel、Import Report、version 和 hash。
7. 确认真实时间字段，并将 failure_rate.v1 绑定到 status；不得绑定 statusCode。
8. LLM、Resolver、Validator 后续必须共享同一个 semantic_compilation。

最新确认：

- failure_rate.v1 已定义，不再询问公式或 owner；I1 只检查字段绑定。
- 生产 Policy/RBAC 延后，不阻塞 I1。
- POC 使用 Catalog 的 access/sensitivity 和现有后端技术 Policy。
- 标记 production_policy_rbac_status=pending。
- I1 只可使用 MCP list_indices/get_mapping，不执行 count/search/msearch，不获取 hits。

实现程度以 docs/REAL_SEMANTIC_ONBOARDING.md 和 I1 checklist 为准。不要在提示词之外
自行扩大范围。

完成后：

1. 运行完整质量命令；
2. 输出 I1 报告，至少包含修改文件、Catalog version/hash、检查的月份、
   Mapping drift、字段冲突、access 统计、时间/status 绑定、candidate_role 隔离、
   测试结果、未完成项和回滚点；
3. 停止，不开始 I2。
````

---

## I2 新 Session 提示词：真实 LLM + OpenSearch MCP

复制下面内容：

````text
你负责 OpenSearch ChatBI 的 I2：一次性接入真实 LLM 和真实 OpenSearch MCP，
并跑通端到端 /api/chat。

仓库：Beatrice052/test
分支：MI_ChatBI

项目负责人已经验收 I1。开始前确认 branch、HEAD、I1 报告、semantic model
version/hash 和测试基线。

必须完整阅读：

1. AGENTS.md
2. docs/DECISION_LOG.md
3. docs/REAL_LLM_INTEGRATION.md
4. docs/REAL_OPENSEARCH_MCP_INTEGRATION.md
5. docs/INTRANET_EXECUTION_CHECKLIST.md 的 I2
6. ARCHITECTURE.md
7. docs/API.md
8. app/intent/structured_client.py
9. app/gateway/mcp.py、app/gateway/execution.py
10. app/query/dsl.py、app/query/validator.py
11. app/main.py 和相关测试
12. I1 阶段报告

本阶段目标：

1. 参考内网已经批准的 LLM 项目，实现 StructuredLLMTransport。
2. 使用其实际 client/factory、认证、structured output、timeout、retry 和日志规范；
   不复制凭证、业务 Prompt 或真实数据。
3. LLM 只生成 AnalysisPlan 和结果总结；不能生成 QueryPlan、DSL、Tool、指标公式
   或 HTML。
4. Prompt 只包含 Catalog access=allowed 的必要语义摘要，blocked、
   review_required 和 candidate_role 必须为零。
5. 实现实际 MCP 平台的 AllowedMCPToolClient：
   list_indices、get_mapping、count、search、msearch。
6. 不增加 PPL、Generic API 或任意 HTTP path。
7. 保持 QueryPlan → CompiledQuery/DSL → Validator → deterministic ToolSelector
   → Gateway 的执行顺序。
8. 正确归一化 timeout、auth、not found、partial shard 和 msearch item error；
   不完整结果不能输出 KPI、表格或图表。
9. 通过 create_app 显式注入真实 LLM、真实 Gateway 和 I1 semantic compilation；
   真实模式缺少依赖时必须启动失败，不能回退 Mock。
10. 使用批准的内网 dev/test 或最小权限聚合范围，跑通真实：
    - 单月 count；
    - 分组/趋势/Top N；
    - 跨月；
    - 多轮澄清；
    - 空结果；
    - Policy 阻断；
    - Evidence。

生产 Policy/RBAC 仍为 pending，不阻塞本阶段；继续使用 Catalog access 和后端
Validator，不能声称已达到生产安全验收。

实现和测试细节以两份 REAL_*_INTEGRATION.md 和 I2 checklist 为准。

完成后：

1. 运行完整质量命令和全部 /api/chat Golden；
2. 输出 I2 报告，至少包含参考 LLM 接入方式、MCP Tool schema、修改文件、
   依赖注入、错误处理、Prompt/日志安全、端到端场景、测试结果、未完成项和回滚点；
3. 停止，不开始 I3。
````

---

## I3 新 Session 提示词：指标对账与 POC 最终验收

复制下面内容：

````text
你负责 OpenSearch ChatBI 的 I3：指标对账和 POC 最终验收。

仓库：Beatrice052/test
分支：MI_ChatBI

项目负责人已经验收 I2，真实 LLM、真实 OpenSearch MCP 和 /api/chat 已经连通。

必须完整阅读：

1. AGENTS.md
2. docs/PROJECT_BACKGROUND.md
3. docs/DECISION_LOG.md
4. docs/INTRANET_EXECUTION_CHECKLIST.md 的 I3
5. docs/API.md
6. docs/MANUAL_ACCEPTANCE.md
7. app/metrics/engine.py
8. app/results/qa.py、app/results/processor.py
9. I1、I2 阶段报告

本阶段目标：

1. 使用最小化脱敏的聚合结果，对账 record_count.v1 和 failure_rate.v1。
2. failure_rate.v1 定义已经冻结，不再询问或修改：
   - document count 为分母；
   - normalized(status) 的 SENT/INPROGRESS 为成功；
   - FAILED/ACKFAIL 为失败；
   - null/空/未知为 Other；
   - retry/duplicate 计入分母；
   - 零分母为 null；
   - ROUND_HALF_UP 两位。
3. 至少对账总体、每日、Channel、Route、单月、跨月、null/unknown、
   retry/duplicate。
4. 差异先从时间区间、月份、字段、filters、状态规范化和舍入定位；不得为了匹配
   报表静默修改 v1。真实口径不同只能提出新版本建议，等项目负责人确认。
5. 如果三运营商 carrier/statusCode 码表已经齐全，可在本阶段新增独立版本化指标；
   如果资料不齐，记录为后续可选能力，不阻塞通用 ChatBI POC 验收。
6. 完成真实端到端验收：
   - 所有 Golden 经 /api/chat；
   - KPI、表格、图表；
   - 多轮澄清；
   - 空结果；
   - blocked；
   - Evidence；
   - LLM/MCP timeout、partial error；
   - Mock/Connected 状态；
   - 常见桌面页面验收。
7. 生产 Policy/RBAC、正式认证、持久化 Session、生产审计和生产压测不属于本次
   POC Gate，继续明确标记 pending。

实现和验收程度以项目背景、Decision Log、API、Manual Acceptance 和 I3 checklist
为准。

完成后：

1. 运行完整质量命令；
2. 输出 POC 最终验收报告，包括对账结果、E2E 场景、故障测试、前端验收、
   数据限制、未完成生产化事项和回滚方式；
3. 停止，等待项目负责人决定是否结束 POC 或进入可选 Production 阶段。
````

---

## 可选 Production 新 Session 提示词

只有项目负责人明确要求生产上线时才使用：

````text
你负责 OpenSearch ChatBI 的生产化加固。本阶段不是当前 POC 的必做项。

仓库：Beatrice052/test
分支：MI_ChatBI

开始前必须阅读 I1～I3 报告、docs/INTRANET_EXECUTION_CHECKLIST.md 的 Production
部分、架构/API/安全文档，并获得项目负责人明确授权。

本阶段根据银行内部规范补齐：

- 生产 Policy/RBAC 和字段/角色/Index 权限；
- 身份认证、管理接口保护；
- secret/TLS/证书；
- 持久化且隔离的 Session；
- 日志、Prompt、Evidence、审计和留存；
- 限流、并发、SLO 和性能压测；
- LLM/MCP/Mapping/Session 故障演练；
- 回滚、部署和生产验收。

在 Policy/RBAC、认证、审计、故障、性能和业务验收全部有证据前，不得声明
production-ready，也不得自行部署或切换生产流量。

完成后运行完整质量命令，输出生产上线验收报告并停止，等待项目负责人做上线决定。
````
