# 真实语义资料接入指南

## 1. 目标

将外网 synthetic Catalog 换成有版本、可审计的真实
`field_catalog_enrich.csv`，并用 MCP 自动读取的 Mapping 校验实际物理 schema，
同时保持 Agent、API 和页面不变。

内网接入的核心不是“CSV 能读进来”，而是证明：

- 字段在相关月份真实存在且物理类型可用；
- 字段的业务含义和允许操作有来源；
- POC 阶段严格执行 Catalog 自带的 access/sensitivity；
- 指标绑定到正确字段和版本；
- 未知字段默认不可查询；
- 编译后的模型是 LLM、Resolver、Validator 和 Evidence 共用的唯一版本。

## 2. 输入及责任人

| 输入 | 必需内容 | 建议 owner |
|---|---|---|
| `field_catalog_enrich.csv` | 语义主资料：字段、描述、别名、类型提示、操作、caveat、access/sensitivity | Catalog 版本信息 |
| 多月 Mapping | MCP `list_indices/get_mapping` 自动返回的实际物理 schema | 不要求人工维护第二份 Mapping |
| `metric_registry.yaml` | 公式版本、绑定、状态集合、舍入、owner | 报表/数据 owner |
| `value_dictionary.yaml` | 维值/状态值/别名/未知策略 | 业务 owner |
| `policy.yaml` | POC 技术控制：blocked/review、只读和查询限制 | 现有配置；不是生产 RBAC |

生产 Policy/RBAC 已明确单列为可选生产化工作，不阻塞 I1。I1～I3 必须标记
`production_policy_rbac_status=pending`，不得声称已完成生产安全审批。

真实文件的存储和分支策略遵循银行内部规范。本仓库的 Mock 文件仅用于格式参考。

## 3. Catalog 导入

### 3.1 先做只读检查

记录：

- 文件来源、版本、生成时间、owner、编码、分隔符；
- 行数、列名、重复 field path；
- 是否包含内部敏感描述或样例值；
- `status`、`Status`、`pushStatus`、`letterStatus`、`ackFlag` 的真实物理命名；
- 时间字段、Channel、Route、provider/carrier、`statusCode/status_code`；
- 字段是否跨月份一致。

不要把真实数据值加入 Catalog；值字典也只存业务允许的代码/枚举定义。

### 3.2 `candidate_role`

即使真实 CSV 包含 `candidate_role`，编译器也必须继续在入口彻底忽略。禁止：

- 用它作为字段用途、安全或 Prompt 候选；
- 将它复制到新列；
- 在 Import Report、hash、Evidence 中暴露其值；
- 因内网文件依赖该列而恢复运行时使用。

如内部流程需要该列，只能由编译器外的离线治理流程使用。

### 3.3 字段访问状态

建议真实 Catalog 明确提供：

```text
allowed
blocked
review_required
```

规则：

- Mapping-only 字段：默认 `review_required`；
- Catalog-only 字段：不可查询，Import Report 报错/警告；
- 类型冲突：不可查询；
- 缺少安全分类：`review_required`；
- blocked：不得进入 Prompt、DSL、结果或 Evidence；
- allowed：POC 可查询，但仍受 `allowed_operations` 和后端技术 Policy 限制；
- Catalog 的 allowed 不等于生产 RBAC 已批准。

禁止批量把新字段设为 allowed 来消除编译警告。

## 4. 获取和比较真实 Mapping

### 4.1 取样范围

Mapping 不是要求业务方人工再整理的一份语义表。I1 通过 MCP `list_indices` 获取
实际月份清单，再用 `get_mapping` 自动读取必要月份。不得调用 count/search/msearch
获取业务数据。

校验范围至少包括：

- 最早保留月份；
- 当前/最近完整月份；
- 默认月份；
- 已知模板或发布变更前后月份；
- 查询会跨越的所有异常月份。

I1 应覆盖当前 POC 允许查询范围或明确的变更边界，而不只是一份 July Mapping。

### 4.2 保存方式

保存的是 Mapping schema 快照，不是 document hits。每份快照应有：

```text
index
retrieved_at
source_tool/version
mapping_hash
reviewer
```

内网 URL、认证头和证书不得写入快照。

### 4.3 Mapping drift

至少比较：

