# OpenSearch ChatBI 内网 I3 统一技术升级执行方案

> 使用对象：接手内网真实工程的 AI 开发工程师和项目开发人员。
>
> 当前状态：内网已经完成 I0、I1、I2，I3 尚未开始。
>
> 本文性质：可直接执行的任务说明，不是技术调研或选型比较报告。
>
> 重要边界：外网 `MI_ChatBI` 分支不包含内网 I2，不能用外网代码覆盖内网工程。

---

## 1. 你的任务

在内网现有 I2 代码基础上，完成一个统一的 I3，使 ChatBI 可以使用：

- 内网批准的真实 LLM；
- 真实 `field_catalog_enrich.csv`；
- 真实月度 OpenSearch Index 和 Mapping；
- 真实 OpenSearch MCP；
- 已冻结的指标和安全规则；

完成以下端到端能力：

```text
用户自然语言问题
→ 识别分析意图并处理多轮上下文
→ 解析字段、指标、值、时间和月份 Index
→ LLM 一次生成候选 QueryPlan + Query DSL + ResultContract
→ 后端确定性校验
→ 程序选择 MCP Tool
→ OpenSearchGateway 执行
→ 后端计算指标并做数据质量检查
→ 返回总结、KPI、表格、图表和安全 Evidence
→ 前端在聊天消息中展示
```

I3 是一个连续完成的实施任务，不再拆成多个需要项目负责人逐个批准的 Phase。

如果内网旧 `AGENTS.md`、README 或阶段提示仍写着“LLM 绝对不能生成 DSL”或“必须继续
拆分多个对外 Phase”，仅这两条以本文最新确认口径为准；其他既有安全规则继续有效。
首个文档 checkpoint 应同步清理旧表述，避免后续 AI 收到冲突指令。

开始修改代码前，先做一次简洁的只读审计；项目负责人确认审计后，在同一 Session 中连续
开发、测试和提交。不要每完成一个小模块就暂停。

---

## 2. 开始前先核对的内网事实

不要直接照抄本文中的示例文件名。先检查内网真实工程并确认：

1. 当前分支、HEAD、未提交文件以及 I0～I2 的提交；
2. 当前 `/api/chat` 调用链和依赖注入方式；
3. AnalysisPlan、QueryPlan、Validator、Metric Engine、Session 的现有实现；
4. 内网批准项目中的真实 LLM Client 调用方式；
5. 真实 `field_catalog_enrich.csv` 的列、样例和版本；
6. 当前能够访问的月份 Index 和命名方式；
7. MCP `tools/list`、Tool 参数、返回结构和错误样例；
8. 真实 Mapping 与 Catalog 的差异；
9. `failure_rate.v1` 当前代码和测试；
10. 当前完整测试命令及已知失败。

第一轮只读审计只需要输出：

```text
当前主流程
可直接复用的模块
需要增强的模块
需要新增的模块
真实 LLM/Catalog/Mapping/MCP 接入点
计划修改的文件
验证这些修改的测试
真实阻塞项
```

不要写大篇背景分析或重新做技术选型，只报告与当前内网实施直接相关的事实。

---

## 3. 不得改变的业务和安全规则

### 3.1 数据范围和时间

- 数据按月拆分为 `tbl_os_sub_message_YYYY_MM` 一类 Index；
- 当前可以查询全部月份，不是只能查询 2026 年 7 月；
- 用户未指定时间时，默认查询 2026 年 7 月完整月份；
- 用户指定时间时，按时间范围选择相应月份 Index；
- 业务时区为 `Asia/Hong_Kong`；
- 所有时间区间使用左闭右开 `[start_time, end_time)`；
- 前端必须显示实际使用的时间范围；
- 物理时间字段由编译后的 Semantic Model 决定，不能在代码多处硬编码。

### 3.2 记录数量

`record_count.v1` 是 OpenSearch document count：

- 一条 document 等于一条记录；
- 不按 `messageId` 或其他业务 ID 去重；
- Retry、重复 document 和空字段 document 都计数；
- 未来需要去重时新增独立指标，不修改现有定义。

### 3.3 Failure Rate

```text
metric_id: failure_rate
version: failure_rate.v1

TotalCount
= 公共过滤条件下的全部 document 数量

TotalSuccessCount
= normalize(status) 属于 SENT 或 INPROGRESS 的 document 数量

TotalFailedCount
= normalize(status) 属于 FAILED 或 ACKFAIL 的 document 数量

OtherCount
= TotalCount - TotalSuccessCount - TotalFailedCount

FailureRate
= ROUND_HALF_UP(100 × TotalFailedCount / TotalCount, 2)
```

