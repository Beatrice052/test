# Phase 4 — 受控恢复与代码实施 V2

## 目标

创建：

```text
recovered-main/
```

正式实现范围：

```text
Requirement
→ Use Case
→ AI Guided Form
→ AC
→ Validation
```

不得恢复完整 MDC Messaging SDLC。

---

## 必须先读取

```text
reports/decision-register.md
reports/phase2/05-source-of-truth-map.md
reports/phase2/06-backend-baseline-decision.md
reports/phase2/07-controlled-merge-plan.md
reports/phase3/03-layout-to-react-mapping.md
reports/phase3/04-interaction-preservation-matrix.md
reports/phase3/06-frontend-implementation-plan.md
```

---

## 强制限制

1. candidates 只读；
2. 不完整目录覆盖；
3. React + Vite 为正式前端；
4. HTML 只迁移视觉；
5. 不迁移静态 SDLC 页面；
6. 核心状态通过 reducer；
7. 每个 Change ID 独立提交；
8. Validation API 不可用时使用 mock；
9. 不因 live API 失败重写 Validation；
10. 测试未执行不得声称通过。

---

## 实施顺序

### 1. 建立 Baseline

- backend：Phase 2 推荐基线；
- frontend：react-original；
- 初始化 Git；
- baseline commit。

### 2. 基础启动

- backend start；
- React start；
- env example；
- 基础连接；
- secret check。

### 3. API Contract

只建立本范围 API：

- Requirement；
- Use Case；
- Intake Session；
- Answer；
- Next Questions；
- Form State；
- AC；
- Validation。

### 4. State / Reducer

统一：

- current use case；
- branch；
- form fields；
- module；
- active questions；
- highlighted fields；
- conflicts；
- Action Preview；
- AC；
- Validation state。

### 5. 恢复 Bug

每个 Bug：

1. failing test；
2. minimal fix；
3. focused test；
4. commit。

### 6. 迁移 Guided Intake

- metadata；
- dependency；
- profiler；
- collector；
- generator；
- grouping；
- ranker；
- planner；
- conflict；
- partial completion；
- preview；
- validation。

### 7. 迁移 AC

保证：

```text
AC1: Whether a Chinese SMS body is provided.
```

无 Given/When/Then。

### 8. 保留 Validation

- 迁移现有代码；
- 统一 contract；
- 增加 mock adapter；
- 增加 fixture；
- 增加 contract test；
- live API 使用 feature flag 或环境配置；
- 记录 external dependency。

### 9. React 视觉改造

只改 in-scope 页面：

- Requirement；
- Use Case；
- Guided Form；
- AC；
- Validation。

不迁移其他静态 SDLC 页面。

### 10. 测试

```text
tests/unit
tests/contract
tests/regression
tests/integration
tests/e2e
```

---

## Recovery Log

```text
recovered-main/recovery-docs/recovery-log.md
```

格式：

| Change ID | Scope | Source | Target | Tests | Commit | Result |
|---|---|---|---|---|---|---|

---

## 验收标准

1. recovered-main 存在；
2. Git 已初始化；
3. React + Vite 为正式前端；
4. 后端基线有记录；
5. API Contract 仅覆盖真实范围；
6. State 统一；
7. Bug 有测试；
8. 33 字段和 4 模块保留；
9. AC 正确；
10. Validation 代码保留；
11. Validation mock/contract test 通过；
12. 静态 SDLC 页面未迁移；
13. candidates 未修改；
14. recovery log 完整。

---

## 最终回复

```markdown
## Phase 4 Result

- Status:
- recovered-main:
- Backend baseline:
- Canonical frontend:
- Completed Change IDs:
- Restored Bug IDs:
- AC status:
- Validation local/mock status:
- Validation live API status:
- Out-of-scope SDLC migrated: YES / NO
- Candidate source modified:
- Tests:
- Open risks:
- Ready for Phase 5:
```
