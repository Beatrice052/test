# Phase 1 — 冻结现场与机械化盘点 V2

## 目标

建立所有候选版本的客观索引，同时严格区分：

- 本次恢复范围；
- Demo 中的完整 MDC Messaging SDLC 静态展示范围。

本阶段只读，不修改代码。

---

## In Scope

- Requirement；
- Historical Use Case；
- A/B1/B2/C；
- AI-Guided Form；
- 33 字段；
- 4 模块；
- Metadata；
- Dependency；
- Planner；
- Conflict；
- State / Reducer；
- AC；
- Validation。

## Out of Scope

- Content Preparation 静态页面；
- Message Template 静态页面；
- UAT 静态页面；
- Release 静态页面；
- Demo 中同事制作的其他 MDC SDLC 展示页面。

Out-of-scope 文件只需要登记，不进入后续深读清单。

---

## 强制限制

1. 不得修改 `candidates/`；
2. 不得开始合并；
3. 不得选择最终后端；
4. 不得深入解释静态 SDLC 页面；
5. 不得依据时间戳；
6. 不得输出完整源码；
7. 完成后停止。

---

## 执行步骤

### 1. 读取输入

读取：

```text
inputs/recovery-notes.md
inputs/business-rules.md
```

### 2. 建立候选清单

记录：

- Candidate ID；
- React / HTML / backend 类型；
- 启动入口；
- API；
- State；
- Reducer；
- Tests；
- AC；
- Validation；
- 环境变量名称。

### 3. 机械扫描

创建：

```text
tools/build_inventory.py
```

输出：

```text
reports/phase1/file-inventory.json
reports/phase1/duplicate-groups.json
reports/phase1/changed-file-groups.json
```

排除：

```text
node_modules
dist
build
.venv
venv
__pycache__
.pytest_cache
coverage
.git
logs
cache
```

### 4. Symbol 索引

输出：

```text
reports/phase1/backend-symbol-index.json
reports/phase1/frontend-symbol-index.json
reports/phase1/api-route-index.json
reports/phase1/test-index.json
```

### 5. Scope 分类

为 HTML Demo 中每个主要页面或模块标记：

- `IN_SCOPE_VISUAL_REFERENCE`
- `IN_SCOPE_BACKEND_CANDIDATE`
- `OUT_OF_SCOPE_STATIC_SDLC`
- `UNKNOWN_REQUIRES_REVIEW`

输出：

```text
reports/phase1/demo-scope-classification.md
```

### 6. 深读短名单

只加入：

- Requirement；
- Use Case；
- Form；
- Planner；
- Dependency；
- State；
- Reducer；
- AC；
- Validation；
- React relevant components；
- HTML relevant layout/CSS。

静态 SDLC 页面不得进入短名单。

输出：

```text
reports/phase1/deep-read-shortlist.md
```

---

## 必须生成

```text
reports/phase1/01-candidate-inventory.md
reports/phase1/file-inventory.json
reports/phase1/duplicate-groups.json
reports/phase1/changed-file-groups.json
reports/phase1/backend-symbol-index.json
reports/phase1/frontend-symbol-index.json
reports/phase1/api-route-index.json
reports/phase1/test-index.json
reports/phase1/demo-scope-classification.md
reports/phase1/deep-read-shortlist.md
reports/phase-status.md
reports/decision-register.md
tools/build_inventory.py
```

---

## 验收标准

1. 候选全部识别；
2. React + Vite 正确识别；
3. HTML Demo 正确识别；
4. Demo 静态 SDLC 页面正确标记；
5. In-scope 后端入口完整；
6. AC 与 Validation 已索引；
7. 静态页面未进入深读；
8. candidates 未修改；
9. 未开始合并；
10. 未开始 Phase 2。

---

## 最终回复

```markdown
## Phase 1 Result

- Status:
- React candidate:
- HTML Demo candidate:
- Backend candidates:
- In-scope files:
- Out-of-scope static SDLC files:
- Deep-read shortlist size:
- Candidate source modified:
- Blockers:
- Ready for Phase 2:
```