补充规则：

- `normalize(status)` 为 trim 后转大写；
- null、空字符串、未知状态和其他状态进入 `OtherCount`；
- 空状态不能被转换为 `INPROGRESS`；
- Retry 和重复 document 继续进入分母；
- `TotalCount = 0` 时 FailureRate 返回 `null`，不能返回 `0%`；
- 最终公式只由 Metric Engine 执行；
- LLM 和前端都不能重新计算；
- 真实报表口径不同需要新增指标版本，不能静默修改 v1。

### 3.4 status 和 statusCode

- `failure_rate.v1` 使用 `status`；
- `statusCode`/`status_code` 是运营商返回的原始编码；
- 当前不能使用 `statusCode` 替代 `status` 计算 v1；
- 中国移动、电信、联通的独立失败率要等内网提供码表和业务定义；
- 以后实现运营商指标时必须新增版本化配置和对账测试。

### 3.5 Catalog、Mapping 和 Policy

真实 `field_catalog_enrich.csv` 是业务语义来源，至少负责：

- 物理字段名；
- 业务含义和别名；
- 数据类型；
- 是否可筛选、分组、聚合和展示；
- canonical value 或枚举信息；
- 安全分类；
- 指标和时间角色；
- 版本信息。

OpenSearch Mapping 是物理运行时事实，负责验证：

- 字段是否真实存在；
- keyword/text/date/numeric 类型；
- multifield；
- nested 结构；
- 字段在各月份 Index 是否一致。

运行时必须把 Catalog 与真实 Mapping 对齐。字段缺失、类型冲突或关键月份不一致时
fail-closed，不执行查询。

生产完整 Policy/RBAC 本轮暂缓，但以下规则不能削弱：

- `candidate_role` 在 CSV 导入时彻底丢弃；
- `candidate_role` 不得进入模型、Prompt、字段候选、DSL、结果或 Evidence；
- blocked 字段不得进入 Prompt、DSL、结果、图表、总结或 Evidence；
- Mapping 中存在但 Catalog 未分类的字段默认 `review_required`；
- 禁止把消息正文、客户姓名、手机号、邮箱、银行账号和客户标识提供给 LLM；
- 不得提交真实数据、凭证、Token、证书、内部 URL 或生产查询结果。

### 3.6 查询边界

- 只使用 OpenSearch Query DSL；
- 不使用 PPL；
- 不开放 `GenericOpenSearchApiTool`；
- 不使用通用 Tool Registry；
- 不让 LLM 查看全部 MCP Tool 后自由尝试；
- 不使用自由 Agent/Tool Loop；
- 当前不引入 LangGraph；
- 当前不把 OpenSearch `QueryPlanningTool` 作为运行时依赖；
- 所有业务查询只能通过 `OpenSearchGateway`。

---

## 4. 最终主流程

整个系统只保留下面这一条主链：

```text
POST /api/chat
  │
  ├─ 1. Session Resolver
  │     读取必要上下文、pending clarification 和最近 Snapshot
  │
  ├─ 2. Intent & Clarification
  │     生成或更新 AnalysisPlan
  │     不完整则返回澄清，不查询
  │
  ├─ 3. Semantic Resolver
  │     解析 metric/field/value/time/index_scope
  │     应用 Catalog、Mapping 和基础 Policy
  │
  ├─ 4. Query Generator
  │     真实 LLM 一次返回 QueryPlan + DSL + ResultContract
  │
  ├─ 5. Query Service
  │     做合同、语义、安全、成本和跨层一致性校验
  │     程序选择 Count/Search/Msearch
  │
  ├─ 6. OpenSearchGateway
  │     通过真实 MCP 执行只读查询
  │
  ├─ 7. Analytics Service
  │     归一化结果、计算指标、Data QA、生成安全 Claims
  │
  └─ 8. Response Builder
        生成总结、KPI、表格、ChartSpec、warnings、Evidence
        保存不可变 Snapshot
```

任何节点失败都必须返回明确状态：

```text
answered
needs_clarification
blocked
not_answerable
error
```

不允许失败后自动扩大范围或静默查询全部数据。

---

## 5. 简化后的模块职责

不要为了名字完全一致而重构 I2 目录。以内网现有模块为基础，把职责归并为以下八类。

| 模块 | 唯一职责 |
|---|---|
| Orchestrator | 串联主流程、控制状态和终态，不实现业务公式 |
| LLM Adapter | 复用内网批准调用方式，提供 typed structured output |
| Semantic Service | 编译 Catalog、校验 Mapping、解析字段/值/时间/Index |
| Query Service | 生成上下文、调用 LLM、校验 QueryBundle、选择 Tool |
| OpenSearchGateway | 封装 Mock/MCP 的 list/mapping/count/search/msearch |
| Analytics Service | 结果归一化、Metric Engine、Data QA、Claims |
| Session Service | 消息、澄清、AnalysisPlan、Snapshot、TTL、reset |
| API/UI | FastAPI 契约和结构化前端渲染 |

