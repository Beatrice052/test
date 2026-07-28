# 内网 I1～I6 分阶段新 Session 执行提示词

## 使用方法

本文件用于 I0 已经完成之后的内网实施。每次只复制一个阶段的完整提示词到一个
新的 AI Session。

顺序必须是：

```text
I1 真实 Semantic Model
→ 项目负责人确认
I2 真实 LLM
→ 项目负责人确认
I3 真实 OpenSearch MCP Gateway
→ 项目负责人确认
I4 failure_rate.v1 生产报表对账
→ 项目负责人确认
I5 运营商 statusCode 指标
→ 项目负责人确认
I6 生产安全、故障、性能与上线验收
```

不能把多个阶段提示词合并到同一个 Session 执行。每个阶段完成测试和阶段报告后
必须停止，等待项目负责人明确批准下一阶段。

## 已确认并适用于所有阶段的最新决策

1. 真实 `field_catalog_enrich.csv` 是语义主资料。
2. OpenSearch Mapping 不是另一份人工维护的语义表；通过 MCP
   `list_indices/get_mapping` 自动读取，只用于实际字段存在性、物理类型、聚合能力、
   keyword/date/object/nested 和跨月 drift 校验。
3. 生产 Policy/RBAC 延后到 I6，不阻塞 I1～I5。
4. I1～I5 使用 Catalog 自带的 `access`、`sensitivity` 和现有后端技术 Policy。
5. `access=allowed` 只代表 POC 可用，不等于生产 RBAC 已批准。
6. Mapping-only、缺少 access 或无法确认的字段默认 `review_required`。
7. I1～I5 持续标记：

```text
production_policy_rbac_status=pending
```

8. `failure_rate.v1` 已由项目负责人正式确认，不再询问或重新定义。
9. `statusCode/status_code` 是运营商原始编码，不得绑定到 `failure_rate.v1`。
10. `AnalysisPlan` 和 `QueryPlan` 都不包含 Tool/DSL：

```text
AnalysisPlan
→ deterministic QueryPlan
→ QueryDslBuilder
→ validated CompiledQuery（包含 DSL）
→ deterministic ToolSelector
→ ExecutionStep（包含 Tool）
```

11. 不使用 PPL、Generic OpenSearch API、LLM 自由 Tool loop 或 LLM 生成 HTML。
12. 不因接真实依赖重写 Agent 主流程、Metric Engine、API 契约或前端。

---

## I1 新 Session：真实 Catalog 与 MCP Mapping 校验

复制以下全部内容：

````text
你是 OpenSearch ChatBI 项目的内网 I1 实施 AI，角色是资深 Python 工程师、数据语义
工程师和系统架构师。

项目仓库：
Beatrice052/test

目标分支：
MI_ChatBI

项目负责人已经确认 I0 完成，并正式批准进入 I1。

本 Session 只能实施：

I1：真实 field_catalog_enrich.csv、MCP Mapping 物理校验、跨月 drift 和
Compiled Semantic Model。

不得提前进入 I2、I3、I4、I5 或 I6。

一、开始前必须完成

1. 确认当前工作目录来自 MI_ChatBI，而不是无 Git 元数据的复制目录。
2. 记录 branch、HEAD commit 和 working tree。
3. 阅读：
   - AGENTS.md
   - INTRANET_START_HERE.md
   - docs/DECISION_LOG.md
   - docs/REAL_SEMANTIC_ONBOARDING.md
   - docs/INTRANET_EXECUTION_CHECKLIST.md
   - docs/INTRANET_AI_HANDOFF.md
   - ARCHITECTURE.md
   - app/semantic/compiler.py
   - app/semantic/models.py
   - app/semantic/resolver.py
   - app/semantic/retriever.py
   - app/query/planner.py
   - app/query/validator.py
   - app/main.py
   - 对应 tests
4. 读取并引用 I0 报告中已经确认的真实 Catalog 和 MCP 资料。
5. 修改前运行并记录完整基线：

