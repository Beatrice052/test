# Phase 2 — 后端功能对比与基线决策 V2

## 目标

只比较本次真实产品范围内的后端能力：

```text
Requirement
→ Use Case
→ AI Guided Form
→ AC
→ Validation
```

不比较完整 MDC Messaging SDLC 静态页面。

---

## 必须先读取

```text
reports/phase-status.md
reports/phase1/deep-read-shortlist.md
reports/phase1/demo-scope-classification.md
reports/phase1/api-route-index.json
reports/phase1/backend-symbol-index.json
inputs/business-rules.md
```

---

## 强制限制

1. 不重新全仓扫描；
2. 不分析 out-of-scope 静态页面；
3. 不修改代码；
4. 不按时间选版本；
5. 不把 Demo 后端整体默认为最新；
6. 不因 Validation API 暂时不可用而判定代码错误；
7. 不开始合并。

---

## 比较范围

### Requirement / Use Case

- 原始 Requirement；
- 历史检索；
- A；
- B1；
- B2；
- C；
- prefill；
- evidence；
- confidence；
- conflict pool。

### AI Guided Form

- 33 fields；
- 4 modules；
- P0；
- visibility；
- dependency；
- mutual exclusion；
- conflict；
- cleanup；
- question generation；
- confirmation question；
- grouping；
- collector；
- ranker；
- planner；
- 1–3 questions；
- partial completion；
- Action Preview；
- InternalImpactPlan；
- Smart Validation。

### State

- centralized state；
- actions/events；
- reducer；
- direct mutation；
- reset；
- persist；
- back navigation；
- highlight；
- workflow state。

### AC

- `user_requirement`；
- no `requirement_summary`；
- confirmed channel；
- language list；
- AC-only；
- no Given/When/Then；
- no Bilingual。

### Validation

- text/screenshot input；
- request schema；
- response schema；
- Validation Report；
- error handling；
- API adapter；
- mockability；
- external dependency handling。

---

## Validation 规则

当前 live API 不可用时：

- 保留代码；
- 比较 contract；
- 检查与原后端流程是否一致；
- 使用 mock 或 fixture 验证；
- 标记 live integration 为 unavailable；
- 不得自动重写。

只有发现明确代码差异或逻辑回归时，才提出定向修复。

---

## 输出

```text
reports/phase2/01-backend-architecture-map.md
reports/phase2/02-api-contract-matrix.md
reports/phase2/03-capability-matrix.md
reports/phase2/04-bug-regression-matrix.md
reports/phase2/05-source-of-truth-map.md
reports/phase2/06-backend-baseline-decision.md
reports/phase2/07-controlled-merge-plan.md
```

### Source of Truth 格式

| Capability | Recommended source | Evidence | Adaptation | Tests |
|---|---|---|---|---|

### Merge Plan 只包含

- Backend baseline；
- API；
- State / Reducer；
- Bug fixes；
- Requirement；
- Use Case；
- Guided Form；
- AC；
- Validation；
- React integration。

不得包含：

- Content Preparation；
- Template；
- UAT；
- Release；
- 其他静态 SDLC 页面。

---

## 验收标准

1. 后端基线有证据；
2. 每项功能有来源；
3. Demo 后端新增能力被识别；
4. 旧 Bug 修复被识别；
5. Validation 被保留；
6. API 不可用被标为 external dependency；
7. 未擅自重写 Validation；
8. 静态 SDLC 页面不在迁移计划；
9. candidates 未修改；
10. 未开始 Phase 3/4。

---

## 最终回复

```markdown
## Phase 2 Result

- Status:
- Recommended backend baseline:
- Capabilities to migrate:
- Regressions to restore:
- AC source:
- Validation source:
- Validation live API status:
- Out-of-scope SDLC excluded:
- Candidate source modified:
- Blockers:
- Ready for Phase 3:
```
