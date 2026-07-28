# 真实 OpenSearch MCP 接入指南

## 1. 目标与架构边界

业务代码只依赖 `OpenSearchGateway`，真实 MCP 必须藏在：

```text
Internal MCP SDK/connector
→ AllowedMCPToolClient
→ MCPOpenSearchGateway
→ deterministic execution/ToolSelector
→ Agent
```

只允许五项能力：

```text
list_indices
get_mapping
count
search
msearch
```

禁止 PPL、Generic OpenSearch API、任意 path/method/body、LLM 自由选 Tool，以及
Agent/Metric/Resolver 直接调用 MCP。

## 2. 先读取真实 Tool schema

内网 AI 必须使用内网提供的 MCP 工具发现/文档机制查看实际 schema，记录：

- Tool 的准确名称和版本；
- 请求参数、必填项、Index 参数位置；
- Query DSL/body 是否作为 object 或 JSON string；
- 返回值 envelope；
- count/search/msearch 的成功样例；
- timeout、认证、权限、not found、invalid DSL；
- `_shards`、`timed_out`、msearch item error；
- 返回大小限制、分页、压缩和调用超时；
- ListIndex/IndexMapping 的权限和过滤能力。

记录需安全清理，不保存 token、内网 URL、真实 query values 或 document hits。

如果实际 MCP 只有 Generic API，I2 必须停止并请求平台提供窄 Tool，不能把
Generic Tool 包一层后声称合规。

## 3. `AllowedMCPToolClient` 实现

当前契约在 `app/gateway/mcp.py`：

```python
class AllowedMCPToolClient(Protocol):
    def list_indices(self, pattern: str | None = None) -> list[str]: ...
    def get_mapping(self, index: str) -> dict[str, Any]: ...
    def count(self, index: str, query: dict[str, Any]) -> dict[str, Any]: ...
    def search(self, index: str, body: dict[str, Any]) -> dict[str, Any]: ...
    def msearch(self, requests: list[dict[str, Any]]) -> list[dict[str, Any]]: ...
```

内网 adapter 负责把真实 tool schema 归一化为上述类型。Provider/MCP 原始响应对象
不能穿透此边界。

示意：

```python
class InternalMCPToolClient:
    def __init__(self, approved_mcp_session) -> None:
        self.session = approved_mcp_session

    def count(self, index: str, query: dict) -> dict:
        response = self.session.call_tool(
            "<actual-approved-count-tool>",
            {"index": index, "query": query},
        )
        return normalize_count_response(response)
```

实际 Tool 名、参数和 client 必须来自现场 schema，不得照示意硬编码。

## 4. 请求约束

`MCPOpenSearchGateway` 会拒绝不匹配
`tbl_os_sub_message_{yyyy}_{mm}` 的 Index。生产还应确认：

- 是否需要环境/tenant 前缀；
- 可查询月份保留范围；
- 角色级 Index allowlist；
- 最大月份数；
- count/search/msearch 并发与请求数；
- body/query 大小；
- aggregate bucket 和 Top N 上限。

任何放宽都应配置化并通过 `QueryDslValidator`，不能在 adapter 中绕过。

Gateway 接收的 DSL 已经过 Validator，但 adapter 仍应：

- 只传入固定允许 Tool；
- 不拼接 HTTP path；
- 不接受用户提供的 Index；
- 不加入 script/runtime mappings/source hits；
- 不自动提升权限或切换 tenant；
- 不把 MCP 原始错误/连接信息返回前端。

## 5. 响应归一化和错误

### Count

至少保留：

```text
count
timed_out（如平台提供）
shard total/successful/failed（如平台提供）
```

### Search

至少保留当前 Result Processor 所需的 aggregations，以及：

```text
timed_out
_shards
truncation/capability metadata
```

业务问题只需聚合时，禁止返回 document `_source`。

### Msearch

响应顺序必须与请求顺序一致。每个 item 单独标记：

```text
success
timeout
shard failure
authorization failure
invalid request
other error
```

不能因 HTTP/MCP 调用整体成功就忽略 item error，也不能只返回成功 items 造成索引
错位。当前 Data QA 会阻止不完整结果变成业务结论。

### 统一行为

| 场景 | 行为 |
|---|---|
| 无匹配 Index | not_answerable/no data，按业务语义区分 |
| timeout | error/QA fail，不输出不完整 KPI |
| partial shards | QA fail 或批准的显式降级，默认 fail closed |
| one msearch item fails | 整体不出业务结论，保留安全 reason |
| auth/permission | fail fast，报警，不重试其他 Tool |
| Mapping changed | 停止查询，重新编译语义 |
| response schema changed | adapter contract test 失败 |

## 6. 安全、认证和日志

- 使用批准的 MCP client/session 和 secret 管理；
- TLS/证书校验不能因调试永久关闭；
- 最小权限仅覆盖允许 Index 和五项只读能力；
- 记录 run ID、Tool logical name、Index 月份数、耗时、结果桶数、错误类别；
- 不记录认证头、URL、客户级 filter value、document hits、完整原始响应；
- Evidence 展示逻辑 Tool 名和清理后的 DSL，不显示连接细节；
- 管理 Mapping/Import Report 接口在共享环境前加认证。

## 7. 依赖注入

```python
mcp_client = InternalMCPToolClient(build_approved_mcp_session())
gateway = MCPOpenSearchGateway(
    mcp_client,
    index_pattern=settings.index_pattern,
)

app = create_app(
    settings,
    semantic_compilation=internal_semantic_compilation,
    gateway=gateway,
    llm_client=structured_llm_client,
)
```

运行配置：

```text
CHATBI_DATA_SOURCE_MODE=mcp
```

没有注入 Gateway 时应用必须启动失败，不允许回退 JSONL Mock。

## 8. 测试

### Contract tests

用脱敏/stub MCP response 固定验证：

- 五个 Tool 请求参数；
- count/search/msearch 成功归一化；
- response envelope 变化；
- timeout、auth、not found；
- partial shard；
- msearch 单项错误和顺序；
- 不匹配 Index 被 Gateway 拒绝；
- Generic/PPL capability 无法启用。

### 集成测试

- `/api/chat` 单月 count；
- 单月 group/trend/Top N；
- 跨月 msearch 和 raw count 合并；
- Mapping 刷新；
- 空结果；
- blocked 字段请求在 MCP 调用前终止；
- DSL 注入/script/runtime mapping 被拒；
- MCP timeout/partial error 不产生 KPI/chart；
- Evidence 中无 endpoint/token/原始错误。

### 连通性验收

先使用批准的测试 Index/只读账号，再切业务环境。至少记录：

```text
Tool schema version
Index 范围
Mapping hashes
请求数/耗时
结果计数
错误演练
审计记录 ID
复核人
```

## 9. 完成门禁

I2 中的 MCP 接入只有在以下条件都满足时完成：

- 实际 Tool schema 和错误样例已存证；
- Adapter 只有五项窄能力；
- Index 和字段 Policy 无法绕过；
- 所有响应/错误已归一化；
- partial/timeout 演练不会输出误导结论；
- 真实模式无 Mock fallback；
- 日志/Evidence 不含连接秘密或客户数据；
- Golden 场景从 `/api/chat` 通过。
