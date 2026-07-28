# 内网 AI 交接运行手册

## 1. 使用目的

本手册面向在银行内网继续本项目的 AI 开发代理和复核人员。外网交付已经搭好
Mock-first 全链路和真实依赖注入边界；内网任务不是重写系统，而是用有证据的真实
实现替换 Mock 依赖，并证明业务口径、安全和故障行为仍然成立。

任何 AI 接手后，必须先完成只读认知阶段。不能看到 `mock` 字样就立即全局替换，
也不能根据字段名猜业务语义。

## 2. 接手时的强制动作

### 2.1 完整研读

按 [文档索引](DOCUMENT_INDEX.md) 的“内网 AI 必读顺序”逐份阅读。还需阅读：

- `app/agent/service.py`：主流程和停止点；
- `app/agent/contracts.py`：AnalysisPlan、QueryPlan、Evidence；
- `app/semantic/compiler.py` 与 `app/semantic/models.py`：语义输入和安全状态；
- `app/intent/structured_client.py`：真实 LLM 契约；
- `app/gateway/mcp.py`：真实 MCP 窄接口；
- `app/query/validator.py`：DSL 强制规则；
- `app/metrics/engine.py`：确定性指标；
- 相关测试，确认系统通过什么证据保护边界。

阅读后先输出“内网接手认知报告”，得到项目负责人确认后才能改代码。报告模板：

```text
项目/分支/提交：
接手日期：

一、我理解的业务目标和主链路
二、冻结决策（逐项列 Decision ID）
三、已找到的内网真实资料及其位置、版本、owner
四、尚未找到的资料及被阻塞能力
五、本阶段只计划修改的文件
六、不会修改的架构边界
七、计划执行的测试与对账
八、数据和凭证保护方式
九、停止条件与需业务确认的问题
```

### 2.2 建立来源清单

所有“真实”结论都必须有来源。清单至少包含：

| 资料 | 最低证据 | 不得替代为 |
|---|---|---|
| 内网 LLM 调用 | 已批准项目代码、平台说明、配置 owner | 记忆中的 SDK 用法 |
| Field Catalog | 语义主资料：原始 CSV、版本/日期、access/sensitivity | Mock CSV 或字段名猜测 |
| Mapping | MCP 自动返回的物理 schema，覆盖代表月份 | 人工重复维护的第二份语义表 |
| MCP Tool | 实际 tool schema、成功/错误样例 | 自造工具名或参数 |
| Failure Rate | v1 定义已经冻结；I3 只找脱敏聚合对账结果 | 重新询问或改写 v1 |
| 生产 Policy | 单列可选生产化；I1～I3 明确标记 pending | 把 POC access 冒充生产批准 |
| Carrier code | 三运营商版本化码表和生效期 | LLM 常识或网上码表 |

清单中记录来源路径时不要把 token、内网 URL、证书内容或生产数据复制进仓库。

## 3. 内网接入原则

### 3.1 保持不变

- `/api/chat` 请求/响应契约；
- `AnalysisPlan → Resolver → QueryPlan → Validator → Gateway → Metric → QA`；
- Tool 由程序规则选择；
- 前端只渲染结构化结果；
- `[from,to)`、时区集中配置和跨月 Index 解析；
- blocked/review-required fail closed；
- Metric Engine 独占公式；
- 不使用 PPL、Generic API、自由 Tool loop。

### 3.2 允许替换

- `semantic_sources/field_catalog_enrich.csv`；
- 编译用 Mapping 来源和版本；
- Metric Registry、值字典、Policy 配置；
- `StructuredLLMTransport` 的内网实现；
- `AllowedMCPToolClient` 的内网实现；
- 应用 bootstrap/依赖注入；
- 生产 Session、认证、审计和部署适配；
- 新增、版本化且已批准的指标。

### 3.3 必须先停止并确认的情况

- 同一字段在 Catalog 和 Mapping 类型冲突；
- 月份间同名字段类型或聚合能力不一致；
- Catalog 字段缺少 access/sensitivity 且无法安全设为 review_required；
- LLM 平台不支持可靠的 structured output，且没有批准的校验/重试方案；
- MCP 只提供 Generic API 或会绕过 Index/字段 allowlist；
- 报表与 `failure_rate.v1` 对账不一致；
- `statusCode` 码表没有版本、生效日期或 unknown 策略；
- 真实结果包含客户级明细，而当前问题只需聚合；
- 测试失败被怀疑是业务语义变化，而不是普通代码缺陷。

