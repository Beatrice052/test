# Phase 4 — 受控恢复与代码实施

## 角色

你是负责恢复主线的高级全栈工程师。你必须严格依据 Phase 2 和 Phase 3 的报告实施，不得重新自由发挥架构。

---

## 阶段目标

创建唯一主版本：

```text
recovered-main/
```

并完成：

- Git 初始化；
- 后端基线；
- 统一 API Contract；
- Reducer/State 收口；
- 已知 Bug 修复；
- 后端能力逐项迁移；
- React + Vite 正式前端；
- HTML Demo 排版迁移；
- 自动测试；
- 恢复日志。

---

## 必须先读取

按顺序读取：

```text
reports/phase-status.md
reports/decision-register.md
reports/phase2/05-source-of-truth-map.md
reports/phase2/06-backend-baseline-decision.md
reports/phase2/07-controlled-merge-plan.md
reports/phase3/03-layout-to-react-mapping.md
reports/phase3/04-interaction-preservation-matrix.md
reports/phase3/06-frontend-implementation-plan.md
reports/phase3/07-frontend-acceptance-checklist.md
```

除非某项证据不足，否则不得重新进行全仓比较。

---

## 强制限制

1. `candidates/` 永远只读。
2. 不得整体复制某个候选覆盖另一个候选。
3. 不得把 HTML Demo 作为正式前端。
4. 不得删除 React + Vite 的交互架构。
5. 不得让 UI 组件直接修改核心业务状态。
6. 不得一次合并多个无关能力。
7. 每个 Change ID 必须独立验证和提交。
8. 测试未执行不得声称通过。
9. 外部 LLM 测试与确定性测试分开。
10. 每完成一个批次都必须更新恢复日志。
11. 出现报告冲突时停止当前 Change ID，记录问题，不得猜测。

---

## Token 节省策略

### 1. 按 Change ID 工作

一次只处理一个 Change ID，完成后记录结果，再继续下一个。

### 2. 只读取来源模块、目标模块和直接依赖

不得为了一个小修复重新解释整个项目。

### 3. 聊天只汇报摘要

代码和测试结果写入仓库文件，不在聊天粘贴完整 diff。

### 4. 使用 Git diff 做局部自检

每个提交前只审查当前 Change ID 的 diff。

### 5. 失败时停止扩散

某项测试失败时，只修当前 Change ID，不顺手重构无关代码。

---

## 执行步骤

### Step 1：创建 recovered-main

依据 Phase 2 的后端基线创建：

```text
recovered-main/backend
```

依据 Phase 3 决策，从原 React + Vite 候选创建：

```text
recovered-main/frontend
```

注意：

- 后端来源和前端来源可以不同。
- HTML Demo 不作为 frontend 根目录来源。
- HTML Demo 只作为后续视觉参照。

创建：

```text
recovered-main/recovery-docs/
```

### Step 2：初始化 Git

创建 `.gitignore`，排除：

```text
.env*
node_modules/
dist/
build/
.venv/
venv/
__pycache__/
.pytest_cache/
coverage/
*.log
```

检查敏感信息后：

```text
git init
git add .
git commit -m "recovery: establish backend and React Vite baselines"
```

创建：

```text
recovery-docs/baseline.md
recovery-docs/recovery-log.md
```

### Step 3：先稳定启动，不迁移功能

先确保：

- 后端可以启动；
- React + Vite 可以启动；
- 基础 API 可连通；
- 环境变量有模板；
- 不要求立即完成功能。

提交：

```text
chore: make recovery baseline runnable
```

### Step 4：建立统一 API Contract

依据 Phase 2：

- 定义 Request/Response Schema；
- 建立统一 API Client；
- 统一错误格式；
- 对旧接口做 adapter；
- 不让 React 组件散落 fetch；
- 不让 HTML Demo 临时接口成为正式标准。

先写 Contract Tests，再改实现。

提交：

```text
refactor: establish canonical frontend backend contracts
```

### Step 5：收口 State/Reducer

处理：

- action/event；
- reducer；
- selector；
- dependency cleanup；
- workflow transition；
- highlight state；
- conflict state；
- Action Preview state。

搜索并分类所有 direct mutation：

- approved initialization；
- reducer-driven；
- invalid direct mutation；
- test-only。

修复 invalid direct mutation。

提交：

```text
refactor: route core state transitions through reducer
```

### Step 6：先恢复已知 Bug

对 Phase 2 的每个 Bug：

