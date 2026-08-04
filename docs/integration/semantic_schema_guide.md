# Semantic / Schema 接入指南

## 输入与产物

真实输入为字段 description Excel/CSV、MCP 导出的 Mapping Snapshot，以及可选但推荐的受控 FieldProfileSnapshot。其余 Dataset/Metric/Value/Recipe/Method/Visualization/Policy 都由 `semantic-input/internal-template/` 提供受版本控制的结构模板。Excel description 是业务语义来源；Mapping 是技术字段与跨索引兼容性来源；Profile 只提供基数、缺失、范围和经 Policy 筛选后的聚合样例值，三者不能相互替代。

```powershell
./scripts/prepare-internal-input.ps1 `
  -FieldCatalog ./input-real/field_descriptions.xlsx `
  -Mapping ./input-real/mapping_snapshot_20260731.json `
  -OutputDir ./semantic-input/internal

./scripts/compile-internal-semantic.ps1 `
  -InputDir ./semantic-input/internal `
  -OutputDir ./.cache/semantic-staging

./scripts/snapshot-field-profile.ps1 `
  -Config ./config/internal.yaml `
  -Dataset sub_message `
  -Mapping ./semantic-input/internal/mapping_snapshot.json `
  -SemanticPackage ./.cache/semantic-staging `
  -Output ./input-real/field_profile_snapshot.json

./scripts/compile-internal-semantic.ps1 `
  -InputDir ./semantic-input/internal `
  -Profile ./input-real/field_profile_snapshot.json `
  -OutputDir ./compiled-semantic/internal-candidate
```

准备脚本从 Mapping 推导 exact index allowlist 和标准月度 index pattern；输出目录必须是新目录或空目录，不覆盖既有候选。Compiler 对 unmatched、duplicate、ambiguous leaf、text/keyword、nested、time、Mapping-only、sanitizer、metric/policy 冲突生成 Import Report；阻塞冲突不能被忽略。

第一次 staging 编译的目的，是在任何样例值画像之前先应用 Excel 中的敏感等级和 Policy。`snapshot-field-profile` 只画像 `model_visible + aggregatable + 非 BLOCKED` 字段，查询固定 `size:0`，不读取 raw document。第二次编译会验证 Profile 的 dataset、indices 和 mapping hash，并把 cardinality 写入 CanonicalField。Agent A 的 candidate 和 Agent B 的 `ResolvedFieldDescriptor` 随后可使用 description、semantic type、capability、compatibility 与 cardinality 判断数据是否足以支撑任务；两者仍看不到 physical path 和原始样本。

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
