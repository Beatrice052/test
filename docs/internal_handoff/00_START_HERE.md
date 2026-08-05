# 内网接手入口

## 项目目标与当前状态

本分支把 V6.1 受治理 ChatBI 升级为 Schema/Registry 驱动的通用分析引擎。正式代码不把 Channel、Use Case、Template 或 Source System 当能力白名单；新字段、字段度量、实体、方法、Recipe 和可视化意图应通过 Semantic Input 编译进入既有 A→Resolver→B→Compiler→Gateway→Dataset→C 链路。

外网可完成的核心框架、Mock 链路、测试、Evidence v2 和接入脚本已经完成。内网工作只剩真实输入、批准的 Adapter 配置、真实业务 Golden 与 Owner 签字，不应重写 Compiler、Agent、Analytics、Grounding 或 Evidence。

## 权威顺序

1. 仓库根目录 `AGENTS.md`。
2. `docs/baseline/OpenSearch_ChatBI_V6.1_Master_Execution_Spec_含_opensearch-agent_架构校准.md` 的冻结架构与安全边界。
3. 本次通用分析升级目标与 Evidence v2 口径。
4. `OpenSearch_ChatBI_通用智能分析能力升级执行方案_v1.md`。
5. 当前代码、Contract、测试和 Gate 报告所证明的批准行为。
6. 更早文档只作背景。

冲突清单和处理结果见 `docs/audits/generic_analytics_phase0_audit.md`。

## 最短接手路径

1. 在完全离线环境运行 `powershell -NoProfile -ExecutionPolicy Bypass -File ./scripts/verify-package.ps1`，确认工具链和 Mock 基线。
2. 按 `02_INTERNAL_INPUT_CHECKLIST.md` 收集真实 Mapping、字段目录、Policy、Metric、ValueDictionary、Entity、MCP、LLM、身份与 Golden。
3. 复制 `semantic-input/internal-template` 到未提交的 `semantic-input/internal`，运行 `prepare-internal-input.ps1`、Mapping snapshot、staging compile、字段 profile、正式 compile。
4. 设置 `.env`，运行 `check-real-llm-cutover.ps1`、`probe-llm.ps1`、`probe-mcp.ps1` 和只读 `smoke-mcp.ps1`。
5. 先 Shadow，完成取数、指标、统计、图表、Claim Trace 与 Evidence 人工对账，再进入 UAT。
6. 将 approved semantic package、配置和 Secret 通过内网发布系统注入；Secret 和真实原始数据不得提交仓库。

## 不得修改的架构边界

- 一个模块化 FastAPI、一个 LangGraph StateGraph、三个受限 LLM Agent；Agent C 保持 C1→Host→C2。
- Agent 不得读取 physical path、凭证、MCP tool 名、raw DSL、未授权字段或任意 `_source`。
- Agent B 只产出逻辑 QueryPlan；确定性 Compiler 独占 DSL。
- 正式指标、统计、图表验证、数值计算、QA、Grounding 和 Evidence 均由 Host 执行。
- 不增加 Supervisor、自由 ReAct/Tool Loop、LLM 代码执行、任意 ECharts option 或业务关键词路由。
- 正式环境拒绝 Mock LLM、Mock Gateway、Mock Identity、Mock semantic input 和未经填写审核的 `internal-template`。

## 内网只需替换的内容

- `semantic-input/internal`：Mapping、字段目录、Policy、Metric、Measure、Method、Recipe、Visualization、ValueDictionary、Entity。
- `.env`/Secret 管理：真实 LLM、MCP、身份、数据库与 artifact 路径。
- 稳定接口后的 MCP transport/bindings；若公司 endpoint 不是既有 OpenAI-compatible 协议，只实现 `StructuredLLMClient` Adapter。
- 真实 Golden、Shadow 样例和业务 Owner verdict。

继续阅读顺序：`01` 架构与数据流 → `02` 输入清单 → `03` Semantic 构建 → `04` LLM → `05` MCP → `06` Evidence → `07` 测试/UAT → `08` 运维/回滚 → `09` 内网确认事项 → `10` 配置参考。
