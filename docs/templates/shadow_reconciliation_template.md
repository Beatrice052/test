# Shadow Reconciliation Template

每个真实 Golden 必须同时保存或引用以下六层产物，不能只比较自然语言回答：

- AnalysisPlan
- QueryPlan
- Compiled DSL
- Normalized Dataset
- Metric result（比例指标含 numerator、denominator、excluded）
- Dashboard/Evidence

如果旧系统存在等价结果，再附 `old_result`。使用 `scripts/build-shadow-report.ps1` 或 `.sh` 生成只含文件名、hash、大小、差异分类和业务 verdict 的审计记录；脚本不会把真实 payload 或 credentials 复制进报告。

允许的差异分类：

- `EXPECTED_SEMANTIC_FIX`
- `EXPECTED_TIMEZONE_FIX`
- `EXPECTED_COMPLETENESS_FIX`
- `METRIC_DEFINITION_DIFFERENCE`
- `DATA_CHANGE`
- `IMPLEMENTATION_BUG`
- `UNKNOWN_NEEDS_INVESTIGATION`

业务审批项：时间范围/时区、grain、完整性、总数、比例分子/分母/排除项、Dashboard/Evidence 追溯、最终 verdict。
