# 项目背景与业务目标

## 1. 为什么做这个项目

银行消息发送数据按月存放在 OpenSearch Index 中。业务人员希望通过自然语言快速
查看记录数量、失败率、Channel/Route 分组、每日趋势和 Top N，同时能够知道系统
到底选了什么字段、执行了什么查询、使用了哪个指标版本。

项目目标不是一个通用 OpenSearch 聊天机器人，而是受控 ChatBI：

```text
自然语言问题
→ 结构化分析意图
→ 经过安全审查的字段和指标
→ 确定性 Query DSL
→ 允许的 OpenSearch MCP Tool
→ 确定性指标与 Data QA
→ 总结/KPI/表格/图表/Evidence
```

## 2. 已确认业务范围

### 月度 Index

Index 按月份拆分：

```text
tbl_os_sub_message_YYYY_MM
```

`tbl_os_sub_message_2026_07` 只是默认时间与 Mock 示例，不是业务唯一数据源。
内网可以拿到全部月份数据，QueryPlan 必须根据用户提问选择一个或多个 Index。

### 记录数量

- 一条 OpenSearch document 等于一条记录；
- 不按 messageId 或其他业务 ID 去重；
- retry、重复、空字段仍计数；
- 如果以后需要唯一消息数，新增 `unique_message_count`，不能改 record count。

### 通用 Failure Rate

当前冻结：

```text
metric_id: failure_rate
version: failure_rate.v1

TotalCount
= 公共过滤条件下全部 document

TotalSuccessCount
= normalized(status) in {SENT, INPROGRESS}

TotalFailedCount
= normalized(status) in {FAILED, ACKFAIL}

OtherCount
= TotalCount - TotalSuccessCount - TotalFailedCount

FailureRate
= ROUND_HALF_UP(100 * TotalFailedCount / TotalCount, 2)
```

- normalized 是 trim 后转大写；
- null、空、未知和其他状态进入 Other；
- null 不能展示为 INPROGRESS 后又计入成功；
- retry 和重复 document 保留在分母；
- `TotalCount=0` 时返回 null；
- LLM 无权修改公式。

### 运营商状态码

`statusCode`/`status_code` 是运营商原始返回编码，不是通用生命周期状态。

中国移动、中国电信、中国联通的失败率需要内网补充：

- carrier 字段；
- code 字段真实命名；
- 每个运营商 success/failed/unknown code；
- 精确/前缀/区间/正则匹配方式；
- 规则版本和生效日期；
- 未知新码的告警方式。

外网版本故意对运营商专项失败率返回 `not_answerable`。

### 时间

- 业务时区：`Asia/Hong_Kong`；
- 全部区间：`[start_time,end_time)`；
- 用户未指定：默认 2026 年 7 月完整月；
- 用户指定：按输入范围；
- 真实物理时间字段由 Semantic Model 绑定。

## 3. 安全背景

外网没有真实敏感字段清单，只实现机制和 Mock Policy。Mock blocked：

```text
消息正文
客户姓名
手机号
邮箱
银行账号
客户标识
```

生产安全配置必须在内网重新完成。任何 Mapping-only 字段默认
`review_required`，完成字段 owner 和数据分类后才能 allowed。

Blocked 字段不得进入：

```text
候选
LLM Prompt
Analysis/Query field selection
Query DSL
OpenSearch result
metric input
table/chart/summary
Evidence/log
```

## 4. 技术边界

采用：

```text
Python + FastAPI + Pydantic
Jinja2 + HTML + CSS + Vanilla JavaScript
local ECharts
OpenSearch Query DSL
```

明确不采用：

```text
PPL
Generic OpenSearch API
通用 Tool Registry
LLM 自由 Tool loop
多 Agent
LLM 生成 HTML/JavaScript
前端重算指标
```

当前不需要 LangGraph。流程是有限、明确的状态机；如果未来出现持久化 checkpoint、
人工审批恢复或复杂并行子图，再单独评估。

## 5. 外网已经完成什么

- 三个月、552 条 synthetic documents；
- 可替换 Semantic Compiler；
- Mock Mapping/Catalog/Metric/Policy；
- bounded Intent adapter；
- 跨月 QueryPlan 和 Query DSL；
- DSL Validator；
- Count/Search/Msearch ToolSelector；
- Mock Gateway 和 MCP adapter seam；
- Metric Engine、Data QA、Evidence；
- Session、多轮澄清、API 和真实聊天页面；
- 真实 LLM/MCP 依赖注入边界；
- 108 项自动化测试（以最新测试报告为准）。

## 6. 内网 POC 必须完成什么

- 研读已有技术方案并保持冻结边界；
- 学习一个批准的内网 LLM 项目并实现真实 transport；
- 使用真实 `field_catalog_enrich.csv`；
- 获取并对齐真实多月 Mapping；
- 接通真实 OpenSearch MCP Tool；
- 与真实报表对账；
- 经 `/api/chat` 完成端到端、故障和前端验收。

生产 Policy/RBAC、认证、持久化 Session、正式审计和生产压测属于可选生产化
工作，不阻塞 POC。运营商 status code 码表就绪时可追加独立指标版本；资料不齐时
也不阻塞通用 ChatBI POC。