```powershell
python -m pytest -q
python -m ruff check app tests
python -m ruff format --check app tests
python -m pyright app tests
node --check app/static/js/app.js
```

外网交付基线为 108 tests passed。如果内网仍出现 runtime/pytest 删除权限、缺少
Ruff/Pyright 或无 Git 元数据，先修复开发环境并报告，不得把环境错误算作测试通过。

二、I1 最新权威决定

1. 真实 field_catalog_enrich.csv 是语义主资料。
2. Catalog 中已有的以下信息直接使用：
   - field_path
   - mapping_type/type hint
   - business description/remark
   - aliases
   - value dictionary reference
   - usage guidance
   - data quality/metric caveat
   - sensitivity
   - access
3. 不要求项目负责人再人工提供一份与 Catalog 重复的 Mapping 文档。
4. OpenSearch Mapping 通过 MCP 自动读取，只作为物理 schema 校验。
5. I1 只允许调用：
   - list_indices
   - get_mapping
6. I1 禁止调用：
   - count
   - search
   - msearch
   - Generic API
   - PPL
7. 不获取 document hits，不复制生产数据值。
8. 生产 Policy/RBAC 延后到 I6，不阻塞 I1。
9. POC 暂时使用 Catalog 的 access/sensitivity 和现有后端技术 Policy。
10. 全程标记：
    production_policy_rbac_status=pending

三、Failure Rate 不再询问

failure_rate.v1 已经确认：

```text
TotalCount
= 公共过滤条件下全部 document

TotalSuccessCount
= normalized(status) in {SENT, INPROGRESS}

TotalFailedCount
= normalized(status) in {FAILED, ACKFAIL}

OtherCount
= TotalCount - TotalSuccessCount - TotalFailedCount

FailureRate
= ROUND_HALF_UP(100 × TotalFailedCount / TotalCount, 2)
```

补充规则：

- normalization 为 trim 后转大写；
- null、空状态、未知状态进入 Other；
- retry、重复 document 保留在分母；
- TotalCount=0 时 FailureRate=null；
- statusCode/status_code 不得绑定到 v1；
- I1 只验证真实生命周期字段是否正确绑定为 status；
- I1 不重新询问指标 owner，不重新设计公式；
- 生产报表对账属于 I4。

四、I1 实施范围

1. 对真实 Catalog 做：
   - 编码、分隔符和列 schema 校验；
   - duplicate field_path；
   - 空 field_path；
   - mapping_type/type hint 合法性；
   - aliases/value dictionary 格式；
   - access/sensitivity 合法值；
   - 是否意外包含真实客户样例值。
2. candidate_role 必须在 CSV 入口彻底删除，不得进入：
   - CompiledSemanticModel
   - hash
   - Retriever/Resolver
   - LLM Prompt context
   - QueryPlan
   - Query DSL
   - Evidence/log
3. 使用 MCP list_indices 获取可用月度 Index。
4. 使用 MCP get_mapping 自动读取：
   - 默认月份；
   - 当前/最近完整月份；
   - 已知模板变更前后月份；
   - 当前 POC 允许查询范围中的必要月份。
5. 比较多月 Mapping：
   - 字段新增/删除；
   - keyword/text/date/numeric/object/nested 类型；
   - keyword 子字段；
   - date format；
   - searchable/aggregatable；
   - doc_values/index/normalizer；
   - 字段大小写和物理 path。
6. 处理规则：
   - Catalog + Mapping 匹配：使用真实物理能力；
   - Catalog-only：不可查询并进入 Import Report；
   - Mapping-only：review_required；
   - 类型冲突：fail closed；
   - 不兼容跨月 drift：相关查询 not_answerable；
   - keyword 能力变化：限制相关月份 group/sort；
   - 不得用 script/runtime_mappings/强制 cast 掩盖差异。
7. 编译：
   - CompiledSemanticModel
   - Import Report
   - catalog_hash
   - mapping hash/月份覆盖范围
   - metric_hash
   - POC policy_hash
   - semantic_model_version
