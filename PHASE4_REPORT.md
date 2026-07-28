# Phase 4 验收报告：Gateway、指标与 Data QA

**日期：** 2026-07-28

**结果：** 通过

**阶段边界：** 三个月 Mock 数据、Gateway、确定性 Tool 选择、跨月结果合并、
指标和故障 QA。

## 创建或修改

```text
scripts/generate_mock_data.py
mock_data/
  tbl_os_sub_message_2026_06.jsonl
  tbl_os_sub_message_2026_07.jsonl
  tbl_os_sub_message_2026_08.jsonl
app/gateway/
  base.py
  models.py
  execution.py
  mock.py
  mcp.py
app/metrics/engine.py
app/results/
  models.py
  processor.py
  qa.py
tests/unit/
  test_gateway.py
  test_mcp_gateway.py
  test_results.py
```

## 能力

- 552 条确定性 synthetic documents；
- Count/Search/Msearch 规则选择和 msearch 顺序 fallback；
- Agent 依赖 Gateway Protocol，不依赖 Mock 实现；
- MCP seam 只暴露五种允许能力；
- status trim/upper、空/未知状态、retry/重复计数；
- 多月份合并原始 counts 后再计算 failure rate；
- Decimal `ROUND_HALF_UP` 两位小数；
- 零分母 `null`；
- timeout、shard failure、bucket truncation、metric corruption QA；
- QA failed 阻止业务结论。

## 测试

```text
python -m pytest -q \
  tests/unit/test_gateway.py \
  tests/unit/test_mcp_gateway.py \
  tests/unit/test_results.py
```

结果：`17 passed`。

## 尚未完成

当时还未接 `/api/chat` 和完整前端。

## 下一阶段

接通 Agent/Session/API/UI/Evidence，运行 Golden 与浏览器验收。
