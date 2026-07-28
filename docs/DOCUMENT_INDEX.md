# 文档索引

## 内网 AI 必读顺序

| 顺序 | 文档 | 用途 |
|---:|---|---|
| 0 | `INTRANET_NEW_SESSION_PROMPT.md` | 新 Session 可直接复制的启动提示词 |
| 1 | `INTRANET_START_HERE.md` | 接手入口、阶段顺序和禁止事项 |
| 2 | `docs/PROJECT_BACKGROUND.md` | 业务背景、已确认范围和未完成项 |
| 3 | `docs/TECHNICAL_EXECUTION_SPEC.md` | 完整技术执行规格 |
| 4 | `ARCHITECTURE.md` | 模块边界、状态机和安全层 |
| 5 | `docs/DECISION_LOG.md` | 冻结决策和内网未决问题 |
| 6 | `docs/INTRANET_AI_HANDOFF.md` | AI 接手、证据、停止和汇报规则 |
| 7 | 当前阶段专项指南 | LLM、Semantic 或 MCP |
| 8 | `docs/INTRANET_EXECUTION_CHECKLIST.md` | I0～I6 Gate |
| 9 | `docs/API.md` | 前后端契约 |
| 10 | 代码和测试 | 以实际行为复核文档 |

完成阅读后必须先交“内网接手认知报告”，不能直接开始替换。

## 业务与架构

| 文档 | 读者 | 内容 |
|---|---|---|
| `README.md` | 所有人 | 项目概览、运行和质量命令 |
| `docs/PROJECT_BACKGROUND.md` | 业务/技术 | 已确认业务语义 |
| `docs/TECHNICAL_EXECUTION_SPEC.md` | 架构/开发 | 三段主流程和模块规格 |
| `ARCHITECTURE.md` | 架构/安全 | 控制边界、依赖注入、安全层 |
| `docs/DECISION_LOG.md` | 全体 | 决策 ID、未决项、变更规则 |

## 内网专项

| 文档 | 作用 |
|---|---|
| `INTRANET_NEW_SESSION_PROMPT.md` | 内网新 Session 启动提示词 |
| `INTRANET_START_HERE.md` | 内网入口 |
| `docs/INTRANET_AI_HANDOFF.md` | 接棒运行手册 |
| `docs/REAL_SEMANTIC_ONBOARDING.md` | 真实 Catalog、多月 Mapping、Policy |
| `docs/REAL_LLM_INTEGRATION.md` | 学习内网项目并接真实模型 |
| `docs/REAL_OPENSEARCH_MCP_INTEGRATION.md` | 真实 MCP 窄能力接入 |
| `docs/INTRANET_EXECUTION_CHECKLIST.md` | 分阶段 Gate 和报告模板 |
| `docs/INTERNAL_MIGRATION.md` | 总体迁移和回滚导航 |

## 接口、数据与验收

| 文档 | 作用 |
|---|---|
| `docs/API.md` | Chat/session/health/admin 契约 |
| `docs/MOCK_DATA_DICTIONARY.md` | synthetic 字段和数据范围 |
| `docs/MANUAL_ACCEPTANCE.md` | 浏览器手工验收 |
| `FINAL_EXTERNAL_ACCEPTANCE_REPORT.md` | 外网交付基线和明确未完成项 |
| `PHASE1_REPORT.md`～`PHASE5_REPORT.md` | 外网各阶段历史报告 |

## 权威性

当内容发生冲突：

1. 用户最新确认和批准的内网证据优先；
2. `docs/DECISION_LOG.md` 中 CONFIRMED 决策次之；
3. 当前代码契约和通过的测试用于验证实际行为；
4. 阶段报告是历史记录，不应覆盖更新后的主规格；
5. Mock 字典不能证明生产语义。

任何真实口径变更都要更新 Decision Log、专项指南、测试和阶段报告，指标变化还要
新增版本。