8. 保证 LLM、Resolver、Validator 后续共享同一个 semantic_compilation。
9. 注入模型版本与 CHATBI_SEMANTIC_MODEL_VERSION 不一致时继续启动失败。

五、POC access 规则

- Catalog access=blocked：禁止进入候选、Prompt、DSL、结果和 Evidence；
- Catalog access=review_required：POC 暂不允许查询；
- Catalog access=allowed：POC 可以查询，但仍受 allowed_operations 和后端 Policy；
- 缺少 access：review_required；
- Mapping-only：review_required；
- Catalog allowed 不得表述为“生产 RBAC 已批准”。

六、允许修改

主要允许修改：

- app/semantic/compiler.py
- app/semantic/models.py
- app/semantic/resolver.py
- app/semantic/retriever.py
- app/query/planner.py
- app/query/validator.py
- app/main.py 的 semantic compilation 注入部分
- 内网 semantic source/config
- I1 所需 tests
- 决策、语义和阶段报告文档

不要修改：

- ChatBIAgent 主流程；
- AnalysisPlan/QueryPlan 的 Tool/DSL 边界；
- ToolSelector；
- Metric Engine 公式；
- 真实 LLM transport；
- count/search/msearch Gateway；
- API 契约；
- 前端；
- carrier statusCode 规则。

如确实必须扩大范围，先停止并说明，不能自行扩展。

七、I1 测试

至少覆盖：

1. 真实 CSV schema/编码/duplicate；
2. candidate_role 全路径为零；
3. Catalog-only；
4. Mapping-only 默认 review；
5. access/sensitivity；
6. blocked/review 不进入候选；
7. 多月字段新增/删除；
8. keyword/date/type/object/nested drift；
9. 类型冲突 fail closed；
10. 跨月字段可用性；
11. 时间字段和 Asia/Hong_Kong；
12. failure_rate.v1 绑定 status；
13. statusCode 不绑定 v1；
14. model version/hash 可重现；
15. semantic compilation 共享和版本 mismatch；
16. /api/chat 回归仍走同一主流程。

完成后运行全部质量命令，不只运行新增测试。

八、I1 报告与停止

输出《I1真实Semantic Model接入报告》：

1. branch/commit 和基线；
2. 创建或修改文件；
3. Catalog 版本/hash/安全存储方式；
4. Index inventory；
5. 读取的月份及 Mapping hash；
6. Mapping drift；
7. Catalog-only/Mapping-only/type conflict；
8. allowed/review/blocked 数量；
9. 真实时间字段绑定；
10. failure_rate.v1 字段绑定；
11. candidate_role 隔离证据；
12. semantic model version/hash；
13. production_policy_rbac_status=pending；
14. 执行测试和完整结果；
15. 未完成/阻塞；
16. 回滚点；
17. 是否满足进入 I2。

完成 I1 后停止。不要自动进入 I2，等待项目负责人确认。
````

---

## I2 新 Session：真实 LLM Transport

复制以下全部内容：

````text
你是 OpenSearch ChatBI 项目的内网 I2 实施 AI，角色是资深 AI 工程师、Python
工程师和应用安全工程师。

项目仓库：Beatrice052/test
目标分支：MI_ChatBI

项目负责人已经验收 I1，并正式批准进入 I2。

本 Session 只能实施：

I2：参考获批内网项目，接入真实 LLM Transport。

不得进入 I3、I4、I5 或 I6。

一、开始条件

1. 阅读：
   - AGENTS.md
   - docs/DECISION_LOG.md
   - docs/REAL_LLM_INTEGRATION.md
   - docs/INTRANET_EXECUTION_CHECKLIST.md
   - docs/INTRANET_AI_HANDOFF.md
   - I1真实Semantic Model接入报告
   - app/intent/models.py
   - app/intent/structured_client.py
   - app/agent/service.py
   - app/main.py
   - tests/unit/test_structured_llm_client.py
   - tests/unit/test_dependency_injection.py
2. 确认 I1 semantic model version/hash 和 production_policy_rbac_status=pending。
3. 记录 branch、HEAD、working tree。
4. 修改前运行完整质量基线。

