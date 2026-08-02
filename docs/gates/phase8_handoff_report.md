# Phase 8 Handoff Report — Internal Shadow Readiness

- 日期：2026-08-01
- 状态：**READY_FOR_INTERNAL_SHADOW**（不是虚构的真实数据 PASSED）

## 外网已完成

- 一键离线验包；
- MCP capability/health/forbidden binding probe；
- LLM strict structured-output config probe；
- MCP Mapping snapshot（hash/index/time/tool/server metadata）；
- 真实 Excel/Mapping → internal candidate scaffold → Semantic compile；
- business-confirmed failure_rate 参数化配置；
- 固定只读 Health/list/mapping/count/channel/channel×status/multi-month smoke；
- AnalysisPlan/QueryPlan/DSL/Dataset/Metric/Dashboard-Evidence 六层 Shadow hash report；
- 七类差异分类、业务 verdict 与上线 Checklist。

## 内网必须提供

1. 真实字段 description Excel/CSV；
2. 真实 Mapping；
3. 已批准 MCP/LLM endpoint 与 Secret；
4. 文档粒度、时间、Channel、status、failure numerator/denominator/null/minimum denominator/Owner 确认；
5. 真实只读数据、旧系统结果（若有）和业务 verdict。

## 核心代码修改判定

预期为零。允许修改范围仅 `config/internal*.yaml`、`semantic-input/internal/**`、不提交的 `.env`/Secret reference、`evals/golden/internal/**` 和 internal gate/report。若需要修改 Contract、Graph、Compiler、Normalizer、Metric、Dashboard、Evidence、Session 或权限，视为外网框架缺陷并停止接入。

动态字段选择、通用 rollup 和声明式 Dashboard 已在外网框架中完成。真实数据出现不同于 Mock 的时间字段、业务分类、状态字段或错误原因维度时，应通过 Semantic Package 与业务口径确认接入，而不是把 `Channel × Status × Month` 复制成新的硬编码分支。

## Phase 8 完成条件

MCP/LLM probe、Import Report、业务语义、固定只读 smoke、真实 Golden 六层 Shadow、Checklist 和业务 Owner verdict 全部通过后，才可将本报告状态升级为 `PASSED`。
