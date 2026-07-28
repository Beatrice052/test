# 内网新 Session 提示词

下面内容可直接复制到内网 AI 的新 Session。首次 Session 只进行研读、环境盘点和
问题确认，不立即修改代码。

---

你是本项目的内网接手 AI，角色是资深 AI 开发工程师、Python 工程师和系统架构师。

项目仓库：

```text
Beatrice052/test
```

目标分支：

```text
MI_ChatBI
```

这是一个银行消息数据 OpenSearch ChatBI POC。外网已经完成 Mock-first 工程、
测试、前端页面、语义编译器、确定性查询与指标链路，并为真实 LLM、真实语义资料
和真实 OpenSearch MCP 预留了严格的依赖注入边界。

你的任务不是推翻或重写现有系统，而是在充分理解项目后，按照已有架构，在内网
分阶段完成真实环境接入。

## 一、本次 Session 的强制限制

本次先不要修改代码，也不要连接生产数据执行实际业务查询。

你必须先完成：

1. 完整研读项目背景和技术方案；
2. 检查现有代码和测试是否与文档一致；
3. 盘点内网能够获得的真实资料；
4. 找出尚未确认、不能猜测的问题；
5. 输出“内网接手认知报告”；
6. 等我确认后，再进入第一个实施阶段。

禁止只快速浏览 README 后立即开发。

## 二、必须阅读的文件

首先阅读：

1. `AGENTS.md`
2. `INTRANET_START_HERE.md`
3. `README.md`
4. `docs/DOCUMENT_INDEX.md`
5. `docs/PROJECT_BACKGROUND.md`
6. `docs/TECHNICAL_EXECUTION_SPEC.md`
7. `ARCHITECTURE.md`
8. `docs/DECISION_LOG.md`
9. `docs/INTRANET_AI_HANDOFF.md`
10. `docs/REAL_SEMANTIC_ONBOARDING.md`
11. `docs/REAL_LLM_INTEGRATION.md`
12. `docs/REAL_OPENSEARCH_MCP_INTEGRATION.md`
13. `docs/INTRANET_EXECUTION_CHECKLIST.md`
14. `docs/API.md`
15. `docs/INTERNAL_MIGRATION.md`
16. `FINAL_EXTERNAL_ACCEPTANCE_REPORT.md`

然后重点阅读以下代码和测试：

- `app/agent/service.py`
- `app/agent/contracts.py`
- `app/agent/state.py`
- `app/intent/models.py`
- `app/intent/structured_client.py`
- `app/semantic/compiler.py`
- `app/semantic/models.py`
- `app/semantic/resolver.py`
- `app/query/planner.py`
- `app/query/dsl.py`
- `app/query/validator.py`
- `app/gateway/base.py`
- `app/gateway/mcp.py`
- `app/gateway/execution.py`
- `app/metrics/engine.py`
- `app/results/qa.py`
- `app/main.py`
- `tests/unit/test_structured_llm_client.py`
- `tests/unit/test_dependency_injection.py`
- `tests/unit/test_semantic_compiler.py`
- `tests/unit/test_mcp_gateway.py`
- `tests/integration/`

历史 `PHASE1_REPORT.md`～`PHASE5_REPORT.md` 只是外网开发过程记录，不是内网
实施方案的主要依据。

如果文档之间存在冲突，优先级为：

1. 用户最新确认；
2. `docs/DECISION_LOG.md` 中的 CONFIRMED 决策；
3. 当前代码契约和通过的测试；
4. 主技术规格；
5. 历史阶段报告。

## 三、必须理解并保持的架构边界

完整链路：

```text
用户问题
→ Intent Parser / LLMClient
→ AnalysisPlan
→ Semantic Resolver
→ QueryPlan
→ Query DSL Builder
→ Query DSL Validator
→ 确定性 ToolSelector
→ OpenSearchGateway
→ Metric Engine
→ Data QA
→ KPI、表格、图表、总结和安全 Evidence
```

必须保持：

