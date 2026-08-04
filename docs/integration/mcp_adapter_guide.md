# MCP Adapter 接入指南

## 固定边界

真实 OpenSearch 只通过官方 Python MCP SDK transport 进入 `McpOpenSearchGateway`。LLM 不拥有 Tool，动态连接参数不来自 Agent。允许能力为 `list_indices`、`get_mapping`、`execute_search`、`health`；`GenericOpenSearchApiTool`、`PPLQueryTool`、Memory/Agentic 和写类 Tool 禁止绑定。

`local-os` 锁定 `opensearch-mcp-server-py==0.11.0`，只启用四个只读 Tool，设置 `OPENSEARCH_SETTINGS_ALLOW_WRITE=false`。生产/内网应由已批准的 MCP 服务、认证代理或受限网络提供相同 Tool schema。

## 配置

复制 `config/internal.example.yaml` 为不含凭证的 `config/internal.yaml`。只在 Secret Store、环境变量或不提交的 `.env` 中设置：

```text
OPENSEARCH_MCP_ENDPOINT
OPENSEARCH_MCP_TRANSPORT=streamable_http
```

stdio 模式可在 `gateway.mcp` 配置 `command`、`args` 和 `environment_from_env`；后者只写环境变量名，不写值。TLS verify 默认必须为 true；仅 `local-os` 无认证开发集群允许 false。

## Probe（不执行业务 DSL）

```powershell
./scripts/probe-mcp.ps1 -Config ./config/internal.yaml -Output ./reports/mcp-probe.json
```

报告包含 transport、可获取的 server name/version、detected tools、required binding found/missing、Search input schema compatibility、health、forbidden binding check，并显式记录不含 credentials。

## Mapping Snapshot

推荐用受控 pattern 自动发现当前可用索引。`ListIndexTool` 返回值由 Adapter 归一化并再次按 pattern 过滤；Agent 不参与：

```powershell
./scripts/snapshot-mapping.ps1 `
  -Config ./config/internal.yaml `
  -Dataset sub_message `
  -IndexPattern 'tbl_os_sub_message_2026_*' `
  -Output ./input-real/mapping_snapshot.json
```

也可以显式指定已审核索引：

```powershell
./scripts/snapshot-mapping.ps1 `
  -Config ./config/internal.yaml `
  -Dataset sub_message `
  -Index tbl_os_sub_message_2026_07 `
  -Output ./input-real/mapping_snapshot_20260731.json
```

输出是编译器可直接读取的版本化 `MappingSnapshot`，保存 mapping hash、indices、timestamp、Tool/transport/server metadata，不保存凭证。

## 受控字段画像（避免 QueryPlan 数据不足）

真实字段 description 来自内网 Excel/CSV；MCP 提供技术 Mapping 与聚合画像。必须按以下两次编译流程执行，不能让 Agent A/B 在普通问答时临时读取 Mapping 或 raw sample：

```powershell
# 1. Excel + Mapping 首次编译，先应用字段敏感性和 Policy
uv run --project backend python -m app.cli semantic compile `
  --field-catalog ./input-real/field_descriptions.xlsx `
  --mapping ./input-real/mapping_snapshot.json `
  --output-dir ./.cache/semantic-staging

# 2. 只画像 staging 包中 model_visible + aggregatable + 非 BLOCKED 字段
./scripts/snapshot-field-profile.ps1 `
  -Config ./config/internal.yaml `
  -Dataset sub_message `
  -Mapping ./input-real/mapping_snapshot.json `
  -SemanticPackage ./.cache/semantic-staging `
  -MaxFields 100 `
  -SampleValueLimit 5 `
  -Output ./input-real/field_profile_snapshot.json

# 3. 带 profile 重编译待发布正式包
uv run --project backend python -m app.cli semantic compile `
  --field-catalog ./input-real/field_descriptions.xlsx `
  --mapping ./input-real/mapping_snapshot.json `
  --profile ./input-real/field_profile_snapshot.json `
  --output-dir ./compiled-semantic/internal-candidate
```

`snapshot-profile` 通过已绑定的 `SearchIndexTool` 发送一条有上限的 `size:0` 聚合查询，不请求 `_source` 或 raw hits。输出的版本化 `FieldProfileSnapshot` 包含非空/缺失量、近似 cardinality、数值/日期范围、最多 10 个聚合样例值、Mapping hash、Query hash 和 provenance。若 Profile 的 dataset、indices 或 Mapping hash 与本次编译不一致，Compiler 会直接拒绝，避免旧画像污染新 Schema。

`SampleValueLimit` 默认为 5，只对已通过 staging Policy 的字段生效；仍应根据内网数据分级决定是否设为 0。聚合样例值只辅助识别值域和估算可视化/桶预算，不能替代 Excel description、Value Dictionary 或业务口径确认，也不会直接提供给 Agent B。

运行时 Agent A 只收到有界候选的 description/semantic metadata；Agent B 收到 `ResolvedFieldDescriptor`（description、semantic/mapping type、capabilities、maturity、compatibility、cardinality），两者都没有 physical path、MCP Tool 或 raw document。完整设计见 `docs/integration/multi_agent_orchestration.md`。

## 固定只读 Smoke

```powershell
./scripts/smoke-mcp.ps1 `
  -Config ./config/internal.yaml -Dataset sub_message `
  -Index tbl_os_sub_message_2026_05,tbl_os_sub_message_2026_06,tbl_os_sub_message_2026_07 `
  -TimeField event_time -ChannelField channel -StatusField status `
  -From '2026-05-01T00:00:00+08:00' -To '2026-08-01T00:00:00+08:00' `
  -Output ./reports/mcp-smoke.json
```

连接级顺序固定为 Health → explicit index list → Mapping；业务 smoke 则按已审核真实语义选择“窄范围总量 → 一个类别拆分 → 一个必要的交叉维度 → 一个跨期问题”，不能把模板字段当成正式任务。字段和 index 参数有安全语法校验，index wildcard 被拒绝；查询固定 `size=0`、10s、`[from,to)` 和显式 timezone。报告保存 DSL、response hash、took、Shard、total、bucket count，不保存 raw 文档或凭证。