停止不等于把整个项目标记失败。应明确指出哪个阶段、哪个能力被阻塞，已经获得
哪些证据，以及需要谁作答。

## 4. 分阶段交接流程

### I0：认知与资料盘点

只读；完成研读、来源清单、未决项和数据处理方案。不得接真实数据。

### I1：真实 Semantic Model

以真实 Catalog 为语义主资料；仅通过 MCP `list_indices/get_mapping` 自动获取
多月 Mapping 做物理 schema/drift 校验；未知字段设为 `review_required`；生成
Import Report；解决重复、缺失、类型冲突和指标绑定。生产 Policy/RBAC 不阻塞 I1。
详见 [真实语义资料接入](REAL_SEMANTIC_ONBOARDING.md)。

### I2：真实 LLM + OpenSearch MCP

同一阶段完成两项现成能力的适配：先研读批准的内网参考项目并实现 provider
transport；再记录实际 MCP Tool schema，实现五项窄能力和统一错误归一化。
LLM 仍只生成 `AnalysisPlan` 和总结，业务模块不得直接调用 MCP。完成后必须用
真实依赖从同一个 `/api/chat` 入口跑通端到端场景。详见
[真实 LLM 接入](REAL_LLM_INTEGRATION.md)与
[真实 OpenSearch MCP 接入](REAL_OPENSEARCH_MCP_INTEGRATION.md)。

### I3：指标对账与 POC 最终验收

使用批准的、最小化脱敏聚合结果逐日、逐 Channel、逐 Route 对账。不同口径新增
版本，不修改 `failure_rate.v1` 的历史含义；同时完成 Golden 场景、澄清、
空结果、Policy、错误和前端验收。有完整运营商码表时可在本阶段追加
`carrier_failure_rate.v1`，码表缺失不阻塞通用 ChatBI POC。

### 可选 Production：生产化门禁

当目标从 POC 升级为生产时，再补齐生产 Policy/RBAC、认证、持久化 Session、
日志脱敏、故障演练、限流、性能、安全扫描和业务验收。只有这些证据齐全，
才可以将环境状态描述为 production-ready。

详细勾选项见 [内网执行清单](INTRANET_EXECUTION_CHECKLIST.md)。

## 5. 修改范围矩阵

| 目标 | 首选修改点 | 不应修改 |
|---|---|---|
| 换真实 LLM | 新建内网 transport；bootstrap 注入 | Query planner、Metric Engine |
| 换真实 Catalog | semantic source/安全配置 | 硬编码 resolver |
| 换真实 Mapping | 编译输入适配和版本快照 | 绕过 Compiler |
| 接 MCP | `AllowedMCPToolClient` 实现、bootstrap | Agent 直接 call tool |
| 改业务指标 | 新 Metric 版本和测试 | LLM Prompt 内写公式 |
| 加生产权限 | Policy/RBAC/部署层 | 只在前端隐藏 |
| 换 React（未来） | 调用相同 API | 后端核心业务模块 |

## 6. 每阶段汇报格式

```text
阶段：
使用的真实来源与版本：
创建/修改文件：
实现能力：
安全影响：
执行测试：
测试结果：
对账结果：
未完成/阻塞：
回滚点：
下一阶段计划：
```

禁止把多阶段变化混在一次汇报中。失败测试必须原样记录失败类别，不得只写
“大部分通过”。

## 7. 数据与秘密处理

- 优先使用 schema、聚合样例和脱敏 fixture，不复制 document hits；
- 真实 CSV 若含内部字段信息，按内网仓库分级要求存放；
- 密钥只从获批 secret 管理或运行环境取得；
- 日志记录 request/run ID、耗时、模型/工具版本、错误类别，不记录 token、
  客户值、完整 Prompt、完整 DSL 参数值或原始响应；
- Evidence 仍需经过字段级安全清理；
- 测试 fixture 必须 synthetic，不能从生产抽样后直接提交。

## 8. 交接结束判定

内网 AI 必须能用证据回答：

1. 每个可查询字段为何允许、来自哪个真实 Mapping/Catalog 版本；
2. LLM 请求经过哪个批准的 client，结构化结果如何验证；
3. 每个 MCP 调用实际使用哪个 Tool，错误如何归一化；
4. 每个指标版本的公式、owner、对账记录和生效范围；
5. blocked 字段为何无法进入 Prompt、DSL、结果和 Evidence；
6. 多月份 Mapping drift 如何处理；
7. 如何一键退回 Mock 或上一个批准配置而不改 Agent/API/UI。

任一项只能靠“代码看起来应该可以”回答时，交接尚未完成。