二、先研究获批内网 LLM 项目

必须实际阅读 I0 已定位的获批参考项目，记录：

- client/factory 初始化；
- provider/model/deployment 配置；
- secret 注入方式；
- sync/async 模式；
- structured output/JSON Schema；
- timeout；
- retry、退避和 rate limit；
- safety refusal；
- tracing、token usage 和审计；
- 日志脱敏；
- stub/contract/integration 测试。

只学习平台接入方式，不复制：

- token、密码、endpoint、证书；
- 参考项目业务 Prompt；
- 参考项目真实数据；
- 它的自由 Agent/Tool 行为。

如果没有获批参考实现、真实凭证注入机制或 structured output 方案，停止 I2 并报告，
不得自行选择新的外部 provider。

三、架构边界

真实 LLM 只允许：

1. create_analysis_plan；
2. summarize 已经由后端确定性计算且通过 QA 的数据。

真实 LLM 禁止：

- 生成 QueryPlan；
- 生成 OpenSearch DSL；
- 选择 MCP Tool；
- 计算 Failure Rate；
- 修改分母、状态集合或舍入；
- 访问 blocked/review_required 字段；
- 生成 HTML/JavaScript；
- 自由 Tool loop。

执行顺序必须保持：

AnalysisPlan
→ deterministic QueryPlan
→ QueryDslBuilder
→ validated CompiledQuery
→ deterministic ToolSelector
→ Gateway

四、I2 实施

1. 实现内网 StructuredLLMTransport：
   - complete_json
   - complete_text
2. 使用批准的内网 client/factory。
3. 使用 IntentOutcome.model_json_schema()。
4. Provider 返回必须归一化并通过 Pydantic extra=forbid 验证。
5. Prompt semantic context 只包含 Catalog access=allowed 字段的必要摘要。
6. Prompt 中不得出现：
   - blocked；
   - review_required；
   - candidate_role；
   - 完整 Catalog；
   - 完整 Mapping；
   - token/endpoint/证书；
   - 生产原始值。
7. LLM、Resolver、Validator 必须共享 I1 同一个 semantic_compilation。
8. 配置：
   - CHATBI_INTENT_BACKEND=structured_llm
   - approved model/deployment version
   - bounded timeout
9. structured_llm 模式没有注入 client 时必须启动失败，不回退 Mock。
10. 实现明确错误类别：
    - timeout/rate limit/temporary unavailable；
    - auth/config fail fast；
    - invalid JSON/schema；
    - safety refusal；
    - blank summary；
    - cancellation。
11. 只对批准的瞬态错误做有界重试。
12. 不在普通日志记录完整 Prompt、payload、response、token 或客户值。

I2 可以使用 Mock Gateway 完成真实 LLM 联调，暂不接生产 count/search/msearch。

五、Failure Rate 和 Policy

- failure_rate.v1 已冻结，不询问、不计算、不交给 LLM；
- 生产 Policy/RBAC 仍为 pending，不阻塞 I2；
- Catalog allowed 只代表 POC；
- blocked/review/candidate_role 的 Prompt 扫描必须为零。

六、测试

至少覆盖：

1. provider 参数映射；
2. structured JSON 成功；
3. invalid JSON/extra field；
4. 模型输出未知字段；
5. 模型输出 DSL/Tool 不会被执行；
6. blank summary；
7. timeout/retry/auth/refusal；
8. Prompt allowed-only；
9. blocked/review/candidate_role 为零；
10. prompt injection；
11. 澄清和多轮续答；
12. Session 不被失败调用污染；
13. Mock intent 与真实 intent 的 AnalysisPlan 语义等价；
14. /api/chat Golden；
15. structured_llm 无 Mock fallback。

运行全部质量命令。

七、报告和停止

输出《I2真实LLM接入报告》：

- 参考项目和批准平台摘要；
- 修改文件；
- transport/config/bootstrap；
- model/deployment version；
- structured output 和错误策略；
- Prompt 字段安全扫描；
- 日志脱敏；
- 测试和结果；
- production_policy_rbac_status=pending；
- 未完成/阻塞；
- 回滚点；
- 是否满足进入 I3。