实现规则：

- I2 已有同职责模块时直接增强，不复制第二套；
- 不为了满足目录示例而大规模移动文件；
- 不建立多个 Orchestrator；
- 不把每个小动作都包装成独立 Agent；
- 不让业务模块直接调用供应商 LLM SDK 或 MCP Tool；
- 模块之间使用严格 Pydantic model 或现有等价 typed contract。

---

## 6. 三个核心数据合同

### 6.1 AnalysisPlan

AnalysisPlan 只描述用户希望分析什么：

```json
{
  "question_type": "metric_by_dimension",
  "metric_id": "failure_rate",
  "metric_version": "failure_rate.v1",
  "dimensions": ["channel"],
  "filters": [],
  "time_range": {
    "start": "2026-07-01T00:00:00+08:00",
    "end": "2026-08-01T00:00:00+08:00"
  },
  "granularity": null,
  "top_n": null,
  "sort": null,
  "presentation_intent": "bar"
}
```

AnalysisPlan 禁止出现：

- MCP Tool 名称；
- OpenSearch DSL；
- Index 物理名称；
- LLM 自己定义的指标公式。

AnalysisPlan 不完整时必须澄清。例如：

```text
用户：看看最近的失败情况。
系统：你希望按 Channel、Route，还是按日期趋势查看？
用户：按 Channel。
系统：结合 pending clarification 继续原分析。
```

### 6.2 ResolvedAnalysis

Semantic Service 把 AnalysisPlan 转成只包含已确认引用的 ResolvedAnalysis：

```json
{
  "analysis_plan_id": "plan-001",
  "metric": {
    "id": "failure_rate",
    "version": "failure_rate.v1",
    "required_fields": ["status"]
  },
  "fields": {
    "time": "synthetic_or_real_time_field",
    "dimensions": ["channel"],
    "filters": []
  },
  "resolved_values": [],
  "time_range_utc": {
    "start": "2026-06-30T16:00:00Z",
    "end": "2026-07-31T16:00:00Z"
  },
  "index_scope_ref": "scope-001",
  "semantic_fingerprint": "sha256:..."
}
```

真实 Index 列表由程序保存并通过 `index_scope_ref` 引用，不让 LLM编造 Index。

### 6.3 QueryGenerationBundle

LLM 在一次 structured-output 调用中返回：

```json
{
  "analysis_plan_id": "plan-001",
  "semantic_fingerprint": "sha256:...",
  "query_plan": {
    "metric_id": "failure_rate",
    "metric_version": "failure_rate.v1",
    "group_by": ["channel"],
    "filters": [],
    "time_field": "synthetic_or_real_time_field",
    "time_range_utc": {
      "start": "2026-06-30T16:00:00Z",
      "end": "2026-07-31T16:00:00Z"
    },
    "top_n": null,
    "sort": []
  },
  "queries": [
    {
      "query_id": "q1",
      "purpose": "failure_rate_components_by_channel",
      "index_scope_ref": "scope-001",
      "body": {
        "size": 0,
        "query": {
          "bool": {
            "filter": [
              {
                "range": {
                  "synthetic_or_real_time_field": {
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
            "terms": {"field": "channel", "size": 50},
            "aggs": {
              "status_counts": {
                "terms": {
                  "field": "status",
                  "size": 50,
                  "missing": "__MISSING__"
                }
              }
            }
          }
        }
      },
      "result_contract": {
        "shape": "grouped_status_buckets",
        "group_key_path": "aggregations.by_channel.buckets[*].key",
        "total_count_path": "aggregations.by_channel.buckets[*].doc_count",
        "status_buckets_path": "aggregations.by_channel.buckets[*].status_counts.buckets",
        "status_key_path": "key",
        "status_count_path": "doc_count",
        "missing_status_key": "__MISSING__"
      }
    }
  ]
}
```

示例中的 `channel`、`status` 和时间字段只是合同说明，不代表已确认的生产物理字段。
内网实现必须使用 ResolvedAnalysis 中已经通过 Catalog/Mapping 校验的具体字段及其
keyword multifield。

要求：

