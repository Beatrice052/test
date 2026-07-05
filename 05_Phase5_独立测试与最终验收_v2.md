# Phase 5 — 独立测试与最终验收 V2

## 目标

验证真实产品范围：

```text
Requirement
→ Use Case
→ AI Guided Form
→ AC
→ Validation
```

不验收完整 MDC Messaging SDLC。

---

## 强制限制

1. 第一轮只测试；
2. 不因页面打开就判定通过；
3. 不因 HTTP 200 就判定通过；
4. 不因 Validation live API 暂时不可用判定代码失败；
5. 必须执行 mock 和 contract test；
6. 不得隐藏失败；
7. 不得验收 out-of-scope 静态页面。

---

## 必跑场景

### 1. 新建 Use Case

- Requirement；
- C；
- P0；
- dependency；
- 1–3 questions；
- all required fields。

### 2. A 分支

复用不修改。

### 3. B1

修改且保持 ID。

### 4. B2

修改且创建新 ID。

### 5. Channel 变化

验证：

- reducer；
- cleanup；
- visibility；
- no stale value；
- Action Preview。

### 6. Reference Prefill

- existing values；
- confirmation questions；
- no repeated questioning；
- evidence/confidence。

### 7. Conflict

- conflict detection；
- clarification；
- resolution。

### 8. Cross-module Highlight

- correct fields；
- correct module；
- reducer-driven。

### 9. Complete All Fields

- 33 fields；
- 4 modules；
- required completion；
- completion state。

### 10. AC

- original user_requirement；
- no requirement_summary；
- confirmed channel；
- languages；
- AC-only；
- no Given/When/Then；
- no Bilingual。

### 11. Validation Mock

- screenshot/text payload；
- request contract；
- mock response；
- state transition；
- error handling。

### 12. Validation Report

- report rendering；
- result preservation；
- retry/error。

### 13. State Mutation Audit

检查：

- current use case；
- branch；
- form；
- channel；
- language；
- questions；
- highlight；
- conflict；
- preview；
- AC；
- validation。

---

## Validation 判定规则

### 可以通过本地验收

当以下全部通过：

- Validation code exists；
- Request schema passes；
- Response schema passes；
- mock adapter passes；
- error handling passes；
- frontend renders report；
- no regression evidence。

### 标记 External Dependency

如果 live API 由于网络、权限或环境暂时不可用：

```text
LIVE VALIDATION API: NOT EXECUTED — EXTERNAL DEPENDENCY
```

不得写：

```text
Validation implementation failed
```

除非存在明确代码错误。

---

## 输出

```text
recovered-main/recovery-docs/final-test-report.md
recovered-main/recovery-docs/final-capability-matrix.md
recovered-main/recovery-docs/state-mutation-audit.md
recovered-main/recovery-docs/frontend-visual-verification.md
recovered-main/recovery-docs/e2e-scenario-report.md
recovered-main/recovery-docs/validation-verification.md
recovered-main/recovery-docs/final-open-risks.md
```

---

## 最终结论

只能使用：

```text
READY FOR INTERNAL DEMO
READY FOR BUSINESS UAT
NOT READY — TARGETED FIXES REQUIRED
NOT READY — ARCHITECTURAL ISSUES REMAIN
```

---

## 验收标准

1. 13 个场景有结果；
2. 33 字段和 4 模块通过；
3. A/B1/B2/C 通过；
4. Reducer audit 通过；
5. AC 通过；
6. Validation mock/contract 通过；
7. live API 状态准确记录；
8. React 交互未退化；
9. HTML 排版已迁移；
10. 静态 SDLC 页面未进入验收；
11. 失败未隐藏；
12. 有明确建议。

---

## 最终回复

```markdown
## Phase 5 Result

- Final recommendation:
- Unit:
- Contract:
- Regression:
- Integration:
- E2E:
- Visual:
- State mutation audit:
- AC:
- Validation mock:
- Validation live API:
- Failed Capability IDs:
- Blocking risks:
```
