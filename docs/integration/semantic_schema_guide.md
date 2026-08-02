# Semantic / Schema 接入指南

## 输入与产物

真实输入只有字段 description Excel/CSV 和 MCP 导出的 Mapping Snapshot。其余 Dataset/Metric/Value/Recipe/Method/Visualization/Policy 都由 `semantic-input/internal-template/` 提供受版本控制的结构模板。

```powershell
./scripts/prepare-internal-input.ps1 `
  -FieldCatalog ./input-real/field_descriptions.xlsx `
  -Mapping ./input-real/mapping_snapshot_20260731.json `
  -OutputDir ./semantic-input/internal

./scripts/compile-internal-semantic.ps1 `
  -InputDir ./semantic-input/internal `
  -OutputDir ./compiled-semantic/internal-candidate
```

准备脚本从 Mapping 推导 exact index allowlist 和标准月度 index pattern；输出目录必须是新目录或空目录，不覆盖既有候选。Compiler 对 unmatched、duplicate、ambiguous leaf、text/keyword、nested、time、Mapping-only、sanitizer、metric/policy 冲突生成 Import Report；阻塞冲突不能被忽略。

## 默认指标边界

internal template 默认只有 `message_record_count.v1`，显示“消息记录数”，不称“发送量”。正式 `failure_rate.v1` 不存在，直到业务确认 success/failure/pending/unknown/null、分子、分母、minimum denominator 和 Owner。

确认后运行：

```powershell
./scripts/configure-failure-rate.ps1 `
  -InputDir ./semantic-input/internal `
  -SuccessStatus SENT,DELIVERED `
  -FailureStatus FAILED,REJECTED `
  -PendingStatus PENDING `
  -UnknownStatus UNKNOWN `
  -NullGroup unknown `
  -MinimumDenominator 30 `
  -Owner approved_business_owner
```

脚本验证 status group 不重叠，生成 Value Dictionary、Metric Definition 并更新 Recipe；再编译候选包和 Shadow 对账。status 值、敏感字段、主时间字段或 index pattern 不符合 POC 假设时，只改 `semantic-input/internal/**` 与 `config/internal*.yaml`，不改 Compiler/Graph/Contract。