- strict schema，未知字段拒绝；
- QueryPlan、DSL 和 ResultContract 同一次生成；
- LLM 输出不含 Tool；
- LLM 输出不含最终 FailureRate；
- LLM 不能改变 ResolvedAnalysis；
- `analysis_plan_id` 和 `semantic_fingerprint` 必须原样返回；
- aggregation alias 使用项目固定常量；
- 只返回聚合结果需要的字段，不返回原始 `_source`。

Failure Rate 查询不得在 DSL 中直接计算 success/failed/rate。推荐的固定查询形态是：

```text
公共 time/filter
→ 可选 group/date bucket
→ 每个 bucket 的 total doc_count
→ status terms 子聚合（missing = "__MISSING__"）
→ Metric Engine 对 status key 做 trim + upper
→ 计算 success/failed/other/rate
```

这样不需要 OpenSearch script，也不会把指标公式交给 LLM。`status` 聚合使用的 keyword
字段、bucket size 和 missing 处理由 Metric Registry 与 Semantic Model 固定，不由 LLM
自由决定。若 `sum_other_doc_count > 0`，说明 status buckets 不完整，Data QA 必须阻止
生成完整 Failure Rate 或返回明确 partial warning。

---

## 7. Query Generator 的输入和输出

### 7.1 输入内容

Query Generator 只接收完成当前查询所需的最小上下文：

```text
已确认 AnalysisPlan
ResolvedAnalysis
目标月份的安全 Mapping 摘要
与本问题相关的 Catalog 字段
Metric Registry 中对应指标的查询需求
允许的 DSL 节点
成本限制
固定 aggregation alias
ResultContract schema
少量经审核的 query examples
```

不得放入：

- 全量 Catalog；
- blocked/review_required 字段；
- `candidate_role`；
- 客户敏感值；
- 凭证和内部 URL；
- 全部会话历史；
- MCP Tool Registry；
- 任意可执行代码。

### 7.2 真实 LLM 接入

内网参考已经批准项目的调用方式，复用：

- 认证和 Secret 管理；
- endpoint 和 model deployment；
- timeout/retry；
- 代理和证书；
- trace ID；
- structured output；
- token 和延迟统计；
- 日志脱敏；
- 并发限制。

业务代码只依赖统一接口，例如：

```python
class QueryGenerationLLM(Protocol):
    async def generate_query_bundle(
        self,
        context: QueryGenerationContext,
    ) -> QueryGenerationBundle:
        ...
```

推荐配置：

```text
temperature = 0 或平台最低稳定值
structured_output = required
max_repair_attempts = 1
prompt_version = recorded
model_id/version = recorded
```

### 7.3 Query Repair

只允许对以下局部问题 repair 一次：

- 非法 JSON；
- schema 字段缺失；
- aggregation alias 错误；
- ResultContract 路径与 DSL 不一致；
- 明确可定位的类型错误。

以下问题不能通过 repair 猜测：

- 未知业务字段；
- 未知指标；
- blocked/review_required 字段；
- 时间范围不确定；
- Index 不确定；
- canonical value 不确定；
- Mapping drift；
- semantic fingerprint 改变；
- 用户意图本身不完整。

这些情况返回 clarification、blocked 或 not_answerable。

---

## 8. Query Service 的五道校验门

不要把校验分散在 Prompt、Agent 和 Gateway 中。统一由 Query Service 顺序执行。

### Gate 1：合同校验

- 输出是单一 JSON 对象；
- strict Pydantic/JSON Schema 通过；
- 不允许 extra fields；
- query ID 唯一；
- ResultContract 完整；
- `analysis_plan_id` 和 fingerprint 一致。

### Gate 2：语义与安全校验

- metric ID/version 已注册；
- 所有字段来自本次 ResolvedAnalysis；
- `candidate_role` 全链路为零；
- blocked/review_required 字段为零；
- status/statusCode 使用正确；
- filter 值来自 canonical resolver；
- QueryPlan 没有扩大用户问题。

### Gate 3：时间、Index 和 Mapping 校验

- 时间字段是已确认字段；
- 使用 `gte` 和 `lt`；
- UTC 边界与 Time Resolver 完全一致；
- `index_scope_ref` 来自程序；
- Index 属于允许的数据族；
- 字段在所有目标月份存在且类型兼容；
- LLM 没有生成物理 Index 名。

### Gate 4：DSL 安全与成本校验

第一版允许：

- `bool.filter`；
- `term`、`terms`；
- `range`；
- `exists`；
- `terms` aggregation；
- `date_histogram`；
- `filter/filters` aggregation；
- Metric Registry 明确允许的简单 metric aggregation；
- 受限 `bucket_sort`。

默认禁止：

