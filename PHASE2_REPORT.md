# Phase 2 验收报告：语义层与 Policy

**日期：** 2026-07-28

**结果：** 通过

**阶段边界：** synthetic 语义源、Semantic Compiler、Import Report、字段检索与
Mock Policy。

## 创建或修改

```text
semantic_sources/
  field_catalog_enrich.csv
  mock_mapping.json
  metric_registry.yaml
  value_dictionary.yaml
  policy.yaml
app/semantic/
  models.py
  compiler.py
  retriever.py
  resolver.py
runtime/
  compiled_semantic_model.json
  semantic_import_report.json
tests/unit/
  test_semantic_compiler.py
  test_semantic_retriever.py
```

## 能力

- CSV、Mapping、Metric、Dictionary、Policy 的真实可替换编译；
- Mapping 权威类型和 text keyword aggregation path；
- mapping-only 默认 review-required；
- duplicate、catalog-only、mapping-only、type conflict、invalid binding 报告；
- blocked/review-required 从候选隔离；
- `candidate_role` 在入口删除，不进入模型与 hash；
- synthetic 字段明确标记；
- 编译产物可审计。

Import Report：

```text
24 mapping fields
22 catalog rows
21 matched
3 mapping-only
1 catalog-only
0 duplicate
0 invalid metric binding
PASSED_WITH_WARNINGS
```

Warnings 是设计的替换/对齐测试数据，不是编译失败。

## 测试

```text
python -m pytest -q \
  tests/unit/test_semantic_compiler.py \
  tests/unit/test_semantic_retriever.py
```

结果：`9 passed`。

## 尚未完成

当时未接 Intent、Query DSL 或执行层。

## 下一阶段

实现受控 Intent、Resolver、跨月 QueryPlan、DSL 和安全 Validator。