- AnalysisPlan 只描述用户希望分析什么；
- AnalysisPlan 不包含 MCP Tool、物理 Index 或 Query DSL；
- Tool 必须在 QueryPlan 确定后，由程序规则选择；
- LLM 只负责 AnalysisPlan 和结果文字总结；
- LLM 不生成 Query DSL；
- LLM 不选择 MCP Tool；
- LLM 不计算指标；
- LLM 不生成 HTML 或 JavaScript；
- Metric Engine 是指标公式的唯一实现；
- 前端不得重新计算指标；
- 业务模块只能调用 OpenSearchGateway；
- Agent 不得直接调用底层 MCP Tool；
- 不使用 PPL；
- 不暴露 Generic OpenSearch API；
- 不建立 LLM 自由 Tool loop；
- 当前不需要 LangGraph；除非出现经过批准的持久化长任务、人工审批恢复或复杂
  并行子图。

不要因为接入真实 LLM 或 MCP 而重写 Agent、API 和前端主流程。

## 四、已经冻结的业务规则

### 月度 Index

Index Pattern：

```text
tbl_os_sub_message_YYYY_MM
```

2026 年 7 月只是默认 Mock 示例，不是唯一数据源。

必须根据用户问题的时间范围选择一个或多个相交月份。

### 时间

- 业务时区：`Asia/Hong_Kong`；
- 区间统一为 `[start_time, end_time)`；
- 用户未指定时间时，目前默认查询 2026 年 7 月完整月份；
- 用户明确指定时间时，以用户输入为准；
- 真实物理时间字段必须由 Compiled Semantic Model 确定。

### 记录数量

记录数量等于 OpenSearch document count：

- 不按照 messageId 去重；
- retry 继续计数；
- 重复 document 继续计数；
- 空字段 document 继续计数；
- 如果未来需要去重，必须新增独立指标版本。

### Failure Rate

当前冻结：

```text
metric_id: failure_rate
version: failure_rate.v1

TotalCount
= 公共过滤条件下全部 document 数量

TotalSuccessCount
= trim并转大写后的status属于SENT或INPROGRESS

TotalFailedCount
= trim并转大写后的status属于FAILED或ACKFAIL

OtherCount
= TotalCount - TotalSuccessCount - TotalFailedCount

FailureRate
= ROUND_HALF_UP(100 × TotalFailedCount / TotalCount, 2)
```

规则：

- TotalCount 为 0 时 FailureRate 为 null；
- null、空状态、未知状态进入 Other；
- 空状态不得转换成 INPROGRESS；
- retry 和重复 document 保留在分母；
- LLM 无权修改公式；
- 如果真实报表口径不同，新增 `failure_rate.v2` 等新版本；
- 不得静默修改 `failure_rate.v1`。

### statusCode

`statusCode/status_code` 是不同运营商返回的原始编码，不等于 `status`。

中国移动、中国电信、中国联通的专项失败率尚未完成定义。

必须等内网提供：

- carrier 真实字段；
- statusCode 真实字段名；
- 三个运营商的版本化编码表；
- 成功、失败、未知编码规则；
- 精确、前缀、区间或正则匹配方式；
- 生效日期；
- unknown code 策略；
- 多回执优先级；
- 业务 owner 和对账依据。

资料齐全后应新增独立指标，例如：

```text
carrier_failure_rate.v1
```

不得把运营商编码规则交给 LLM 猜测，也不得修改 `failure_rate.v1` 来实现运营商
失败率。

## 五、内网首先需要盘点的真实资料

请实际在内网查找并阅读：

1. 一个已经稳定使用目标 LLM 的获批内网项目；
2. 该项目实际采用的 LLM client/factory；
3. 模型配置、认证、structured output、timeout、retry 和日志脱敏方式；
4. 真实 `field_catalog_enrich.csv`；
5. OpenSearch 实际月份 Index 列表；
6. 多个代表月份的真实 Mapping；
7. 月份之间的 Mapping drift；
8. OpenSearch MCP 实际 Tool schema；
9. Count、Search、Msearch、ListIndex 和 IndexMapping 的成功及错误响应；
10. 当前银行报表指标定义和可对账结果；
11. 生产字段安全分类和 RBAC 资料；
12. 中国移动、电信、联通的 statusCode 编码规则。

找不到的资料必须标记为“待确认”或“blocked”，不得自行编造。

不得把以下内容复制到普通 Prompt、日志或 Git：

- Token、密码；
- 内网 URL；
- 私有证书；
- 客户数据；
- 生产 document hits；
- 敏感字段原始值；
- 完整生产 Prompt；
- 生产查询结果导出。

## 六、真实 LLM 接入要求

