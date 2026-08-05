# Semantic Package 构建与迁移

## 目录准备

不要直接上线 `semantic-input/internal-template`。复制到不会提交的 `semantic-input/internal`，填写真实内容并由 Owner 审核。至少保留这些目录/文件：

```text
dataset_registry.yaml
mapping_snapshot.json
field_descriptions.csv 或 field_descriptions.xlsx
policy.yaml
metric_registry/*.yaml
measures/*.yaml
methods/*.yaml
values/*.yaml
entities/*.yaml
recipes/*.yaml
visualizations/*.yaml
```

可先用真实目录和 Mapping 生成骨架：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ./scripts/prepare-internal-input.ps1 `
  -FieldCatalog C:\secure\field_descriptions.xlsx `
  -Mapping C:\secure\mapping_snapshot.json `
  -OutputDir C:\secure\semantic-input\internal `
  -IndexPattern 'approved-index-prefix-*'
```

## 推荐编译顺序

1. 通过 MCP 对明确 index 或已审批 pattern 固化 Mapping：

```powershell
./scripts/snapshot-mapping.ps1 -Config ./config/gateway.mcp.yaml -Dataset business_dataset `
  -Index @('index_2026_06','index_2026_07') -Output C:\secure\mapping_snapshot.json
```

2. 不带 profile 进行 staging compile：

```powershell
./scripts/compile-internal-semantic.ps1 `
  -InputDir C:\secure\semantic-input\internal `
  -OutputDir C:\secure\compiled-semantic\staging
```

3. 只对 Policy 允许字段执行 `size:0` profile，然后再次编译：

```powershell
./scripts/snapshot-field-profile.ps1 -Config ./config/gateway.mcp.yaml `
  -Dataset business_dataset -Mapping C:\secure\mapping_snapshot.json `
  -SemanticPackage C:\secure\compiled-semantic\staging `
  -Output C:\secure\field_profile_snapshot.json

./scripts/compile-internal-semantic.ps1 `
  -InputDir C:\secure\semantic-input\internal `
  -Profile C:\secure\field_profile_snapshot.json `
  -OutputDir C:\secure\compiled-semantic\approved
```

编译必须稳定：相同输入重复编译得到相同 package version/hash；Mapping、catalog、Policy 或 Registry 改动必须产生 diff/new version。

## Config-only onboarding

### 新字段

在 Mapping 和字段目录中加入字段，由 Compiler 推断/校验 mapping type、semantic type、capability、跨月兼容性、security 和 cardinality。若字段可过滤/分组/range/数值聚合，对应 capability 会进入 Retriever 与 Resolver；正式 Python/TypeScript 代码不改。

### 新字段度量

在 `measures/*.yaml` 定义 `source_field_id`、`allowed_aggregations`、default/parameters、unit、source grain、population scope、additive semantics 与 approximate。Compiler 会拒绝字段缺失或 capability 不匹配。支持 `value_count/cardinality/sum/avg/min/max/stats/extended_stats/percentiles`。

### 新实体

在 `entities/*.yaml` 定义 identifier/label semantic field、resolution 模式和最短查询长度。低基数且安全的 dictionary 可随 package；高基数成员必须使用 approved lookup Adapter，不能把全量成员交给 LLM。

### 新正式指标

在 `metric_registry/*.yaml` 定义版本化 Formula AST。`filtered_count` 指标应显式配置 `value_dictionary_ids` 和 `source_field_ids`；Resolver/Compiler 会校验唯一兼容字典，不再假定任何样例状态值。新业务公式必须由 Owner 确认，不能让 LLM 自由生成。

## 常见失败与修复

| 编译问题 | 修复 |
|---|---|
| Mapping type conflict | 修正跨月 Mapping，或拆分不兼容 index family；不要强制 cast 掩盖 |
| measure capability missing | 使用可聚合 numeric/keyword path，或缩小 allowed aggregations |
| metric dictionary count ≠ 1 | 显式填写 versioned `value_dictionary_ids`，确保公式 group 全部存在 |
| blocked/sensitive candidate 出现 | 修 Policy 并重编译；测试要求 model-invisible field/measure 不进入 retrieval |
| cardinality 超预算 | 获取 profile；使用 composite、Top-N dependent query 或澄清，不能静默截断 |
| entity ambiguous | 补 alias/dictionary 或让用户澄清；不得猜 member ID |
| package 路径含 mock/template | 正式 profile 会拒绝；发布审核后的独立 internal 路径 |

迁移旧 Registry 时先运行 `docs/integration/legacy_metric_registry_migration.md` 的检查，再补本文件要求的 Measure/Entity/ValueDictionary 与 Evidence 技术口径字段。
