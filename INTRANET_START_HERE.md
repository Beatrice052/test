# 内网 AI 从这里开始

本文件是内网接手入口。当前仓库已经完成外网 Mock-first POC，但没有真实 LLM、
真实 Field Catalog、真实 Mapping、真实 OpenSearch MCP、真实银行 Policy 或
运营商状态码规则。

新建内网 AI Session 时，可直接复制
[`INTRANET_NEW_SESSION_PROMPT.md`](INTRANET_NEW_SESSION_PROMPT.md) 的完整提示词。
I0 完成后，I1～I6 分阶段新 Session 使用
[`INTRANET_PHASE_EXECUTION_PROMPTS.md`](INTRANET_PHASE_EXECUTION_PROMPTS.md)。

不要打开代码后立即替换几个路径就运行。内网接入顺序错误会造成字段泄露、指标
口径错误或把 Mock 行为误当生产行为。

## 第一步：只研读，不修改

内网 AI 必须完整阅读：

1. [项目背景](docs/PROJECT_BACKGROUND.md)
2. [完整技术执行规格](docs/TECHNICAL_EXECUTION_SPEC.md)
3. [系统架构](ARCHITECTURE.md)
4. [冻结决策与未决项](docs/DECISION_LOG.md)
5. [内网 AI 交接运行手册](docs/INTRANET_AI_HANDOFF.md)
6. [真实 LLM 接入](docs/REAL_LLM_INTEGRATION.md)
7. [真实语义资料接入](docs/REAL_SEMANTIC_ONBOARDING.md)
8. [真实 OpenSearch MCP 接入](docs/REAL_OPENSEARCH_MCP_INTEGRATION.md)
9. [分阶段执行清单](docs/INTRANET_EXECUTION_CHECKLIST.md)
10. [API 契约](docs/API.md)

完成阅读后，先输出“内网接手认知报告”，至少包含：

```text
1. 项目要解决的业务问题
2. 完整运行链路
3. 冻结的指标、时间和安全规则
4. 已找到的真实内部资料
5. 尚未找到、不能猜测的资料
6. 拟修改文件
7. 拟执行测试
8. 本阶段停止条件
```

## 第二步：盘点内网依赖

需要实际找到并阅读，而不是让用户口述大概：

- 一个已经稳定调用目标 LLM 的内网参考项目；
- 真实 `field_catalog_enrich.csv`；
- 真实 OpenSearch 月度 Index 列表；
- 至少一个代表性月份的真实 Mapping，最好覆盖多个有 Mapping 变更的月份；
- OpenSearch MCP 已暴露 Tool 的真实 schema 和返回样例；
- I4 可使用的生产报表脱敏对账结果；`failure_rate.v1` 定义不再重新询问；
- 生产字段安全分级、角色和 Index 权限资料如暂缺，记录为 I6 待办；
- 中国移动/电信/联通 `statusCode/status_code` 解析规则。

如果某项不存在，在报告中标记 blocked/待确认，不得伪造。

## 第三步：严格按阶段接入

顺序：

```text
Phase I0  内网认知与资料盘点
Phase I1  真实 Catalog + MCP Mapping 校验 + POC access 编译
Phase I2  真实 LLM transport
Phase I3  真实 OpenSearch MCP Gateway
Phase I4  指标与真实报表对账
Phase I5  Carrier statusCode 新指标
Phase I6  安全、故障、性能和业务验收
```

生产 Policy/RBAC 延后到 I6，不阻塞 I1。I1～I5 使用 Catalog 的
access/sensitivity 和现有技术安全控制，并明确标记 pending。

不能把 I1～I6 一次性做完后再报告。每阶段先跑测试、汇报、确认，再进入下一阶段。

## 当前可直接复用的接入点

真实 LLM：

```python
create_app(
    settings,
    semantic_compilation=compilation,
    llm_client=StructuredLLMClient(
        settings=settings,
        semantic_model=compilation.model,
        transport=internal_transport,
    ),
)
```

真实 MCP：

```python
create_app(
    settings,
    semantic_compilation=compilation,
    gateway=MCPOpenSearchGateway(internal_mcp_client),
)
```

设置：

```text
CHATBI_DATA_SOURCE_MODE=mcp
CHATBI_INTENT_BACKEND=structured_llm
CHATBI_SEMANTIC_MODEL_VERSION=<approved version>
```

如果设置为真实模式但没有注入真实实现，应用会明确启动失败，不会回退 Mock。
如果注入模型版本与 `CHATBI_SEMANTIC_MODEL_VERSION` 不一致，同样会启动失败。

## 绝对禁止

- 把 `statusCode` 当作 `status`；
- 只查 July；
- 把所有历史消息无限放入 Prompt；
- 把真实完整 Catalog 或 Mapping 不加过滤地放入 Prompt；
- 让 LLM 自由调用 MCP Tool；
- 使用 Generic OpenSearch API；
- 绕过 Catalog access/sensitivity 或把 Mapping-only 字段默认当 allowed；
- 在前端计算 Failure Rate；
- 将真实数据、token、URL、证书或客户信息提交到 Git；
- 为了让测试通过而硬编码固定 Mock 问题。

## 交接完成标准

内网工作完成不等于“接口能返回 200”。必须：

- 真实语义编译通过；
- LLM structured output 通过严格验证；
- MCP 只读能力和 Policy 无法绕过；
- 多月份和 Mapping drift 已处理；
- 指标与真实报表对账；
- 空值、未知码、partial shard、msearch partial error 已演练；
- blocked 字段在 Prompt/DSL/result/Evidence 全路径扫描为零；
- 全部 Golden 经 `/api/chat`；
- 每个新指标有版本、owner、证据和生效日期。