- `match_all`；
- `script`、`script_score`、`runtime_mappings`；
- `query_string`、`wildcard`、`regexp`、`fuzzy`；
- neural、k-NN；
- arbitrary pipeline aggregation；
- raw `_source`；
- raw hits；
- profile/explain；
- 未列入白名单的节点。

还要限制：

- 最大月份数；
- 最大时间跨度；
- 最大 bucket；
- terms size；
- Top N；
- timeout；
- msearch 子查询数。

### Gate 5：跨层一致性

- QueryPlan 中的 filter、group、time、sort、Top N 在 DSL 中等价；
- DSL 不包含 QueryPlan 之外的条件；
- ResultContract 的路径在 DSL 中真实存在；
- Failure Rate 查询能够返回每个目标 bucket 的 total 和完整 status buckets；
- aggregation alias 与项目常量一致；
- 选择的 Tool 与查询形态兼容。

任何 Gate 不通过都不能执行查询。修复后的 Bundle 从 Gate 1 重新检查。

如果真实 MCP/OpenSearch 支持 Validate Query API，可以把它作为额外语法检查；它不能
替代上述五道校验。

---

## 9. Tool 选择和 OpenSearchGateway

Tool 由程序根据已经校验的查询形态选择：

| 查询形态 | Tool |
|---|---|
| 单纯 document count | `CountTool` |
| 过滤、聚合、分组、趋势、Top N | `SearchIndexTool` |
| 多个相互独立查询 | `MsearchTool` |
| 启动或运维时发现 Index | `ListIndexTool` |
| 启动、版本变化或 drift 检查 Mapping | `IndexMappingTool` |
| 任意通用 API | 禁止 |

`ListIndexTool` 和 `IndexMappingTool` 是语义编译、启动检查或 drift 检查能力，不是让
LLM 在业务问答过程中自由选择的查询 Tool。

业务模块只调用：

```python
class OpenSearchGateway:
    def list_indices(self): ...
    def get_mapping(self, index: str): ...
    def count(self, indices: list[str], query: dict): ...
    def search(self, indices: list[str], body: dict): ...
    def msearch(self, requests: list[dict]): ...
```

内网 `MCPOpenSearchGateway` 必须：

- 把程序参数转换为真实 MCP schema；
- 只读；
- Index allowlist；
- timeout/retry/circuit breaker；
- 区分参数错误、权限、timeout、partial shard 和 unavailable；
- 清理 MCP 原始错误；
- 返回统一 typed result；
- 记录 query hash，不记录敏感原始内容。

多个查询部分失败时必须返回 partial warning 或整体 error，不能把缺失子查询补零后当成
完整成功。

---

## 10. Analytics Service

Analytics Service 合并以下职责，避免建立过多相互调用的小模块：

```text
OpenSearch response
→ NormalizedResult
→ Metric Engine
→ Data QA
→ deterministic Claims
```

### 10.1 NormalizedResult

屏蔽 Mock 与真实 MCP 返回格式差异，统一为：

- 查询 ID；
- group key；
- 时间 bucket；
- total 和 raw status buckets；
- source aggregation path；
- partial/timed_out/truncated 标志。

### 10.2 Metric Engine

- 指标配置版本化；
- 只接受 NormalizedResult；
- 确定性计算；
- 对每个 raw status bucket 执行 trim + upper；
- 按 v1 状态集合累加 success/failed，剩余进入 other；
- 不读取 LLM 总结；
- 不让 DSL 或前端计算最终 FailureRate；
- 保存分子、分母、OtherCount 和舍入后的值。

### 10.3 Data QA

至少检查：

- `success + failed + other = total`；
- count 不为负；
- 分组汇总和总计是否一致；
- 是否有 unknown/null status；
- 是否 partial、timeout 或 truncated；
- 空分母是否返回 null；
- 多月结果是否存在 Mapping/字段不一致；
- ResultContract 是否完整解析。

### 10.4 Claims 和总结

程序从 MetricResult 生成可回溯的结构化 Claim：

```json
{
  "type": "ranking",
  "subject": "SMS",
  "metric_id": "failure_rate",
  "metric_version": "failure_rate.v1",
  "value": 12.34,
  "unit": "percent",
  "evidence_refs": ["result:q1:row:0"]
}
```

LLM Summary 只能根据 Claims、warnings、scope 和 metric definition 表达，不能生成新的
数值、排名或原因。

总结 grounding 失败时使用程序模板总结，不影响 KPI、表格和图表返回。

---

## 11. 多轮、澄清和结果复用

Session 第一版继续使用内存 Store，但必须保存：

- `session_id`；
- 当前必要消息；
- pending clarification；
- 最近 AnalysisPlan；
- 最近 QueryPlan；
- 最近不可变 AnalysisSnapshot；
- TTL；
- reset 状态。