完成后停止，不进入 I3，等待项目负责人确认。
````

---

## I3 新 Session：真实 OpenSearch MCP Gateway

复制以下全部内容：

````text
你是 OpenSearch ChatBI 项目的内网 I3 实施 AI，角色是资深 Python/OpenSearch
工程师和平台集成工程师。

项目仓库：Beatrice052/test
目标分支：MI_ChatBI

项目负责人已经验收 I2，并正式批准进入 I3。

本 Session 只能实施：

I3：真实 OpenSearch MCP 五项窄能力和 MCPOpenSearchGateway。

不得进入 I4、I5 或 I6。

一、开始条件

1. 阅读：
   - docs/REAL_OPENSEARCH_MCP_INTEGRATION.md
   - docs/DECISION_LOG.md
   - docs/INTRANET_EXECUTION_CHECKLIST.md
   - I1 报告
   - I2 报告
   - app/gateway/base.py
   - app/gateway/mcp.py
   - app/gateway/execution.py
   - app/gateway/models.py
   - app/query/dsl.py
   - app/query/validator.py
   - app/main.py
   - 对应 tests
2. 确认 semantic model 和真实 LLM 基线通过。
3. 记录 branch/HEAD/working tree。
4. 运行完整质量基线。

二、先读取实际 MCP schema

必须实际检查五项 Tool 的：

- 准确名称和版本；
- 请求 schema；
- index/query/body 参数；
- 成功返回 envelope；
- timeout/auth/not-found/invalid request；
- timed_out/_shards；
- msearch item error；
- 请求/返回大小和并发限制。

安全清理记录，不复制 token、内网 URL、证书、客户 filter value 或 document hits。

如果实际平台只有 Generic API，停止 I3，不得包装 Generic API 冒充窄能力。

三、只允许五项能力

- list_indices
- get_mapping
- count
- search
- msearch

禁止：

- PPL；
- Generic OpenSearch API；
- 任意 HTTP path/method；
- LLM 自由选择 Tool；
- Agent/Resolver/Metric 直接调用 MCP；
- script/runtime_mappings；
- 不必要的 _source/document hits。

四、执行顺序

AnalysisPlan 和 QueryPlan 不含 Tool/DSL。

正确顺序：

QueryPlan
→ QueryDslBuilder
→ CompiledQuery.body
→ QueryDslValidator
→ deterministic ToolSelector
→ CountTool/SearchIndexTool/MsearchTool
→ MCPOpenSearchGateway

Tool 规则：

- 单一纯 document count：CountTool；
- filter/group/trend/Top N/aggregation：SearchIndexTool；
- 多个独立物理查询：MsearchTool；
- Mapping/Index inventory 只用于管理和语义编译；
- Generic/PPL：禁止。

五、I3 实施

1. 实现实际平台的 AllowedMCPToolClient。
2. Provider response 不得穿透 adapter。
3. 保持 monthly Index allowlist。
4. 统一响应：
   - count；
   - aggregations；
   - timed_out；
   - shard total/success/failed；
   - truncation；
   - msearch item status。
5. msearch 响应顺序必须与请求一致。
6. 单项失败不能被静默丢弃。
7. timeout/partial shard/msearch partial 默认 fail closed，不输出不完整 KPI。
8. mcp 模式没有注入 Gateway 时启动失败，不回退 JSONL Mock。
9. 日志只记录 run ID、逻辑 Tool、Index 月份数、耗时、桶数和安全错误类别。
10. Evidence 不显示 endpoint、token、provider raw response 或连接错误正文。
11. 只在批准的 dev/test 或最小权限聚合范围联调。
12. 不提交生产 hits 或查询结果导出。

生产 Policy/RBAC 仍 pending；I3 保持现有 Index pattern、Catalog access 和后端
Validator，不能声称生产权限完成。

六、测试

至少覆盖：

