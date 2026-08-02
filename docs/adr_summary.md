# ADR 汇总

| ADR | 冻结决定 | 主要实现/验证 |
|---|---|---|
| ADR-001 | Greenfield 模块化单体、一个 StateGraph、三个受限 Node | `backend/app/bootstrap.py`、Graph/architecture tests |
| ADR-002 | strict LLM、官方 MCP、required/forbidden Tool、无 direct 旁路 | `app/llm/`、`app/gateway/`、MCP probe tests |
| ADR-003 | subject-scoped Session、不可变 Answer、分层 Evidence、安全 ECharts | Repository/API/Playwright/security tests |
| ADR-004 | mock/local-os/mcp profiles、锁文件、内网参数化交付 | Compose、verify scripts、handoff tests |

未采用：旧工程增量补丁、自由 Tool Loop、Supervisor/Swarm、LLM raw DSL、LLM 指标计算、一图一查、前端指标公式、任意 ECharts option、PPL 主路径、Generic API、OpenSearch Agentic Memory 替代 Session。