不要把全部聊天历史无限放进 Prompt。

### 11.1 本轮如何判断

每轮先判断：

```text
NEW_QUERY
REFINE_QUERY
ANSWER_CLARIFICATION
PRESENTATION_ONLY
RESET
```

多个动作可以在同一轮合并。例如“按 Route，并且只看 SMS”应形成一个 typed patch，
不能拆成两个彼此覆盖的计划。

### 11.2 什么时候澄清

以下信息缺失且会改变查询时必须澄清：

- 指标；
- 分组维度；
- 用户明确要求但无法解析的时间；
- 模糊业务值对应多个 canonical value；
- 字段歧义；
- Top/趋势问题缺少必要方向或粒度。

### 11.3 什么时候可以复用

Snapshot 已包含相同：

- metric/version；
- time/index scope；
- filters；
- group/granularity；
- 所需列和完整数据；

且 Snapshot 未过期、未 partial、未 truncated 时，可以只改变表格/图表展示，不重新查询。

只要改变指标、过滤、分组、时间、粒度或 Top N 数据需求，就必须重新生成查询。

每个回答保存新的 Snapshot，并记录 `answer_id` 和 `parent_answer_id`，防止后续追问引用
了错误结果。

---

## 12. API、前端和 Evidence

### 12.1 API

保持：

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

响应保留现有字段，并允许增加：

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
  "kpis": [],
  "table": {"columns": [], "rows": []},
  "chart": {},
  "warnings": [],
  "evidence": {}
}
```

前端只消费结构化字段，不能解析 LLM 生成的 HTML。

### 12.2 前端

继续使用：

```text
FastAPI + Jinja2 + HTML + CSS + Vanilla JavaScript + 本地 ECharts
```

职责：

- Jinja2 只渲染页面骨架；
- JavaScript 负责聊天、loading、session 和组件渲染；
- ECharts 只渲染后端 ChartSpec；
- 前端不计算指标；
- 不增加 Node 构建流程；
- 不使用外部 CDN。

后端只输出受控 ChartSpec：

```json
{
  "type": "bar",
  "title": "Failure Rate by Channel",
  "x_field": "channel",
  "y_fields": ["failure_rate"],
  "unit": "percent",
  "data": []
}
```

前端使用固定 adapter 支持：

- KPI；
- table；
- bar；
- horizontal bar；
- line。

禁止返回或执行原生 JavaScript、`eval()`、动态 formatter 或不受控 ECharts option。

### 12.3 Evidence

Evidence 默认折叠，只显示清理后的：

- AnalysisPlan；
- Resolved fields；
- QueryPlan；
- Tool 和程序选择理由；
- Query DSL；
- ResultContract；
- Metric ID/version；
- validation 摘要；
- repair/fallback；
- 聚合结果摘要；
- QA warnings；
- semantic/mapping/config fingerprint。

不得显示：

- system prompt；
- chain-of-thought；
- 全量 Catalog/Mapping；
- blocked 字段；
- 敏感值；
- 凭证；
- MCP 原始错误堆栈；
- 未清理 raw hits。

---

## 13. 配置、降级和可观测性

### 13.1 集中配置

以下参数集中配置并在启动时校验：

```yaml
query_generation:
  mode: shadow
  provider: application_llm
  max_repair_attempts: 1
  allow_llm_match_all: false
query_limits:
  max_indices: 12
  max_time_range_days: 366
  max_buckets: 500
  max_terms_size: 100
  max_msearch_queries: 5
sessions:
  ttl_seconds: 1800
  max_sessions: 1000
  max_turns: 20
visualization:
  allowed_types: [bar, horizontal_bar, line, table]
  max_points: 500
```

示例上限要根据内网容量测试调整。配置版本/hash 进入 trace 和 Evidence。

### 13.2 渐进启用

保留现有确定性 Query Builder，但只作为：

- `shadow` 对照；
- 已注册简单场景的受控 fallback；
- Golden oracle；
- emergency switch。

运行模式：

```text
deterministic
shadow
guarded
primary
```

推荐先 shadow，再 guarded。未经真实对账和安全验收，不直接切 primary。

生成失败时：

```text
已注册简单场景
→ 使用同一语义和校验链的 deterministic fallback