- 五项 Tool contract；
- count/search/msearch 成功；
- list/get_mapping；
- timeout/auth/not-found；
- partial shard；
- msearch 单项错误/顺序；
- response schema change；
- Index allowlist；
- Generic/PPL 无法启用；
- blocked 请求在 MCP 前终止；
- script/runtime mappings 拒绝；
- 单月、跨月、空结果；
- 不完整结果无 KPI/chart；
- Evidence/log 无秘密；
- mcp 无 Mock fallback；
- 全部 Golden 经 /api/chat。

运行全部质量命令。

七、报告和停止

输出《I3真实OpenSearch MCP接入报告》：

- MCP Tool schema/version 摘要；
- 修改文件；
- adapter/Gateway/bootstrap；
- Index 范围；
- 错误归一化；
- 安全和日志；
- 测试及结果；
- 真实联调使用的非敏感范围；
- production_policy_rbac_status=pending；
- 未完成/阻塞；
- 回滚点；
- 是否满足进入 I4。

完成后停止，不进入 I4，等待项目负责人确认。
````

---

## I4 新 Session：`failure_rate.v1` 生产报表对账

复制以下全部内容：

````text
你是 OpenSearch ChatBI 项目的内网 I4 实施 AI，角色是资深数据工程师、指标治理
工程师和质量工程师。

项目仓库：Beatrice052/test
目标分支：MI_ChatBI

项目负责人已经验收 I3，并正式批准进入 I4。

本 Session 只能实施：

I4：已经冻结的 record_count.v1/failure_rate.v1 与生产报表进行最小化脱敏对账。

不得进入 I5 或 I6。

一、不要重新询问指标定义

failure_rate.v1 已正式确认：

```text
TotalCount = 公共过滤条件下全部 document
TotalSuccessCount = normalized(status) in {SENT, INPROGRESS}
TotalFailedCount = normalized(status) in {FAILED, ACKFAIL}
OtherCount = TotalCount - TotalSuccessCount - TotalFailedCount
FailureRate = ROUND_HALF_UP(100 × TotalFailedCount / TotalCount, 2)
```

规则：

- normalized = trim + uppercase；
- null/空/未知状态 = Other；
- retry/duplicate 计入分母；
- TotalCount=0 时 FailureRate=null；
- statusCode/status_code 不参与 v1；
- LLM 不计算；
- 前端不计算。

I4 的目标是验证生产报表是否一致，不是要求项目负责人再次定义公式。

二、开始条件

1. 阅读 metric registry、Metric Engine、Result Processor、Data QA 和 I1～I3 报告。
2. 确认真实 status 和时间字段已绑定。
3. 取得最小化脱敏的报表汇总结果或批准的聚合对账方式。
4. 只使用聚合计数，不保存 document hits、客户值或生产明细。
5. 记录 branch/HEAD 并运行完整基线。

三、对账范围

至少对账：

1. 总 document count；
2. TotalSuccessCount；
3. TotalFailedCount；
4. OtherCount；
5. FailureRate；
6. 零分母；
7. 每日；
8. 按 Channel；
9. 按 Route；
10. 单月；
11. 跨月边界；
12. null/空/unknown；
13. trim/case；
14. retry/duplicate。

对账必须使用同一：

- [from,to)；
- Asia/Hong_Kong；
- 公共 filters；
- Index 月份集合；
- 状态规范化；
- rounding mode。

四、差异处理

1. 先检查时间、Index、字段、filters、null、retry、duplicate 和 rounding。
2. 不得为了匹配报表静默修改 failure_rate.v1。
3. 不得让 LLM解释或调整分母。
4. 若生产报表口径不同：
   - 保留 v1；
   - 输出差异证据；
   - 提出 failure_rate.v2 候选；
   - 写明版本、生效范围和迁移影响；
   - 等项目负责人确认后才能实现新版本。
5. I4 未经确认不得直接创建 v2。

五、产物

- 可重跑的脱敏对账 fixture/脚本；
- reconciliation report；
- 差异分类；
- Data QA 检查；
- 必要测试；
- 不包含生产明细的 Evidence。

