# 内网迁移总指南

## 1. 先读再迁移

本文件是迁移导航，不替代专项手册。内网 AI 和工程师必须先从
[`INTRANET_START_HERE.md`](../INTRANET_START_HERE.md) 开始，按
[文档索引](DOCUMENT_INDEX.md) 研读项目背景、技术方案、架构和冻结决策，并先提交
认知报告。

迁移目标是替换四类依赖：

```text
Mock semantic sources → 真实 Catalog + MCP Mapping 校验 + Metric/POC Policy
MockLLMClient          → StructuredLLMClient + 内网批准 transport
MockOpenSearchGateway  → MCPOpenSearchGateway + 内网批准 client
开发部署配置            → 内网认证、Session、审计、限流和运维
```

Agent 主流程、API 契约和前端结构不应因此重写。

## 2. 迁移前基线

在独立分支记录：

```powershell
python -m pytest -q
python -m ruff check app tests
python -m ruff format --check app tests
python -m pyright app tests
node --check app/static/js/app.js
```

同时保存：

- 基线 commit；
- Mock semantic model version/hash；
- 当前 Golden 结果；
- Python/依赖版本；
- 不含秘密的运行配置；
- 回滚启动命令。

不要删除 Mock fixture。它们是回归和离线故障排查基线，但生产页面必须明确显示
当前数据源状态，不能把 Mock 结果混入真实会话。

## 3. 迁移顺序

```text
I0  认知/来源盘点
 ↓
I1  真实语义模型
 ↓
I2  真实 LLM + OpenSearch MCP + /api/chat 端到端联调
 ↓
I3  指标对账 + POC 最终验收

Optional Production  Policy/RBAC、认证、持久化、审计和生产压测
```

详细 Gate 见 [内网执行清单](INTRANET_EXECUTION_CHECKLIST.md)。每阶段独立提交、
测试、汇报和确认。

## 4. 真实语义模型

按 [真实语义资料接入](REAL_SEMANTIC_ONBOARDING.md)：

1. 只读检查真实 `field_catalog_enrich.csv`；
2. 通过 MCP `list_indices/get_mapping` 自动获取多月 Mapping 作物理校验；
3. 比较字段/类型/keyword/date/object drift；
4. Mapping-only 和未分类字段默认 `review_required`；
5. 编译 Metric、Value Dictionary、Catalog access 和现有技术 Policy；
6. 生成 Import Report、model version/hash；
7. 让 LLM、Resolver 和 Validator 使用同一模型；
8. 跑隔离、安全、跨月和业务测试。

`candidate_role` 即使在真实 CSV 中存在也继续彻底忽略。
生产 Policy/RBAC 属于可选生产化工作，不阻塞本阶段；I1～I3 标记 pending。

## 5. 真实 LLM（I2）

按 [真实 LLM 接入](REAL_LLM_INTEGRATION.md)：

1. 找到并研读一个当前批准的内网参考项目；
2. 记录其 client/factory、认证、structured output、timeout、retry、审计和测试；
3. 实现 `StructuredLLMTransport`；
4. 使用真实 Compiled Semantic Model 创建 `StructuredLLMClient`；
5. 通过 `create_app(..., llm_client=...)` 注入；
6. 验证 Prompt 只含 allowed 字段，真实模式无 Mock fallback。

不要把参考项目的业务 Prompt、凭证或秘密复制进本仓库。

## 6. 真实 OpenSearch MCP（同属 I2）

按 [真实 MCP 接入](REAL_OPENSEARCH_MCP_INTEGRATION.md)：

1. 读取实际 MCP Tool schema 和错误样例；
2. 实现 `AllowedMCPToolClient`；
3. 创建 `MCPOpenSearchGateway`；
4. 通过 `create_app(..., gateway=...)` 注入；
5. 验证五项窄能力、Index/字段 allowlist 和错误归一化；
6. 演练 timeout、partial shard 和 msearch item error。

业务模块不能直接调用底层 MCP。Generic API 和 PPL 不得加入 adapter。

## 7. 指标和运营商规则（I3）

`failure_rate.v1` 必须先与真实报表对账。真实定义不同则新增版本。

`statusCode/status_code` 是不同运营商的原始码，不是 `status`。中国移动、中国电信、
中国联通的专项失败率必须等待：

```text
carrier 字段
code 字段
三运营商码表
匹配方法
unknown 策略
版本/生效日期/owner
多回执优先级
```

然后新增如 `carrier_failure_rate.v1` 的独立指标，由版本化配置和 Metric Engine
确定性执行。规则不得放入 Prompt 让 LLM判断。

## 8. 建议的内网组装

以下只说明依赖关系，平台调用细节以内部参考项目为准：

```python
settings = Settings(
    data_source_mode="mcp",
    intent_backend="structured_llm",
    semantic_model_version="<approved-version>",
)

semantic = compile_internal_semantics(settings)
llm_client = StructuredLLMClient(
    settings=settings,
    semantic_model=semantic.model,
    transport=build_internal_llm_transport(),
)
gateway = MCPOpenSearchGateway(
    build_internal_allowed_mcp_client(),
    index_pattern=settings.index_pattern,
)

app = create_app(
    settings,
    semantic_compilation=semantic,
    llm_client=llm_client,
    gateway=gateway,
)
```

`create_app` 已支持注入 `semantic_compilation` 或自定义 `semantic_source_paths`，
并验证模型版本与 Settings 一致。内网应注入真实 compilation，确保只编译一次且
所有组件共享同一版本；不要让默认 Mock 编译与真实 LLM 并存。

## 9. 可选生产化配置与安全

最低要求：

- `CHATBI_DATA_SOURCE_MODE=mcp`；
- `CHATBI_INTENT_BACKEND=structured_llm`；
- 语义模型和模型部署版本固定；
- secret 由批准的管理方式注入；
- MCP/LLM 都是最小权限；
- `/api/admin/semantic/report` 受认证保护；
- Session 有用户/角色隔离；
- 日志、trace、Evidence 脱敏；
- 请求、月份、桶、并发和超时有限制；
- 页面显示真实 Connected 状态，但不暴露 endpoint。

Mock Policy 不能作为生产安全验收结果。

## 10. 回滚

每阶段保留可独立回滚的 commit 和配置版本。回滚原则：

- 语义问题：退回上一批准 semantic model/config；
- LLM 问题：退回上一批准 model deployment/transport，不静默切 Mock；
- MCP 问题：停止真实流量或退回上一 Gateway adapter；
- 指标问题：撤下新版本，不修改已发布旧版本含义；
- 安全问题：立即禁用受影响字段/Index，优先 fail closed。

Mock 模式只能用于明确标注的离线演示/测试，不能作为生产无提示降级。

## 11. POC 与生产化验收

I3 的 POC 完成判定以 [内网执行清单](INTRANET_EXECUTION_CHECKLIST.md)为准，
至少包括：

- 真实语义编译和 Mapping drift；
- LLM structured output 与 Prompt 安全；
- MCP 五项窄能力和故障演练；
- 真实报表逐日/逐维度对账；
- carrier 规则版本化（若该能力上线）；
- blocked 字段全路径零泄露；
- 全部 Golden 经 `/api/chat`。

认证、生产 RBAC、持久化 Session、正式审计、生产性能和上线回滚演练属于可选
Production Gate；这些内容未完成时可以验收 POC，但不得声明 production-ready。