其他场景
→ clarification / not_answerable / error
```

不得 fallback 到 `match_all`。

### 13.3 Trace

每轮记录：

- request ID 和 session hash；
- AnalysisPlan ID；
- semantic/mapping/config fingerprint；
- model 和 prompt version；
- query generation mode；
- validation error code；
- repair/fallback；
- Tool；
- query shape hash；
- gateway/metric/总延迟；
- token；
- QA 和 response status。

不得记录敏感用户值、全量 Prompt、raw hits、凭证或 blocked 字段。

---

## 14. 统一 I3 的实施顺序

首轮只读审计获确认后，按下面顺序连续实施。它们是同一个 I3 内部 checkpoint，不是需要
项目负责人逐个批准的新 Phase。

### Checkpoint 1：受控查询核心

完成：

- 对齐并精简核心 typed contracts；
- 接入真实 LLM Adapter；
- 接入真实 Catalog 和 Mapping drift 检查；
- 完成 Semantic Resolver；
- 一次生成 QueryPlan + DSL + ResultContract；
- 完成五道 Query Gate；
- 完成程序 ToolSelector；
- 增加 shadow/guarded 配置。

测试：

- contract/unit；
- semantic/compiler/mapping；
- candidate_role/blocked；
- QueryBundle；
- DSL allowlist/denylist；
- QueryPlan/DSL/ResultContract 一致性；
- repair/fallback。

### Checkpoint 2：完整聊天主链

完成：

- MCPOpenSearchGateway；
- Count/Search/Msearch；
- NormalizedResult；
- Failure Rate/record count；
- Data QA；
- Claims/grounded summary；
- Session/clarification/reuse；
- API/Evidence；
- 前端结构化展示。

测试：

- Gateway adapter；
- Metric 对账；
- partial/timeout；
- Session/clarification；
- `/api/chat` Golden；
- 页面和静态资源。

### Checkpoint 3：真实验收和收口

完成：

- 多月份真实查询；
- 真实 LLM structured output 稳定性；
- 真实 Catalog/Mapping drift；
- 真实 MCP 错误处理；
- `failure_rate.v1` 与真实报表对账；
- shadow 差异检查；
- 性能、并发、安全和前端验收；
- 更新内网 README、AGENTS/项目记忆和最终报告。

每个 checkpoint：

- 使用小而可回滚的 commit；
- 运行相关测试；
- 记录一段简洁测试结果；
- 无真实阻塞则继续，不等待项目负责人再次批准。

---

## 15. 必须通过的测试

### 15.1 单元和合同

- Catalog compiler；
- Catalog/Mapping 对齐；
- `candidate_role` 隔离；
- blocked/review_required；
- time/index resolver；
- AnalysisPlan；
- QueryGenerationBundle strict schema；
- 五道 Query Gate；
- ToolSelector；
- ResultContract parser；
- Failure Rate 全部分支；
- Data QA；
- Session TTL/reset/reuse。

### 15.2 Failure Rate

覆盖：

- SENT、INPROGRESS、FAILED、ACKFAIL；
- 大小写和前后空格；
- null、empty、unknown；
- TotalCount=0；
- Retry 和 duplicate；
- Channel、Route、daily；
- 多月份；
- statusCode 不参与；
- `success + failed + other = total`；
- ROUND_HALF_UP 两位。

### 15.3 `/api/chat` Golden

全部通过同一个主入口：

1. 单纯记录数量；
2. 2026 年 7 月各 Channel Failure Rate；
3. SMS 每日趋势；
4. Route 失败 Top N；
5. SMS 和 Email 记录数量比较；
6. 多条件过滤；
7. 跨月份查询；
8. 空结果；
9. 未知值和未知字段；
10. “看看最近的失败情况”触发澄清；
11. “按 Channel”继续原问题；
12. 换图表复用 Snapshot；
13. blocked 字段；
14. prompt injection；
15. malformed/unsafe DSL；
16. MCP timeout/partial failure。

### 15.4 前端手工验收

- 首页显示 Connected/Mock、IndexScope、时间和 Semantic 版本；
- 无刷新聊天；
- loading 和重复提交保护；
- Enter/Shift+Enter；
- 澄清选项和自由输入；
- KPI、table、chart；
- 空结果无误导图；
- Evidence 折叠；
- Clear Conversation；
- 错误提示可理解；
- 常见桌面分辨率无横向滚动；
- 无外部 CDN；
- 无 blocked/raw 数据；
- 前端没有第二套指标公式。

### 15.5 完整质量命令

以内网现有工程实际命令为准，至少运行：

```text
python -m pytest -q
python -m ruff check app tests
python -m pyright app tests
node --check app/static/js/app.js
```

如果工具未安装，按内网工程规范处理，不能把“未运行”报告成“通过”。

---

## 16. 只有这些情况需要停止并询问

- 内网代码与 I2 报告严重不一致；
- 需要改变冻结指标口径；
- 真实 Catalog 缺少完成目标所需的字段语义；
- Mapping 与 Catalog 冲突且无法安全判断；
- MCP 缺少 Count/Search/Msearch 等必需只读能力；
- 真实 LLM 不支持可靠 structured output；
- 需要扩大数据权限或访问敏感字段；
- 需要开放新的高风险 DSL 节点；
- 现有 API 必须做破坏性变更；
- `failure_rate.v1` 与真实报表无法对账。

以下不是阻塞，可以明确记录后继续：

- 生产完整 Policy/RBAC 暂未提供；
- 运营商 statusCode 码表暂未提供；
- carrier failure rate 暂未定义；
- 尚未使用 LangGraph；
- 尚未切 primary；
- 暂未使用数据库持久 Session；
- 暂未迁移 React/Vue。

---

## 17. I3 完成标准

- [ ] 真实 LLM 按内网批准方式接入；
- [ ] 真实 Catalog 生效；
- [ ] 多月份 Mapping drift fail-closed；
- [ ] AnalysisPlan 不含 Tool/DSL；
- [ ] LLM 一次生成候选 QueryPlan + DSL + ResultContract；
- [ ] LLM 不选择、不调用 MCP Tool；
- [ ] 五道 Query Gate 全部实现；
- [ ] 生成失败不会静默 `match_all`；
- [ ] Count/Search/Msearch 由程序选择；
- [ ] 业务代码只调用 OpenSearchGateway；
- [ ] `candidate_role` 和 blocked 字段全链路为零；
- [ ] `failure_rate.v1` 使用 status 并完成真实对账；
- [ ] statusCode 未被错误用于 v1；
- [ ] Metric Engine 是唯一最终计算位置；
- [ ] Session 澄清和 Snapshot 复用正确；
- [ ] Claims/Summary 有结果证据；
- [ ] 前端只渲染结构化结果；
- [ ] Evidence 完整且安全；
- [ ] Golden 全部通过 `/api/chat`；
- [ ] 安全、故障、性能和前端验收通过；
- [ ] deterministic emergency switch 可用；
- [ ] 内网 README、AGENTS/项目记忆与真实实现一致；
- [ ] 一份 I3 最终报告完成。

---

## 18. 最终报告格式

I3 全部完成后只提交一份最终报告：

```text
1. 最终架构和实际主流程
2. 创建/修改文件
3. 真实 LLM 接入方式
4. 真实 Catalog、Mapping 和多月 Index
5. QueryPlan + DSL + ResultContract 生成及五道校验
6. ToolSelector 和真实 MCP Gateway
7. Metric、Data QA、Session、前端和 Evidence
8. 测试命令与真实结果
9. Golden 和 Failure Rate 对账结果
10. 性能、已知限制和仍待补资料
11. feature flag、回滚方法和 commit 清单
```

不要为每个小模块生成单独 Phase Report。

---

## 19. 给内网新 Session 的开工提示词

```text
请继续完成内网 OpenSearch ChatBI 的统一 I3。