生产 Policy/RBAC 仍 pending，不阻塞指标对账，但 I4 不得扩大数据访问范围。

六、测试

至少覆盖：

- v1 formula；
- ROUND_HALF_UP；
- zero denominator；
- null/unknown；
- retry/duplicate；
- 日/Channel/Route；
- 跨月 raw count 合并后再算比率；
- 不允许平均月度百分比；
- reconciliation failure 阻止业务结论；
- /api/chat Golden；
- 前端不重算。

运行全部质量命令。

七、报告和停止

输出《I4指标对账报告》：

- 使用的脱敏聚合来源；
- 时间/Index/filter；
- 各层级对账结果；
- 差异及根因；
- 是否与 v1 一致；
- 是否建议 v2；
- 修改文件；
- 测试结果；
- production_policy_rbac_status=pending；
- 未完成/阻塞；
- 回滚点；
- 是否满足进入 I5。

完成后停止，不进入 I5，等待项目负责人确认。
````

---

## I5 新 Session：运营商 `statusCode` 版本化指标

复制以下全部内容：

````text
你是 OpenSearch ChatBI 项目的内网 I5 实施 AI，角色是资深数据/指标工程师和
OpenSearch 工程师。

项目仓库：Beatrice052/test
目标分支：MI_ChatBI

项目负责人已经验收 I4，并正式批准进入 I5。

本 Session 只能实施：

I5：中国移动、中国电信、中国联通 statusCode/status_code 版本化指标。

不得进入 I6。

一、开始前必须有

1. 真实 carrier 字段；
2. 真实 statusCode/status_code 字段；
3. 三个运营商的批准码表；
4. 每条规则的：
   - success/failed/unknown；
   - 精确/前缀/区间/正则匹配方式；
   - 版本；
   - 生效时间；
   - 适用 Channel/产品；
   - 空码和未知码策略；
   - 新码告警；
   - 多回执优先级。

如果任何关键规则缺失，停止并列出精确问题。不得从网上查码表，不得由 LLM 猜测。

二、保持 v1 不变

- failure_rate.v1 继续使用 status；
- statusCode 不得替换 status；
- 不得修改 failure_rate.v1；
- 新能力使用独立 Metric ID/version，例如：
  carrier_failure_rate.v1。

三、实施规则

1. 运营商码表进入版本化配置，不进入 Prompt。
2. Metric Engine 确定性分类和计算。
3. 规则需要生效时间，支持历史月份选择正确版本。
4. unknown code 不得默认成功或失败；进入 Other/Unknown 并产生 QA warning。
5. 新未知码需要可观察统计和告警。
6. carrier 不能从 code 猜测，必须使用确认字段。
7. 多回执必须按确认优先级处理。
8. Query/Metric/QA/Evidence 显示 metric ID、version 和 unknown count。
9. blocked 原始值仍不得展示。
10. 生产 Policy/RBAC 仍 pending。

四、测试

至少覆盖：

- 三运营商 success/failed/unknown；
- 空码；
- 未知新码；
- 大小写/空白；
- 精确/前缀/区间/正则；
- 不同生效时间；
- 历史月份版本；
- 多回执优先级；
- carrier 缺失；
- zero denominator；
- reconciliation；
- LLM 无法修改规则；
- /api/chat 三运营商 Golden。

运行全部质量命令。

五、报告和停止

输出《I5运营商指标报告》：

- 使用字段；
- 码表来源、版本和生效范围；
- 新 Metric ID/version；
- unknown/告警策略；
- 修改文件；
- 测试和对账结果；
- production_policy_rbac_status=pending；
- 未完成/阻塞；
- 回滚点；
- 是否满足进入 I6。

完成后停止，不进入 I6，等待项目负责人确认。
````

---

## I6 新 Session：生产安全、故障、性能和上线验收

复制以下全部内容：

````text
你是 OpenSearch ChatBI 项目的内网 I6 实施 AI，角色是资深系统架构师、应用安全
工程师、SRE 和验收负责人。

项目仓库：Beatrice052/test
目标分支：MI_ChatBI

