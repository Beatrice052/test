# ADR-001：OpenSearch ChatBI V6.1 Greenfield 基线

- 状态：Accepted
- 日期：2026-08-01

## 背景

V6.1 唯一权威基线明确禁止继续在旧 V2–V6 工程上叠加补丁。当前工作区也没有可运行旧工程或可复用核心代码。

## 决策

在全新目录构建模块化单体：

- 一个 FastAPI 后端进程；
- 一个 low-level LangGraph StateGraph；
- 三个受限、结构化输出 LLM Node；
- 确定性 Semantic、Query、Gateway、Result、Analytics、Presentation、Evidence、Persistence 与 Security 模块；
- 一个 React/TypeScript/Vite/ECharts 前端；
- Mock/MCP Gateway 与 Mock/Recorded/OpenAI-compatible LLM Adapter 通过统一 Contract 替换；`direct` 仅保留为需单独批准的扩展标识，不在当前基线中旁路 MCP。

禁止 AgentExecutor、ReAct、自由 Tool Loop、Agent 间自由通信、LLM Tool binding、LLM 最终 DSL、LLM 指标计算和任意 ECharts option。

## 后果

- 内网只替换真实输入、配置和凭证，不修改核心链。
- 所有跨层数据必须是版本化 Pydantic Contract。
- 每个阶段以测试和 Gate Report 证明完成，不以目录或接口占位宣称完成。
- 初始投入高于 Demo Agent，但查询安全、指标口径、Evidence、Session 与回归测试可审计。

## 未采用方案

- 在旧工程继续增量补丁；
- 单一大 Agent + 全部 Tools；
- Supervisor/Swarm 多 Agent；
- LLM 直出 raw DSL；
- 一图一查询；
- 微服务、消息队列和独立向量数据库作为 POC 前置依赖。