先完整阅读《OpenSearch ChatBI 内网 I3 统一技术升级执行方案》，然后检查内网当前分支、
I0～I2 代码、报告和测试。外网 GitHub 不包含内网 I2，不能用外网代码覆盖内网工程。

第一轮只做只读审计，不修改代码。请简洁说明：
- 当前 /api/chat 主流程；
- 可以复用、需要增强和需要新增的模块；
- 真实 LLM、field_catalog_enrich.csv、Mapping、月度 Index 和 MCP 接入点；
- 计划修改的文件和测试；
- 真实阻塞项。

技术决策已经确认：
- AnalysisPlan 只描述业务意图，不含 Tool/DSL；
- 在语义、字段、值、时间和 IndexScope 确定后，真实 LLM 一次生成候选
  QueryPlan + OpenSearch DSL + ResultContract；
- 候选必须通过后端五道确定性校验；
- Tool 由程序选择，LLM 不选择、不调用 MCP；
- failure_rate.v1 使用 status，最终公式只由 Metric Engine 计算；
- statusCode 留给以后运营商码表；
- 支持全部月份，2026年7月只是默认范围；
- 不使用 PPL、Generic API、自由 Tool Loop、LangGraph 或 QueryPlanningTool；
- 生产完整 Policy/RBAC 暂缓，但 candidate_role 和 blocked 字段隔离不能削弱。

我确认审计后，请在同一 Session 中连续完成 I3，不再拆多个对外 Phase。按文档三个
checkpoint 使用小 commit 和相关测试；只有遇到文档第16节的真实阻塞才暂停。

完成后运行完整质量命令和 /api/chat Golden，只提交一份 I3 最终报告。
```