1. 新增失败测试；
2. 确认测试在当前 baseline 失败；
3. 迁移最小修复；
4. 运行测试；
5. 独立提交。

格式：

```text
fix(BUG-XXX): restore ...
```

不得为了修一个 Bug 复制整个文件。

### Step 7：迁移后端能力

严格按照 `07-controlled-merge-plan.md`：

- Metadata；
- Dependency；
- Profiler；
- Candidate Collector；
- Question Generator；
- Grouping；
- Ranker；
- Planner；
- Conflict Resolver；
- Partial Completion；
- Action Preview；
- InternalImpactPlan；
- Smart Validation；
- Workflow；
- Content Preparation；
- Message Templates；
- AC；
- Validation Report；
- Release Check。

每项：

- 记录来源版本；
- 适配统一 Schema；
- 增加测试；
- 单独提交；
- 更新 recovery-log。

### Step 8：迁移 HTML Demo 排版到 React

严格按照 Phase 3 的批次：

#### 8.1 App Shell

- 引入 design tokens；
- 建立整体网格；
- 不改业务状态。

#### 8.2 Workflow Header

- 对齐 HTML Demo 排版；
- 保留 React Workflow 状态和事件。

#### 8.3 Sidebar

- 对齐视觉；
- 保留模块跳转和完成状态。

#### 8.4 Main Form

- 对齐宽度、滚动和卡片结构；
- 保留 Dynamic Form、Validation、Prefill 和 Highlight。

#### 8.5 Assistant Area

- 视觉上合并 Guidance/Chat；
- 逻辑上保留明确的数据流；
- 展示为何提问和 Action Preview。

#### 8.6 Highlight

- 使用 React state/reducer；
- 禁止 DOM query 驱动业务状态；
- 验证跨模块高亮。

#### 8.7 Responsive

- 不出现不必要横向滚动；
- 低宽度下合理折叠。

每个批次独立提交。

### Step 9：AC 最新规则

必须保证：

- 输入使用原始 `user_requirement`；
- 不需要 `requirement_summary`；
- 使用 confirmed channel；
- 使用语言列表；
- 只输出 AC 文本行；
- 不输出 Given/When/Then/Pass；
- 每种语言和渠道分别枚举；
- 不使用 `Bilingual`。

增加结构化验证和测试。

### Step 10：建立测试矩阵

至少包括：

```text
tests/unit/
tests/contract/
tests/regression/
tests/integration/
tests/e2e/
```

外部 LLM：

- 默认 mock；
- live test 单独标记；
- 不把随机 LLM 输出作为 CI 唯一依据。

### Step 11：持续记录

`recovery-log.md` 格式：

| Change ID | Capability | Source | Target | Tests | Commit | Result |
|---|---|---|---|---|---|---|

另建：

```text
recovery-docs/discarded-implementations.md
recovery-docs/open-risks.md
```

### Step 12：完成后更新阶段状态

记录：

- 已完成 Change ID；
- 未完成 Change ID；
- 测试；
- 阻塞；
- 是否可进入 Phase 5。

---

## 每个 Change ID 的验收模板

```markdown
### Change ID

- Scope:
- Source candidate:
- Target files:
- Business behavior:
- Logic intentionally preserved:
- Tests added:
- Tests executed:
- Result:
- Git commit:
- Rollback:
- Unresolved risks:
```

未填写完整不得进入下一个 Change ID。

---

## Phase 4 总体验收标准

1. `recovered-main` 已建立。
2. Git 已初始化。
3. 候选目录未修改。
4. React + Vite 是正式前端。
5. HTML Demo 排版已迁移到 React，而不是整页嵌入。
6. API Contract 已统一。
7. 核心状态通过 reducer 或统一入口。
8. 已知 Bug 有失败测试和修复测试。
9. 功能迁移有来源记录。
10. 每个 Change ID 独立提交。
11. 测试目录完整。
12. 恢复日志完整。
13. 没有未经记录的整文件覆盖。
14. 可进入独立验收。

---

## 最终回复格式

```markdown
## Phase 4 Result

- Status: PASS / FAIL
- recovered-main created:
- Git initialized:
- Canonical frontend:
- Backend baseline:
- Completed Change IDs:
- Restored Bug IDs:
- React visual migration batches completed:
- Tests executed:
- Tests passed:
- Tests failed:
- Candidate source modified: YES / NO
- Open risks:
- Ready for Phase 5: YES / NO
```

完成后停止。
