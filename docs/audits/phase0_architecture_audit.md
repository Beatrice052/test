# Phase 0 Architecture Audit

- 日期：2026-07-31
- 基线 SHA-256：`3762adc6ca42745151d01894c835f6d80c9dfb84a6e1ce9624e8b026ed85b6c6`
- 结论：纯 Greenfield；当前工作区不存在旧 ChatBI 代码、入口、API、测试或启动脚本。

## 必答审计结论

| 问题 | 证据结论 | V6.1 决策 |
|---|---|---|
| 可运行入口 | 无 | 新建 FastAPI 与 React 入口 |
| 前后端栈 | 无 | Python 3.12/FastAPI；Node 22/React/Vite |
| 多套 Contract | 无实现 | 只创建一套版本化 Contract |
| DSL 链 | 无实现 | Finalizer→AST→Compiler→Validator→Gateway |
| Channel 维度丢失 | 无旧代码可定位 | DatasetContract、BucketPath、walker、G03 阻断 |
| doc_count 命名 | 无实现 | 默认只称“消息记录数” |
| Mapping 获取 | 无实现 | Bootstrap/Refresh 编译，在线不重复获取 |
| MCP/LLM 调用链 | 无实现 | React→FastAPI→StateGraph→Gateway→MCP→OpenSearch |
| 旧代码复用 | 无旧代码 | 不复用核心链；后续旧资产仅作行为/视觉参考 |
| 风险 | Python/Node 宿主版本差异、缺 uv/Docker、真实语义和口径未知 | 受管运行时、Adapter、Mock、Fixture、Gate |

## 权威边界

Agent A 负责意图、指标选择与分析任务；Agent B 负责受约束的逻辑 QueryPlan；Agent C 负责基于真实结果的洞察和可视化意图。Semantic Binding、公式、Query Consolidation、DSL、Gateway、Normalizer、Analytics、QA、Grounding、Dashboard、Evidence、Session、权限与幂等全部由确定性程序负责。

内网只提供真实 Excel、Mapping、LLM/MCP 配置和凭证、业务口径批准与 Shadow 对账；不重写核心模块。

完整实施前审计原稿保存在本交付上级目录的 `phase0_architecture_audit.md`，本文件作为正式仓库内的审计记录。

