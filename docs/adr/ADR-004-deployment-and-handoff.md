# ADR-004：Mock-first 部署与内网交付

- 状态：Accepted
- 日期：2026-08-01

## 决策

- `mock` profile 只有前后端、RuleBased Mock LLM 和 fixture Gateway，不需要 Key、OpenSearch 或内网。
- `local-os` profile 使用固定 OpenSearch image、受限 fixture loader、锁定版本的官方 OpenSearch MCP Server 和 MCP Gateway；应用不直连 OpenSearch。
- `mcp` profile 从环境获取外部 MCP/LLM 参数，不把凭证写入 Compose 或 YAML。
- Python、Node、MCP 均有 lockfile；Windows/Linux 提供相同的启动、验包、Semantic、MCP、LLM、Smoke 和 Shadow 脚本。
- 正式 `failure_rate` 默认不在 internal template 中；业务显式确认 status groups、null、minimum denominator、Owner 后由脚本生成。

## 后果

外网包可以独立完成 Mock 回归。内网只提供真实 Excel/Mapping、配置/Secret、口径确认和 Shadow 数据，不修改核心代码。