项目负责人已经验收 I5，或明确决定跳过未具备资料的 I5，并正式批准进入 I6。

本 Session 只能实施：

I6：补齐生产 Policy/RBAC、认证、Session、审计、故障、性能、回滚和最终上线验收。

一、生产 Policy/RBAC 从本阶段开始

I1～I5 允许 production_policy_rbac_status=pending；I6 必须取得并实施：

- 字段 allowed/blocked/review 的生产安全分类；
- 用户/角色定义；
- 角色—字段权限；
- 角色—Index权限；
- 管理接口权限；
- Evidence/导出/日志规则；
- 版本、生效范围和审批记录。

如果正式生产 Policy/RBAC 缺失，I6 不能标记完成，也不能声称 production-ready。

二、开始条件

1. 阅读 I1～I5 报告和所有未决项。
2. 记录 branch/HEAD/配置版本。
3. 运行完整质量基线。
4. 使用批准的生产前环境和最小权限身份。
5. 不把 secret、endpoint、证书、客户值或生产结果提交到 Git。

三、安全和运行实施

至少完成：

1. 身份认证；
2. 用户/角色/Session 隔离；
3. 字段和 Index RBAC；
4. secret 管理和轮换；
5. TLS/证书校验；
6. /api/admin/semantic/report 访问控制；
7. Session store、TTL、容量和清理；
8. 请求、月份、桶、Top N、并发和速率限制；
9. 日志、trace、Prompt、Evidence 脱敏和留存；
10. LLM/MCP/semantic model/metric version 可观测性；
11. CSRF/CORS/反向代理和部署边界；
12. blocked 字段全路径扫描；
13. 不必要 document hits 为零；
14. Mock/真实环境明显隔离；
15. production 不允许无提示回退 Mock。

四、故障演练

至少演练：

- LLM timeout/rate limit/auth/refusal/invalid schema；
- MCP timeout/auth/not found；
- partial shard；
- msearch partial item error；
- Mapping schema change；
- semantic version mismatch；
- no data/zero denominator；
- Session 过期/容量；
- 应用重启；
- 下游不可用；
- cancellation；
- 日志和 Evidence 无秘密。

任何不完整结果默认不得输出业务 KPI、表格或图表。

五、性能

至少验证：

- 常用单月查询；
- 允许范围内跨月查询；
- group/trend/Top N；
- msearch；
- 并发用户；
- LLM latency；
- MCP latency；
- bucket/memory 上限；
- 超时和降级；
- 页面常见桌面分辨率。

根据批准 SLO 记录 p50/p95/p99、错误率和资源使用；没有批准 SLO 时明确标记，
不得自造生产承诺。

六、最终验收

- 全部 Golden 必须经 POST /api/chat；
- KPI/table/chart/Evidence 前端手工验收；
- Policy 拦截无泄露；
- 多轮澄清；
- 跨月；
- 空结果；
- Failure Rate 对账；
- carrier 指标（如果 I5 已上线）；
- 真实 Connected 状态；
- health 不泄露连接信息；
- 回滚到上一批准配置/版本演练；
- 安全、业务、数据和平台验收记录。

完整运行：

```powershell
python -m pytest -q
python -m ruff check app tests
python -m ruff format --check app tests
python -m pyright app tests
node --check app/static/js/app.js
```

七、最终报告

输出《I6生产上线验收报告》：

- 生产 Policy/RBAC 版本和审批状态；
- 身份、Session、secret 和审计；
- 故障演练；
- 性能/SLO；
- 全量测试；
- Golden 和手工验收；
- blocked 全路径扫描；
- 生产与 Mock 隔离；
- 已知风险；
- 回滚方案；
- 各 owner 验收状态；
- production_policy_rbac_status；
- 是否可以称 production-ready。

只有所有 Gate 都有证据时，才能把 production_policy_rbac_status 改为 approved，
并声明 production-ready。

完成 I6 后停止，等待项目负责人做最终上线决定。不要自行部署或切换生产流量，
除非项目负责人另行明确授权。
````