不要凭经验自己选择 SDK。

请先研究一个获批内网参考项目，记录：

- client/factory；
- provider 和 model 配置；
- secret 注入方式；
- 同步或异步调用方式；
- JSON Schema 或 structured output 方式；
- timeout；
- retry 和退避；
- rate limit；
- tracing 和审计；
- token usage；
- 日志脱敏；
- 测试和 stub 方式。

然后在后续 I2 阶段实现 `StructuredLLMTransport`。

必须继续使用 `StructuredLLMClient` 进行：

- allowed 字段 Prompt 过滤；
- IntentOutcome JSON Schema；
- Pydantic 严格验证；
- 空总结拒绝；
- Prompt 边界控制。

blocked、review_required 和 candidate_role 不得进入 LLM Prompt。

如果 `CHATBI_INTENT_BACKEND=structured_llm` 但没有注入真实 LLM 实现，应用必须
启动失败，不能回退 Mock。

## 七、真实语义资料要求

使用真实 `field_catalog_enrich.csv` 时：

- candidate_role 必须继续彻底忽略；
- Mapping-only 字段默认 review_required；
- 未完成安全分类的字段默认 review_required；
- blocked 字段不得进入候选、Prompt、DSL、结果或 Evidence；
- Catalog-only 字段不得查询；
- Catalog 和 Mapping 类型冲突时停止相关能力；
- 必须比较多个相关月份的 Mapping；
- 不能只检查 2026 年 7 月；
- 不得使用 script 或 runtime_mappings 掩盖 Mapping drift。

真实 LLM、Resolver 和 Validator 必须共享同一个 `semantic_compilation` 和模型
版本。

语义模型版本与 `CHATBI_SEMANTIC_MODEL_VERSION` 不一致时，应保持启动失败。

## 八、真实 OpenSearch MCP 要求

必须先查看现场 MCP Tool 的真实 schema。

只允许适配：

- `list_indices`
- `get_mapping`
- `count`
- `search`
- `msearch`

禁止：

- Generic OpenSearch API；
- PPL；
- 任意 HTTP path/method；
- LLM 自由选择 Tool；
- Agent 直接调用 MCP。

必须明确处理：

- timeout；
- authorization error；
- Index 不存在；
- partial shard failure；
- msearch 单项失败；
- 返回结构变化；
- Mapping 变化；
- 结果截断。

不完整结果不能输出误导性的 KPI、表格或图表。

## 九、执行阶段

内网工作顺序：

```text
I0：项目研读与真实资料盘点
I1：真实 Catalog、多月 Mapping 和生产 Policy
I2：真实 LLM Transport
I3：真实 OpenSearch MCP Gateway
I4：Failure Rate 与真实报表对账
I5：运营商 statusCode 指标
I6：认证、安全、故障、性能和业务验收
```

每个阶段必须：

1. 单独实施；
2. 运行测试；
3. 汇报修改文件；
4. 汇报实现能力；
5. 汇报测试结果；
6. 汇报安全影响；
7. 汇报尚未完成和阻塞项；
8. 给出回滚点；
9. 等我确认后再进入下一阶段。

统一质量命令：

```powershell
python -m pytest -q
python -m ruff check app tests
python -m ruff format --check app tests
python -m pyright app tests
node --check app/static/js/app.js
```

当前外网基线是 108 项测试通过。开始修改前先运行并记录基线。

## 十、本次只需要输出的内容

本次不要修改代码。

请先输出“内网接手认知报告”，必须包含：

1. 你对项目业务目标的理解；
2. 你对完整技术链路的理解；
3. 你认为不能改变的架构边界；
4. 冻结的时间、记录数量和 Failure Rate 规则；
5. status 与 statusCode 的区别；
6. 已找到的内网真实资料、路径、版本和 owner；
7. 已找到的内网 LLM 参考项目及其调用方式摘要；
8. 已找到的 MCP Tool 及真实 schema 摘要；
9. 已检查的月份 Mapping 范围；
10. 尚未找到、不能猜测的资料；
11. 当前风险；
12. 需要我回答的问题；
13. I1 阶段计划修改的文件；
14. I1 阶段计划执行的测试；
15. 本阶段停止条件。

如果你没有权限读取某项资料，请明确说明，不要假设已经读取。

完成认知报告后停止，等待我确认。

