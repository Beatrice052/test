# 外网 Mock-first 最终验收报告

**日期：** 2026-07-28

**结论：** 外网能够可靠实现的范围已完成并通过验收。

**生产声明：** 未接入真实银行数据、真实 Mapping、真实 MCP 或生产 Policy。

## 最终交付

- 可运行 FastAPI ChatBI；
- 完整自然语言到 Evidence 主流程；
- 可替换 Semantic Compiler；
- 多月份 Mock OpenSearch；
- 版本化确定性指标；
- 后端安全 Policy 和 DSL Validator；
- Mock/MCP Gateway 可替换边界；
- 真实 LLM `StructuredLLMTransport`、严格 schema 校验和显式依赖注入；
- 内网 AI 必读入口、来源盘点、真实 Semantic/LLM/MCP 专项手册和 I0～I6 门禁；
- Session 与澄清；
- 本地 ECharts 结构化页面；
- 阶段报告、API、Mock 字典、内网迁移和手工验收文档。

## 全量质量门

```text
python -m pytest -q
108 passed

python -m ruff check app tests
All checks passed

python -m pyright app tests
0 errors, 0 warnings, 0 informations

node --check app/static/js/app.js
passed
```

ECharts：

```text
version: 6.1.0
sha256: B66B25AEB4DF84E33199DC21694014D336D222CBD9DEB0E5A7C14BD6AA0D0FD0
runtime CDN requests: none
```

## 浏览器验收

在本地 `http://127.0.0.1:8000` 实际操作：

| 项目 | 结果 |
|---|---|
| Mock 警示、Index、默认时间、时区、模型 | 通过 |
| 示例填入、Enter 发送 | 通过 |
| Failure Rate KPI | 5 张，值为 186/62/62/62/33.33% |
| Channel 表格 | 3 行 |
| ECharts | 实际生成 canvas |
| Evidence | 默认折叠；展开 8 个区块 |
| Evidence blocked 泄露扫描 | 无 |
| “最近失败情况”澄清 | 通过 |
| “按Channel”续答 | 失败记录 62 条 |
| 页面刷新恢复当前会话 | 通过 |
| Policy 阻断 | 无 DSL/Evidence/物理 blocked 字段 |
| 空结果 | 0、Failure Rate `—`、无图表 |
| 页面水平溢出 | 无 |
| 浏览器 console error/warning | 0 |

## 阶段测试

```text
Phase 1：29 passed（历史骨架 Gate）
Phase 2：9 passed（Semantic）
Phase 3：22 passed（Intent/Query）
Phase 4：17 passed（Gateway/Metric/QA）
Phase 5：29 passed（Integration/Golden/UI contract）
Full suite：108 passed（包含语义模型注入、真实依赖和 structured LLM 契约测试）
```

阶段报告：

```text
PHASE1_REPORT.md
PHASE2_REPORT.md
PHASE3_REPORT.md
PHASE4_REPORT.md
PHASE5_REPORT.md
```

## 明确未伪造

- 不将 July 当成唯一业务表；
- 不将 `statusCode` 当成通用生命周期状态；
- 不回答尚无编码表的运营商专项失败率；
- 不声称 Mock Policy 已是生产清单；
- 不声称 MCP 已连接；
- 不使用 PPL/Generic API/自由 Tool loop；
- 不使用 LLM 改写指标公式；
- 不在前端重算结果。

## 下一步

进入内网后先从 `INTRANET_START_HERE.md` 研读项目背景和技术方案，提交接手认知
报告，再按 I0～I6 替换语义源、真实 LLM、Mapping、MCP Gateway、Metric/Policy，
并用相同 Golden 场景与真实报表对账。Agent、API 和页面不应重写。

内网交接专项文档：

```text
docs/INTRANET_AI_HANDOFF.md
docs/REAL_LLM_INTEGRATION.md
docs/REAL_SEMANTIC_ONBOARDING.md
docs/REAL_OPENSEARCH_MCP_INTEGRATION.md
docs/INTRANET_EXECUTION_CHECKLIST.md
docs/DOCUMENT_INDEX.md
```
