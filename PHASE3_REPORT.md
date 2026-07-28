# Phase 3 验收报告：理解、规划与 DSL

**日期：** 2026-07-28

**结果：** 通过

**阶段边界：** Intent/AnalysisPlan、Semantic Resolver、月份 Index、
QueryPlan、OpenSearch DSL 和安全校验。

## 创建或修改

```text
app/intent/
  models.py
  mock_client.py
app/query/
  models.py
  index_resolver.py
  planner.py
  dsl.py
  validator.py
app/agent/contracts.py
app/agent/state.py
tests/unit/
  test_intent_parser.py
  test_resolver.py
  test_monthly_index_resolver.py
  test_query_pipeline.py
```

## 能力

- AnalysisPlan 不含 Tool、Index 或 DSL；
- 默认月、单月、跨月、单日和日期范围解析；
- 统一 `Asia/Hong_Kong` 和 `[from, to)`；
- 字段歧义、blocked、review-required、未定义指标的 answerability；
- 2026-06～08 扩展为三个物理 Index；
- 纯 count、过滤、terms、date histogram、metric aggregation DSL；
- script/runtime mapping、blocked field、非法 Index、超时/桶/时间范围校验；
- 运营商专项失败率不会静默映射到 `failure_rate.v1`；
- 无 PPL、Generic API 或 LLM Tool loop。

## 测试

```text
python -m pytest -q \
  tests/unit/test_intent_parser.py \
  tests/unit/test_resolver.py \
  tests/unit/test_monthly_index_resolver.py \
  tests/unit/test_query_pipeline.py
```

结果：`22 passed`。

## 尚未完成

当时没有查询执行、确定性指标或页面展示。

## 下一阶段

实现 Mock/MCP Gateway 边界、ToolSelector、synthetic 数据、Metric Engine 和 QA。