- 字段新增/删除；
- `keyword/text/date/numeric/object` 类型变化；
- keyword 子字段有无；
- date format；
- object/nested 变化；
- doc_values、index、normalizer；
- 字段 path 大小写变化。

处理原则：

| Drift | 行为 |
|---|---|
| 新字段 | `review_required`，等待 Catalog 补充 |
| 字段删除 | 涉及月份不可用或 QueryPlan 拆分；不得静默查询 |
| 可兼容扩展 | 记录版本并测试 |
| 不兼容类型变化 | 停止相关跨月查询，明确 not_answerable |
| keyword 子字段变化 | 按月份能力处理或禁用 group/sort |
| 时间格式变化 | 停止并由 owner 确认，不做猜测 cast |

不要通过 `script`、`runtime_mappings` 或宽松字符串转换掩盖 drift；当前 Validator
明确禁止这些能力。

## 5. 指标和字段绑定

### `failure_rate.v1`

`failure_rate.v1` 定义已经由项目负责人确认，不在 I1 重新询问。I1 只验证真实
生命周期字段是否绑定为 `status`，并确保 `statusCode/status_code` 不得绑定到 v1。

对账内容：

```text
success set = SENT, INPROGRESS
failed set = FAILED, ACKFAIL
other = null + unknown + remaining values
denominator = all filtered documents
retry/duplicate = included
zero denominator = null
rounding = ROUND_HALF_UP, 2 decimals
```

生产报表对账属于 I3。若 I3 证明真实报表口径不同，则创建
`failure_rate.v2`，写明：

- 新公式；
- 原因；
- owner/批准人；
- 生效日期和适用月份；
- v1/v2 共存或迁移策略；
- 对账 fixture。

### 运营商失败率

必须等待真实 carrier 字段、code 字段和码表。新增独立指标，不修改
`failure_rate.v1`。详见 [项目背景](PROJECT_BACKGROUND.md) 和
[决策日志](DECISION_LOG.md) 的 O09/O10。

## 6. 编译和发布

推荐流程：

```text
真实 Catalog + MCP Mapping snapshots + Metric + Dictionary + POC technical Policy
→ SemanticCompiler
→ Import Report
→ 人工复核 conflicts/review_required
→ 生成 immutable semantic model version/hash
→ 测试
→ 批准
→ 配置 CHATBI_SEMANTIC_MODEL_VERSION
```

语义版本建议包含内部发布号，不用文件修改时间充当版本。

`CompiledSemanticModel` 必须被以下组件共享：

- `StructuredLLMClient`；
- `SemanticResolver/Retriever`；
- `QueryDslValidator`；
- health/runtime metadata；
- Evidence 的模型版本。

禁止 LLM 使用新模型而 Agent/Validator 仍使用旧模型。

## 7. 测试

### 编译测试

- CSV schema、编码、重复行；
- `candidate_role` 全路径隔离；
- Mapping/Catalog missing/conflict；
- mapping-only 默认 review；
- blocked/review 不进入 allowed 检索；
- metric binding 类型/操作合法；
- 模型版本/hash 可重现；
- 多月 Mapping drift fixtures。

### 安全测试

对 Catalog 中每个 blocked 字段做字符串和别名扫描：

```text
semantic prompt context
AnalysisPlan field selection
QueryPlan
Query DSL
MCP request
raw normalization
KPI/table/chart/summary
Evidence/log
```

### 业务测试

- 时间字段在 `[from,to)` 和 Asia/Hong_Kong 下正确；
- 每个允许维度支持的 filter/group/sort 与 Mapping 一致；
- status trim/upper；
- null/unknown/retry/duplicate；
- 跨月字段存在性和结果合并；
- 真实报表对账。

Golden 场景必须从 `/api/chat` 进入，不能直接调用 Metric Engine 冒充 E2E。

## 8. 完成门禁

I1 完成需要：

- 来源、owner 和版本清楚；
- Import Report 无未解释 fatal conflict；
- 所有 Mapping-only/未分类字段为 review；
- Catalog 的 access/sensitivity 被严格执行；
- 多月 drift 有处理结论；
- `candidate_role` 隔离测试通过；
- blocked 全路径扫描为零；
- LLM/Agent/Validator 使用同一模型版本；
- 真实文件没有凭证和客户数据。

生产 Policy/RBAC 不属于 I1～I3 的 POC 完成 Gate；需要生产化时再在可选
Production 阶段补齐。
